from __future__ import annotations

from datetime import date, datetime

from core import db


class SupplierInvoice(db.Model):
    __tablename__ = "supplier_invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_ref = db.Column(db.String(80), unique=True, nullable=False, index=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=True)
    issue_date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date, nullable=False, default=date.today)
    amount_total = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    state = db.Column(db.String(30), default="Unpaid", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    po = db.relationship("PurchaseOrder", back_populates="invoice", lazy="selectin")


class DocumentPrintLayout(db.Model):
    __tablename__ = "document_print_layouts"

    id = db.Column(db.Integer, primary_key=True)
    target_type = db.Column(db.String(50), unique=True, nullable=False)
    header_html = db.Column(db.Text, nullable=False)
    footer_text = db.Column(db.Text, nullable=False)
    custom_css = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class JournalEntry(db.Model):
    __tablename__ = "journal_entries"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(80), nullable=False, index=True)
    narration = db.Column(db.String(255), nullable=False)
    debit = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    credit = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
