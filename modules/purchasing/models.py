from __future__ import annotations

from datetime import datetime

from core import db


class BusinessPartner(db.Model):
    __tablename__ = "business_partners"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    address = db.Column(db.Text, nullable=True)
    partner_type = db.Column(db.String(20), nullable=False, default="supplier")
    scope_type = db.Column(db.String(20), nullable=False, default="local")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    purchase_orders = db.relationship("PurchaseOrder", back_populates="partner", lazy="selectin")
    inventory_items = db.relationship("Product", back_populates="assigned_partner", lazy="selectin")


class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    purchase_orders = db.relationship("PurchaseOrder", back_populates="vendor", lazy="selectin")


class PurchaseRequisition(db.Model):
    __tablename__ = "purchase_requisitions"

    id = db.Column(db.Integer, primary_key=True)
    serial = db.Column(db.String(80), unique=True, nullable=False, index=True)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    partner_type = db.Column(db.String(20), nullable=True, default="supplier")
    partner_id = db.Column(db.Integer, db.ForeignKey("business_partners.id"), nullable=True)
    partner_name_snapshot = db.Column(db.String(200), nullable=True)
    partner_address_snapshot = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default="Draft", nullable=False)
    total_estimated_cost = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    requested_by = db.relationship("User", lazy="selectin")
    partner = db.relationship("BusinessPartner", lazy="selectin")
    purchase_orders = db.relationship("PurchaseOrder", back_populates="requisition", lazy="selectin")
    line_items = db.relationship(
        "PurchaseRequisitionLineItem",
        back_populates="requisition",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PurchaseRequisitionLineItem(db.Model):
    __tablename__ = "purchase_requisition_line_items"

    id = db.Column(db.Integer, primary_key=True)
    requisition_id = db.Column(db.Integer, db.ForeignKey("purchase_requisitions.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product_sku_snapshot = db.Column(db.String(80), nullable=False)
    product_name_snapshot = db.Column(db.String(200), nullable=False)
    uom_snapshot = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Numeric(14, 2), nullable=False)
    unit_price = db.Column(db.Numeric(14, 4), nullable=False)
    notes = db.Column(db.String(255), nullable=True)

    requisition = db.relationship("PurchaseRequisition", back_populates="line_items", lazy="selectin")
    product = db.relationship("Product", lazy="selectin")

    @property
    def line_total(self):
        return self.quantity * self.unit_price


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)
    serial = db.Column(db.String(80), unique=True, nullable=False, index=True)
    requisition_id = db.Column(db.Integer, db.ForeignKey("purchase_requisitions.id"), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True)
    partner_id = db.Column(db.Integer, db.ForeignKey("business_partners.id"), nullable=True)
    vendor_name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(30), default="Draft", nullable=False)
    total_amount = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    requisition = db.relationship("PurchaseRequisition", back_populates="purchase_orders", lazy="selectin")
    vendor = db.relationship("Vendor", back_populates="purchase_orders", lazy="selectin")
    partner = db.relationship("BusinessPartner", back_populates="purchase_orders", lazy="selectin")
    line_items = db.relationship("POLineItem", back_populates="po", cascade="all, delete-orphan", lazy="selectin")
    invoice = db.relationship("SupplierInvoice", back_populates="po", uselist=False, lazy="selectin")


class POLineItem(db.Model):
    __tablename__ = "po_line_items"

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Numeric(14, 2), nullable=False)
    unit_price = db.Column(db.Numeric(14, 4), nullable=False)

    po = db.relationship("PurchaseOrder", back_populates="line_items", lazy="selectin")
    product = db.relationship("Product", lazy="selectin")

    @property
    def line_total(self):
        return self.quantity * self.unit_price
