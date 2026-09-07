from __future__ import annotations

from datetime import datetime

from core import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    uom = db.Column(db.String(50), nullable=False)
    current_stock = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    average_cost = db.Column(db.Numeric(14, 4), default=0, nullable=False)
    tag_kind = db.Column(db.String(30), default="purchase", nullable=False)
    assigned_partner_id = db.Column(db.Integer, db.ForeignKey("business_partners.id"), nullable=True)

    stock_moves = db.relationship("StockMove", back_populates="product", cascade="all, delete-orphan", lazy="selectin")
    assigned_partner = db.relationship("BusinessPartner", back_populates="inventory_items", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Product {self.sku}>"


class StockMove(db.Model):
    __tablename__ = "stock_moves"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Numeric(14, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(14, 4), nullable=False)
    source_document = db.Column(db.String(80), nullable=False)
    move_type = db.Column(db.String(40), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    product = db.relationship("Product", back_populates="stock_moves")

    def __repr__(self) -> str:
        return f"<StockMove {self.move_type} {self.source_document}>"
