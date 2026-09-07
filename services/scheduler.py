from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

_scheduler: BackgroundScheduler | None = None


def start_scheduler(app):
    global _scheduler
    if _scheduler:
        return _scheduler

    scheduler = BackgroundScheduler(timezone=app.config["TIMEZONE"])
    scheduler.add_job(
        func=lambda: run_weekly_purchasing_metrics(app),
        trigger="cron",
        day_of_week="mon",
        hour=8,
        minute=0,
        id="weekly_purchasing_metrics",
        replace_existing=True,
    )
    scheduler.add_job(
        func=lambda: run_monthly_ledger_metrics(app),
        trigger="cron",
        day="1",
        hour=1,
        minute=0,
        id="monthly_ledger_metrics",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    app.logger.info("Background scheduler started.")
    return scheduler


def run_weekly_purchasing_metrics(app):
    from modules.purchasing.models import PurchaseOrder, PurchaseRequisition

    with app.app_context():
        metrics = {
            "requisitions": PurchaseRequisition.query.count(),
            "purchase_orders": PurchaseOrder.query.count(),
            "confirmed_orders": PurchaseOrder.query.filter(PurchaseOrder.status.in_(["Confirmed", "Received"])).count(),
        }
        app.logger.info("Weekly purchasing metrics: %s", metrics)


def run_monthly_ledger_metrics(app):
    from modules.accounting.models import SupplierInvoice

    with app.app_context():
        metrics = {
            "open_invoices": SupplierInvoice.query.filter(SupplierInvoice.state != "Settled").count(),
            "total_invoices": SupplierInvoice.query.count(),
        }
        app.logger.info("Monthly ledger metrics: %s", metrics)
