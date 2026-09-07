from flask import Response, flash, redirect, render_template, request, url_for
from core import db

from core.decorators import permission_required
from modules.accounting import accounting_bp
from modules.accounting.models import DocumentPrintLayout, SupplierInvoice
from services.pdf_generator import render_html_to_pdf


@accounting_bp.route("/")
@permission_required("accounting:view")
def dashboard():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    invoice_query = SupplierInvoice.query
    if search:
        like = f"%{search}%"
        invoice_query = invoice_query.filter(
            (SupplierInvoice.invoice_ref.ilike(like))
            | (SupplierInvoice.state.ilike(like))
        )
    if status:
        invoice_query = invoice_query.filter(SupplierInvoice.state == status)
    invoices = invoice_query.order_by(SupplierInvoice.created_at.desc()).all()
    layouts = DocumentPrintLayout.query.order_by(DocumentPrintLayout.target_type.asc()).all()
    return render_template("accounting/dashboard.html", invoices=invoices, layouts=layouts, search=search, status=status)


@accounting_bp.route("/invoices/<int:invoice_id>", methods=["GET", "POST"])
@permission_required("accounting:view")
def invoice_detail(invoice_id: int):
    invoice = SupplierInvoice.query.get_or_404(invoice_id)
    layout = DocumentPrintLayout.query.filter_by(target_type="INVOICE").first()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "mark_paid":
            invoice.state = "Settled"
            flash(f"{invoice.invoice_ref} marked as paid.", "success")
        elif action == "mark_unpaid":
            invoice.state = "Unpaid"
            flash(f"{invoice.invoice_ref} marked as unpaid.", "info")
        db.session.commit()
        return redirect(url_for("accounting.invoice_detail", invoice_id=invoice.id))
    return render_template("documents/invoice.html", invoice=invoice, layout=layout)


@accounting_bp.route("/invoices/<int:invoice_id>/receipt", methods=["GET"])
@permission_required("accounting:view")
def receipt_detail(invoice_id: int):
    invoice = SupplierInvoice.query.get_or_404(invoice_id)
    layout = DocumentPrintLayout.query.filter_by(target_type="INVOICE").first()
    return render_template("documents/receipt.html", invoice=invoice, layout=layout)


@accounting_bp.route("/invoices/<int:invoice_id>/print")
@permission_required("accounting:view")
def print_invoice(invoice_id: int):
    invoice = SupplierInvoice.query.get_or_404(invoice_id)
    layout = DocumentPrintLayout.query.filter_by(target_type="INVOICE").first()
    html = render_template("documents/invoice.html", invoice=invoice, layout=layout)
    if request.args.get("format", "pdf") == "html":
        return html
    try:
        pdf_bytes = render_html_to_pdf(html, base_url=request.url_root)
    except RuntimeError:
        return html
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_ref}.pdf"'},
    )


@accounting_bp.route("/invoices/<int:invoice_id>/receipt/print")
@permission_required("accounting:view")
def print_receipt(invoice_id: int):
    invoice = SupplierInvoice.query.get_or_404(invoice_id)
    layout = DocumentPrintLayout.query.filter_by(target_type="INVOICE").first()
    html = render_template("documents/receipt.html", invoice=invoice, layout=layout)
    if request.args.get("format", "pdf") == "html":
        return html
    try:
        pdf_bytes = render_html_to_pdf(html, base_url=request.url_root)
    except RuntimeError:
        return html
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_ref}-receipt.pdf"'},
    )
