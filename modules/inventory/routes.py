from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import flash, redirect, render_template, request, url_for

from core import db
from core.decorators import permission_required
from modules.accounting.models import SupplierInvoice
from modules.inventory import inventory_bp
from modules.inventory.models import Product, StockMove
from modules.purchasing.models import BusinessPartner, PurchaseOrder


def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _apply_receipt(product: Product, quantity: Decimal, unit_cost: Decimal, source_document: str) -> None:
    current_stock = _to_decimal(product.current_stock)
    average_cost = _to_decimal(product.average_cost)
    quantity = _to_decimal(quantity)
    unit_cost = _to_decimal(unit_cost)
    total_stock = current_stock + quantity
    if total_stock > 0:
        new_average_cost = ((current_stock * average_cost) + (quantity * unit_cost)) / total_stock
    else:
        new_average_cost = unit_cost
    product.current_stock = total_stock
    product.average_cost = new_average_cost
    product.stock_moves.append(
        StockMove(
            quantity=quantity,
            unit_cost=unit_cost,
            source_document=source_document,
            move_type="receipt",
        )
    )


@inventory_bp.route("/")
@permission_required("inventory:view")
def dashboard():
    search = request.args.get("search", "").strip()
    partner_id = request.args.get("partner_id", "").strip()
    product_query = Product.query
    move_query = StockMove.query
    if search:
        like = f"%{search}%"
        product_query = product_query.filter((Product.sku.ilike(like)) | (Product.name.ilike(like)))
        move_query = move_query.join(StockMove.product).filter(
            (StockMove.source_document.ilike(like)) | (Product.name.ilike(like))
        )
    if partner_id.isdigit():
        product_query = product_query.filter(Product.assigned_partner_id == int(partner_id))
    products = product_query.order_by(Product.name.asc()).all()
    recent_moves = move_query.order_by(StockMove.created_at.desc()).limit(10).all()
    open_pos = PurchaseOrder.query.filter(PurchaseOrder.status != "Received").order_by(PurchaseOrder.created_at.desc()).all()
    partners = BusinessPartner.query.order_by(BusinessPartner.name.asc()).all()
    stats = {
        "products": Product.query.count(),
        "open_orders": PurchaseOrder.query.filter(PurchaseOrder.status.in_(["Draft", "Confirmed", "Approved", "Done"])).count(),
        "stock_moves": StockMove.query.count(),
        "suppliers": BusinessPartner.query.filter(BusinessPartner.partner_type.in_(["supplier", "both"])).count(),
    }
    return render_template(
        "inventory/dashboard.html",
        products=products,
        recent_moves=recent_moves,
        open_pos=open_pos,
        partners=partners,
        stats=stats,
        search=search,
        partner_id=partner_id,
    )


@inventory_bp.route("/products", methods=["GET", "POST"])
@permission_required("inventory:view")
def products():
    search = request.args.get("search", "").strip()
    partner_id = request.args.get("partner_id", "").strip()

    product_query = Product.query
    if search:
        like = f"%{search}%"
        product_query = product_query.filter((Product.sku.ilike(like)) | (Product.name.ilike(like)))
    if partner_id.isdigit():
        product_query = product_query.filter(Product.assigned_partner_id == int(partner_id))

    products = product_query.order_by(Product.name.asc()).all()
    partners = BusinessPartner.query.order_by(BusinessPartner.name.asc()).all()
    stats = {
        "products": Product.query.count(),
        "tagged": Product.query.filter(Product.assigned_partner_id.isnot(None)).count(),
        "purchase_items": Product.query.filter(Product.tag_kind == "purchase").count(),
        "suppliers": BusinessPartner.query.filter(BusinessPartner.partner_type.in_(["supplier", "both"])).count(),
    }

    if request.method == "POST":
        action = request.form.get("action")
        if action in {"create_product", "update_product"}:
            sku = request.form.get("sku", "").strip()
            name = request.form.get("name", "").strip()
            uom = request.form.get("uom", "").strip()
            if not sku or not name or not uom:
                flash("SKU, name, and UoM are required.", "warning")
                return redirect(url_for("inventory.products"))

            if action == "create_product":
                if Product.query.filter_by(sku=sku).first():
                    flash("A product with that SKU already exists.", "warning")
                    return redirect(url_for("inventory.products"))
                product = Product()
                db.session.add(product)
                flash_message = f"Created product {name}."
            else:
                product = db.session.get(Product, int(request.form["product_id"]))
                if not product:
                    flash("Product not found.", "warning")
                    return redirect(url_for("inventory.products"))
                flash_message = f"Updated product {name}."

            product.sku = sku
            product.name = name
            product.uom = uom
            product.current_stock = _to_decimal(request.form.get("current_stock", 0))
            product.average_cost = _to_decimal(request.form.get("average_cost", 0))
            product.tag_kind = request.form.get("tag_kind", "purchase")
            assigned_partner_id = request.form.get("assigned_partner_id") or None
            product.assigned_partner_id = int(assigned_partner_id) if assigned_partner_id and assigned_partner_id.isdigit() else None
            db.session.commit()
            flash(flash_message, "success")
            return redirect(url_for("inventory.products", search=search, partner_id=partner_id))

    return render_template(
        "inventory/products.html",
        products=products,
        partners=partners,
        stats=stats,
        search=search,
        partner_id=partner_id,
    )


@inventory_bp.route("/receive/<int:po_id>", methods=["POST"])
@permission_required("inventory:receive")
def receive_purchase_order(po_id: int):
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.status not in {"Draft", "Confirmed", "Approved", "Done"}:
        flash("Only open purchase orders can be received.", "warning")
        return redirect(url_for("inventory.dashboard"))

    for line_item in po.line_items:
        _apply_receipt(line_item.product, line_item.quantity, line_item.unit_price, po.serial)

    po.status = "Received"
    if not po.invoice:
        po.invoice = SupplierInvoice(
            invoice_ref=f"INV-{po.serial}",
            issue_date=po.created_at.date() if po.created_at else date.today(),
            due_date=po.created_at.date() if po.created_at else date.today(),
            amount_total=po.total_amount,
            state="Unpaid",
        )
    db.session.commit()
    flash(f"Receiving completed for {po.serial}. Supplier bill drafted automatically.", "success")
    return redirect(url_for("accounting.invoice_detail", invoice_id=po.invoice.id))


@inventory_bp.route("/tag/<int:product_id>", methods=["POST"])
@permission_required("inventory:tag")
def tag_product(product_id: int):
    product = Product.query.get_or_404(product_id)
    partner_id = request.form.get("assigned_partner_id") or None
    tag_kind = request.form.get("tag_kind", "purchase")
    product.tag_kind = tag_kind
    product.assigned_partner_id = int(partner_id) if partner_id and partner_id.isdigit() else None
    db.session.commit()
    flash(f"Updated tag for {product.name}.", "success")
    return redirect(url_for("inventory.dashboard", search=request.args.get("search", ""), partner_id=partner_id or ""))
