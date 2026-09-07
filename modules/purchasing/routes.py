from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from core import db
from core.models import CompanySetting
from core.decorators import permission_required
from modules.accounting.models import SupplierInvoice
from modules.inventory.models import Product
from modules.purchasing import purchasing_bp
from modules.purchasing.models import BusinessPartner, POLineItem, PurchaseOrder, PurchaseRequisition, PurchaseRequisitionLineItem, Vendor

PSGC_API_BASE = "https://psgc.cloud/api/v2"


def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _partner_address(partner: BusinessPartner | None) -> str:
    return partner.address if partner and partner.address else ""


def _compose_address(form) -> str:
    address_mode = (form.get("scope_type") or "local").strip().lower()
    if address_mode == "private":
        return form.get("private_address", "").strip()
    parts = [
        form.get("street", "").strip(),
        form.get("barangay", "").strip(),
        form.get("city", "").strip(),
        form.get("province", "").strip(),
        "Philippines",
    ]
    return ", ".join([part for part in parts if part])


def _psgc_get(path: str, params: dict | None = None):
    query = f"?{urlencode(params or {})}" if params else ""
    req = Request(f"{PSGC_API_BASE}{path}{query}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError):
        return []


def _normalize_psgc_item(item, label_key: str = "name", value_key: str = "code"):
    if isinstance(item, dict):
        return {
            "id": item.get(value_key) or item.get("code") or item.get("name"),
            "text": item.get(label_key) or item.get("name") or item.get("code"),
        }
    return {"id": item, "text": str(item)}


def _extract_psgc_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _company_acronym() -> str:
    setting = CompanySetting.get_solo()
    acronym = (setting.acronym or "INV").strip().upper()
    return acronym or "INV"


def _next_serial(model, document_code: str) -> str:
    year = date.today().year
    prefix = f"{_company_acronym()}-{document_code}-{year}-"
    latest = (
        model.query.filter(model.serial.like(f"{prefix}%"))
        .order_by(model.serial.desc())
        .first()
    )
    sequence = 1
    if latest and latest.serial:
        match = re.search(r"(\d+)$", latest.serial)
        if match:
            sequence = int(match.group(1)) + 1
    return f"{prefix}{sequence:04d}"


def _copy_requisition_to_po(requisition: PurchaseRequisition, po_status: str = "Draft") -> PurchaseOrder:
    po = PurchaseOrder(
        serial=_next_serial(PurchaseOrder, "PO"),
        requisition=requisition,
        vendor_name=requisition.partner_name_snapshot or "Unassigned",
        partner=requisition.partner,
        status=po_status,
        total_amount=requisition.total_estimated_cost,
    )
    db.session.add(po)
    db.session.flush()
    for line in requisition.line_items:
        db.session.add(
            POLineItem(
                po=po,
                product=line.product,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
        )
    return po


@purchasing_bp.route("/address/provinces")
@permission_required("purchasing:view")
def address_provinces():
    q = request.args.get("q", "").strip()
    payload = _psgc_get("/provinces")
    items = _extract_psgc_items(payload)
    results = []
    for item in items:
        normalized = _normalize_psgc_item(item)
        if q and q.lower() not in normalized["text"].lower():
            continue
        results.append(normalized)
    return jsonify(results=results)


@purchasing_bp.route("/address/cities")
@permission_required("purchasing:view")
def address_cities():
    q = request.args.get("q", "").strip()
    province = request.args.get("province", "").strip()
    if province:
        payload = _psgc_get(f"/provinces/{province}/cities-municipalities")
    else:
        payload = _psgc_get("/cities-municipalities")
    items = _extract_psgc_items(payload)
    results = []
    for item in items:
        normalized = _normalize_psgc_item(item)
        if q and q.lower() not in normalized["text"].lower():
            continue
        results.append(normalized)
    return jsonify(results=results)


@purchasing_bp.route("/address/barangays")
@permission_required("purchasing:view")
def address_barangays():
    q = request.args.get("q", "").strip()
    city = request.args.get("city", "").strip()
    province = request.args.get("province", "").strip()
    if city:
        payload = _psgc_get(f"/cities-municipalities/{city}/barangays")
    elif province:
        payload = _psgc_get(f"/provinces/{province}/barangays")
    else:
        payload = _psgc_get("/barangays")
    items = _extract_psgc_items(payload)
    results = []
    for item in items:
        normalized = _normalize_psgc_item(item)
        if q and q.lower() not in normalized["text"].lower():
            continue
        results.append(normalized)
    return jsonify(results=results)


def _partner_directory_context(display_type: str, show_all: bool = False):
    if display_type == "supplier":
        return {
            "title": "Partners",
            "subtitle": "Manage supplier and client records used in procurement.",
            "default_partner_type": "supplier",
            "query_filter": None if show_all else BusinessPartner.partner_type.in_(["supplier", "both"]),
            "partner_type_options": [("supplier", "Supplier"), ("customer", "Client"), ("both", "Both")],
            "show_all": show_all,
        }
    return {
        "title": "Clients",
        "subtitle": "Manage client records and the address used when creating purchase requests.",
        "default_partner_type": "customer",
        "query_filter": BusinessPartner.partner_type.in_(["customer", "both"]),
        "partner_type_options": [("customer", "Client"), ("both", "Both")],
    }


@purchasing_bp.route("/", methods=["GET", "POST"])
@permission_required("purchasing:view")
def dashboard():
    search = request.args.get("search", "").strip()
    partner_type = request.args.get("partner_type", "").strip()
    scope_type = request.args.get("scope_type", "").strip()
    status = request.args.get("status", "").strip()

    requisition_query = PurchaseRequisition.query
    if search:
        like = f"%{search}%"
        requisition_query = requisition_query.filter(
            (PurchaseRequisition.serial.ilike(like))
            | (PurchaseRequisition.partner_name_snapshot.ilike(like))
            | (PurchaseRequisition.partner_address_snapshot.ilike(like))
        )
    if partner_type:
        requisition_query = requisition_query.filter(PurchaseRequisition.partner_type == partner_type)
    if status:
        requisition_query = requisition_query.filter(PurchaseRequisition.status == status)
    requisitions = requisition_query.order_by(PurchaseRequisition.created_at.desc()).all()

    purchase_order_query = PurchaseOrder.query
    if search:
        like = f"%{search}%"
        purchase_order_query = purchase_order_query.filter(
            (PurchaseOrder.serial.ilike(like))
            | (PurchaseOrder.vendor_name.ilike(like))
        )
    if status:
        purchase_order_query = purchase_order_query.filter(PurchaseOrder.status == status)
    purchase_orders = purchase_order_query.order_by(PurchaseOrder.created_at.desc()).all()

    products = Product.query.order_by(Product.name.asc()).all()
    suppliers = BusinessPartner.query.filter(BusinessPartner.partner_type.in_(["supplier", "both"])).order_by(BusinessPartner.name.asc()).all()
    clients = BusinessPartner.query.filter(BusinessPartner.partner_type.in_(["customer", "both"])).order_by(BusinessPartner.name.asc()).all()
    vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    next_request_serial = _next_serial(PurchaseRequisition, "PR")
    stats = {
        "suppliers": len(suppliers),
        "clients": len(clients),
        "requests": PurchaseRequisition.query.count(),
        "orders": PurchaseOrder.query.count(),
        "products": Product.query.count(),
        "bills": SupplierInvoice.query.count(),
    }

    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_requisition":
            if not (current_user.has_permission("purchasing:create") or current_user.has_permission("admin:settings")):
                flash("You do not have permission to create purchase requests.", "warning")
                return redirect(url_for("purchasing.dashboard"))
            requisition_partner_type = request.form.get("partner_type", "supplier").strip().lower()
            partner_field = "supplier_partner_id" if requisition_partner_type == "supplier" else "client_partner_id"
            partner_id_raw = request.form.get(partner_field, "").strip()
            partner = db.session.get(BusinessPartner, int(partner_id_raw)) if partner_id_raw.isdigit() else None
            partner_name = request.form.get("partner_name", "").strip() or (partner.name if partner else "")
            partner_address = request.form.get("partner_address", "").strip() or _partner_address(partner)
            if not partner_name:
                flash("Please choose a supplier or client for the purchase request.", "warning")
                return redirect(url_for("purchasing.dashboard"))

            line_rows = []
            product_ids = request.form.getlist("line_product_id")
            quantities = request.form.getlist("line_quantity")
            unit_prices = request.form.getlist("line_unit_price")
            notes = request.form.getlist("line_notes")

            for index, product_id_raw in enumerate(product_ids):
                if not product_id_raw or not product_id_raw.isdigit():
                    continue
                product = db.session.get(Product, int(product_id_raw))
                if not product:
                    continue
                quantity = _to_decimal(quantities[index] if index < len(quantities) else 0)
                if quantity <= 0:
                    continue
                unit_price = _to_decimal(unit_prices[index] if index < len(unit_prices) and unit_prices[index] else product.average_cost)
                line_rows.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "notes": notes[index].strip() if index < len(notes) and notes[index] else "",
                    }
                )

            if not line_rows:
                flash("Add at least one product line to the purchase request.", "warning")
                return redirect(url_for("purchasing.dashboard"))

            serial = _next_serial(PurchaseRequisition, "PR")
            total_estimated_cost = sum((row["quantity"] * row["unit_price"] for row in line_rows), Decimal("0"))
            requisition = PurchaseRequisition(
                serial=serial,
                requested_by_id=current_user.id,
                partner_type=requisition_partner_type,
                partner_id=partner.id if partner else None,
                partner_name_snapshot=partner_name,
                partner_address_snapshot=partner_address,
                status="Draft",
                total_estimated_cost=total_estimated_cost,
            )
            db.session.add(requisition)
            db.session.flush()
            for row in line_rows:
                db.session.add(
                    PurchaseRequisitionLineItem(
                        requisition=requisition,
                        product=row["product"],
                        product_sku_snapshot=row["product"].sku,
                        product_name_snapshot=row["product"].name,
                        uom_snapshot=row["product"].uom,
                        quantity=row["quantity"],
                        unit_price=row["unit_price"],
                        notes=row["notes"] or None,
                    )
                )
            db.session.commit()
            flash(f"Created purchase request {serial}.", "success")
            return redirect(url_for("purchasing.requisition_detail", requisition_id=requisition.id))

        return redirect(url_for("purchasing.dashboard", search=search, partner_type=partner_type, scope_type=scope_type, status=status))

    return render_template(
        "purchasing/dashboard.html",
        requisitions=requisitions,
        purchase_orders=purchase_orders,
        products=products,
        suppliers=suppliers,
        clients=clients,
        vendors=vendors,
        next_request_serial=next_request_serial,
        stats=stats,
        search=search,
        partner_type=partner_type,
        scope_type=scope_type,
        status=status,
    )


@purchasing_bp.route("/requests/<int:requisition_id>")
@permission_required("purchasing:view")
def requisition_detail(requisition_id: int):
    requisition = PurchaseRequisition.query.get_or_404(requisition_id)
    linked_po = requisition.purchase_orders[0] if requisition.purchase_orders else None
    return render_template("purchasing/request_detail.html", requisition=requisition, linked_po=linked_po)


@purchasing_bp.route("/requests/<int:requisition_id>/confirm", methods=["POST"])
@permission_required("purchasing:create")
def confirm_requisition(requisition_id: int):
    requisition = PurchaseRequisition.query.get_or_404(requisition_id)
    if requisition.status not in {"Draft", "Submitted"}:
        flash("Only draft purchase requests can be confirmed.", "warning")
        return redirect(url_for("purchasing.requisition_detail", requisition_id=requisition.id))
    if requisition.purchase_orders:
        flash("This request already has a linked purchase order.", "info")
        return redirect(url_for("purchasing.requisition_detail", requisition_id=requisition.id))
    _copy_requisition_to_po(requisition, po_status="Draft")
    requisition.status = "Confirmed"
    db.session.commit()
    flash(f"Purchase request {requisition.serial} confirmed and converted to a purchase order.", "success")
    return redirect(url_for("purchasing.purchase_orders"))


@purchasing_bp.route("/purchase-orders")
@permission_required("purchasing:approve")
def purchase_orders():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    po_query = PurchaseOrder.query
    if search:
        like = f"%{search}%"
        po_query = po_query.filter(
            (PurchaseOrder.serial.ilike(like))
            | (PurchaseOrder.vendor_name.ilike(like))
            | (PurchaseOrder.status.ilike(like))
        )
    if status:
        po_query = po_query.filter(PurchaseOrder.status == status)
    purchase_orders = po_query.order_by(PurchaseOrder.created_at.desc()).all()
    next_purchase_order_serial = _next_serial(PurchaseOrder, "PO")
    return render_template(
        "purchasing/purchase_orders.html",
        purchase_orders=purchase_orders,
        search=search,
        status=status,
        next_purchase_order_serial=next_purchase_order_serial,
    )


@purchasing_bp.route("/purchase-orders/<int:po_id>")
@permission_required("purchasing:approve")
def purchase_order_detail(po_id: int):
    po = PurchaseOrder.query.get_or_404(po_id)
    return render_template("purchasing/purchase_order_detail.html", po=po)


@purchasing_bp.route("/purchase-orders/<int:po_id>/approve", methods=["POST"])
@permission_required("purchasing:approve")
def approve_purchase_order(po_id: int):
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.status not in {"Draft", "Confirmed"}:
        flash("Only draft or confirmed purchase orders can be approved.", "warning")
        return redirect(url_for("purchasing.purchase_orders"))
    po.status = "Approved"
    db.session.commit()
    flash(f"Purchase order {po.serial} approved.", "success")
    return redirect(url_for("purchasing.purchase_orders"))


@purchasing_bp.route("/purchase-orders/<int:po_id>/purchase", methods=["POST"])
@permission_required("purchasing:approve")
def purchase_purchase_order(po_id: int):
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.status not in {"Approved", "Confirmed", "Draft"}:
        flash("Only draft, confirmed, or approved purchase orders can be marked as purchased.", "warning")
        return redirect(url_for("purchasing.purchase_orders"))
    po.status = "Done"
    db.session.commit()
    flash(f"Purchase order {po.serial} marked as done.", "success")
    return redirect(url_for("purchasing.purchase_orders"))


@purchasing_bp.route("/suppliers", methods=["GET", "POST"])
@permission_required("purchasing:view")
def suppliers():
    return _partner_directory("supplier", show_all=True)


@purchasing_bp.route("/clients", methods=["GET", "POST"])
@permission_required("purchasing:view")
def clients():
    return _partner_directory("customer")


def _partner_directory(display_type: str, show_all: bool = False):
    config = _partner_directory_context(display_type, show_all=show_all)
    search = request.args.get("search", "").strip()

    partner_query = BusinessPartner.query
    if config.get("query_filter") is not None:
        partner_query = partner_query.filter(config["query_filter"])
    if search:
        like = f"%{search}%"
        partner_query = partner_query.filter(
            (BusinessPartner.name.ilike(like))
            | (BusinessPartner.email.ilike(like))
            | (BusinessPartner.address.ilike(like))
        )
    partners = partner_query.order_by(BusinessPartner.name.asc()).all()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_partner":
            if not (current_user.has_permission("purchasing:partner_manage") or current_user.has_permission("admin:settings")):
                flash("You do not have permission to create partners.", "warning")
                return redirect(url_for(f"purchasing.{display_type}s", search=search))
            name = request.form.get("name", "").strip()
            if name and not BusinessPartner.query.filter_by(name=name).first():
                address = _compose_address(request.form)
                partner = BusinessPartner(
                    name=name,
                    email=request.form.get("email", "").strip() or None,
                    phone=request.form.get("phone", "").strip() or None,
                    address=address or None,
                    partner_type=request.form.get("partner_type", config["default_partner_type"]),
                    scope_type=request.form.get("scope_type", "local"),
                )
                db.session.add(partner)
                db.session.commit()
                flash(f"Created partner {partner.name}.", "success")
        elif action == "update_partner":
            if not (current_user.has_permission("purchasing:partner_manage") or current_user.has_permission("admin:settings")):
                flash("You do not have permission to edit partners.", "warning")
                return redirect(url_for(f"purchasing.{display_type}s", search=search))
            partner = db.session.get(BusinessPartner, int(request.form["partner_id"]))
            if partner:
                partner.name = request.form.get("name", partner.name).strip() or partner.name
                partner.email = request.form.get("email", partner.email).strip() or partner.email
                partner.phone = request.form.get("phone", partner.phone).strip() or partner.phone
                partner.address = _compose_address(request.form) or partner.address
                partner.partner_type = request.form.get("partner_type", partner.partner_type)
                partner.scope_type = request.form.get("scope_type", partner.scope_type)
                db.session.commit()
                flash(f"Updated partner {partner.name}.", "success")
        return redirect(url_for(f"purchasing.{display_type}s", search=search))

    return render_template(
        "purchasing/partners.html",
        title=config["title"],
        subtitle=config["subtitle"],
        partners=partners,
        search=search,
        partner_type_options=config["partner_type_options"],
        default_partner_type=config["default_partner_type"],
        show_all=config.get("show_all", False),
    )
