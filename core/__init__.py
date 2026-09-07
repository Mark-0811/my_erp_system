from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

from flask import Flask, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import (
    AnonymousUserMixin,
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from sqlalchemy.orm import selectinload
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()
login_manager = LoginManager()

BASE_DIR = Path(__file__).resolve().parent.parent


class AnonymousERPUser(AnonymousUserMixin):
    def has_permission(self, permission_name: str) -> bool:
        return False


login_manager.login_view = "login"
login_manager.login_message_category = "info"
login_manager.anonymous_user = AnonymousERPUser


class BaseConfig:
    APP_NAME = "Inventory System"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'erp.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    AUTO_CREATE_DB = os.getenv("AUTO_CREATE_DB", "true").lower() in {"1", "true", "yes", "on"}
    ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "false").lower() in {"1", "true", "yes", "on"}
    TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Singapore")
    ASSET_VERSION = os.getenv("ASSET_VERSION", datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AUTO_CREATE_DB = True


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


NAV_ITEMS = [
    {"label": "Procurement Home", "endpoint": "dashboard", "icon": "bi-speedometer2", "permission": None},
    {"label": "Purchase Requests", "endpoint": "purchasing.dashboard", "icon": "bi-receipt", "permission": "purchasing:view"},
    {"label": "Purchase Orders", "endpoint": "purchasing.purchase_orders", "icon": "bi-bag-check", "permission": "purchasing:approve"},
    {"label": "Products", "endpoint": "inventory.products", "icon": "bi-box-seam", "permission": "inventory:view"},
    {"label": "Suppliers", "endpoint": "purchasing.suppliers", "icon": "bi-truck", "permission": "purchasing:view"},
    {"label": "Clients", "endpoint": "purchasing.clients", "icon": "bi-people", "permission": "purchasing:view"},
    {"label": "Receiving", "endpoint": "inventory.dashboard", "icon": "bi-box-seam", "permission": "inventory:view"},
    {"label": "Supplier Bills", "endpoint": "accounting.dashboard", "icon": "bi-journal-text", "permission": "accounting:view"},
    {"label": "Company Settings", "endpoint": "admin.settings", "icon": "bi-gear", "permission": "admin:settings"},
    {"label": "Users", "endpoint": "admin.users", "icon": "bi-people-fill", "permission": "admin:manage_users"},
    {"label": "Roles & Permissions", "endpoint": "admin.roles", "icon": "bi-shield-lock-fill", "permission": "admin:manage_roles"},
]

SIDEBAR_GROUPS = [
    {
        "title": "General",
        "items": [
            NAV_ITEMS[0],
        ],
    },
    {
        "title": "Operations",
        "items": [
            NAV_ITEMS[1],
            NAV_ITEMS[2],
            NAV_ITEMS[3],
            NAV_ITEMS[6],
            NAV_ITEMS[7],
        ],
    },
    {
        "title": "Administration",
        "items": [
            NAV_ITEMS[4],
            NAV_ITEMS[5],
            NAV_ITEMS[8],
            NAV_ITEMS[9],
            NAV_ITEMS[10],
        ],
    },
]

APP_LAUNCHER = [
    {"label": "Products", "endpoint": "inventory.products", "icon": "bi-box-seam", "permission": "inventory:view", "color": "bg-light-warning"},
    {"label": "Purchase Requests", "endpoint": "purchasing.dashboard", "icon": "bi-receipt", "permission": "purchasing:view", "color": "bg-light-success"},
    {"label": "Purchase Orders", "endpoint": "purchasing.purchase_orders", "icon": "bi-bag-check", "permission": "purchasing:approve", "color": "bg-light-primary"},
    {"label": "Suppliers", "endpoint": "purchasing.suppliers", "icon": "bi-truck", "permission": "purchasing:view", "color": "bg-light-primary"},
    {"label": "Clients", "endpoint": "purchasing.clients", "icon": "bi-people", "permission": "purchasing:view", "color": "bg-light-danger"},
    {"label": "Receiving", "endpoint": "inventory.dashboard", "icon": "bi-box-seam", "permission": "inventory:view", "color": "bg-light-primary"},
    {"label": "Supplier Bills", "endpoint": "accounting.dashboard", "icon": "bi-journal-text", "permission": "accounting:view", "color": "bg-light-secondary"},
    {"label": "Settings", "endpoint": "admin.settings", "icon": "bi-gear", "permission": "admin:settings", "color": "bg-light-danger"},
]


def _get_config(config_name: str | None) -> type[BaseConfig]:
    selected = (config_name or os.getenv("FLASK_CONFIG") or "development").lower()
    return CONFIG_MAP.get(selected, DevelopmentConfig)


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_object(_get_config(config_name))

    db.init_app(app)
    login_manager.init_app(app)

    from modules.accounting import accounting_bp
    from modules.admin import admin_bp
    from modules.inventory import inventory_bp
    from modules.purchasing import purchasing_bp

    app.register_blueprint(inventory_bp)
    app.register_blueprint(purchasing_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(admin_bp)

    from core.models import CompanySetting, Permission, Role, User
    from modules.accounting.models import DocumentPrintLayout, SupplierInvoice
    from modules.inventory.models import Product, StockMove
    from modules.purchasing.models import BusinessPartner, POLineItem, PurchaseOrder, PurchaseRequisition, PurchaseRequisitionLineItem, Vendor

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        company_setting = CompanySetting.get_solo()
        return {
            "app_name": app.config["APP_NAME"],
            "nav_items": NAV_ITEMS,
            "sidebar_groups": SIDEBAR_GROUPS,
            "app_launcher": APP_LAUNCHER,
            "company_setting": company_setting,
            "company_acronym": company_setting.acronym,
            "current_year": date.today().year,
        }

    @app.errorhandler(403)
    def forbidden(_exc):
        return render_template("error.html", title="Forbidden", message="You do not have access to this page."), 403

    @app.errorhandler(404)
    def not_found(_exc):
        return render_template("error.html", title="Not found", message="The page you requested does not exist."), 404

    @app.route("/")
    @login_required
    def dashboard():
        stats = {
            "products": Product.query.count(),
            "stock_moves": StockMove.query.count(),
            "purchase_requests": PurchaseRequisition.query.count(),
            "purchase_orders": PurchaseOrder.query.count(),
            "supplier_bills": SupplierInvoice.query.count(),
            "suppliers": Vendor.query.count(),
        }
        recent_orders = (
            PurchaseOrder.query.options(selectinload(PurchaseOrder.line_items))
            .order_by(PurchaseOrder.created_at.desc())
            .limit(5)
            .all()
        )
        recent_invoices = SupplierInvoice.query.order_by(SupplierInvoice.created_at.desc()).limit(5).all()
        return render_template(
            "dashboard.html",
            stats=stats,
            recent_orders=recent_orders,
            recent_invoices=recent_invoices,
        )

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            identifier = request.form.get("identifier", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter(
                (User.email == identifier) | (User.full_name == identifier)
            ).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                flash(f"Welcome back, {user.full_name}.", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid email/name or password.", "danger")

        return render_template("login.html")

    @app.route("/reset-password", methods=["GET", "POST"])
    def reset_password():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            identifier = request.form.get("identifier", "").strip()
            new_password = request.form.get("new_password", "").strip()
            confirm_password = request.form.get("confirm_password", "").strip()

            if not identifier or not new_password or not confirm_password:
                flash("Identifier, new password, and confirmation are required.", "warning")
                return redirect(url_for("reset_password"))
            if new_password != confirm_password:
                flash("Passwords do not match.", "danger")
                return redirect(url_for("reset_password"))
            if len(new_password) < 6:
                flash("Please choose a password with at least 6 characters.", "warning")
                return redirect(url_for("reset_password"))

            user = User.query.filter(
                (User.email.ilike(identifier)) | (User.full_name.ilike(identifier))
            ).first()
            if not user:
                flash("We could not find a matching account.", "warning")
                return redirect(url_for("reset_password"))

            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash("Password updated. You can now sign in with the new password.", "success")
            return redirect(url_for("login"))

        return render_template("reset_password.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been signed out.", "info")
        return redirect(url_for("login"))

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            current_user.full_name = request.form.get("full_name", current_user.full_name).strip() or current_user.full_name
            current_user.email = request.form.get("email", current_user.email).strip() or current_user.email
            new_password = request.form.get("new_password", "").strip()
            confirm_password = request.form.get("confirm_password", "").strip()
            if new_password:
                if new_password != confirm_password:
                    flash("Passwords do not match.", "danger")
                    return redirect(url_for("profile"))
                current_user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))

        return render_template("profile.html")

    @app.route("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
        return {"status": "ok" if db_ok else "degraded", "app": app.config["APP_NAME"], "database": db_ok}

    if app.config["ENABLE_SCHEDULER"]:
        from services.scheduler import start_scheduler

        start_scheduler(app)

    return app


def initialize_database(app: Flask) -> None:
    if not app.config["AUTO_CREATE_DB"]:
        return

    with app.app_context():
        from core.models import User

        db.create_all()
        _sync_schema()
        _backfill_demo_partners()
        if not db.session.query(User.id).first():
            seed_demo_data()


def _sync_schema() -> None:
    inspector = inspect(db.engine)
    existing_columns = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in inspector.get_table_names()
    }

    def add_column(table_name: str, column_name: str, column_sql: str) -> None:
        if column_name not in existing_columns.get(table_name, set()):
            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))

    add_column("business_partners", "address", "TEXT")
    add_column("purchase_requisitions", "partner_type", "VARCHAR(20)")
    add_column("purchase_requisitions", "partner_id", "INTEGER")
    add_column("purchase_requisitions", "partner_name_snapshot", "VARCHAR(200)")
    add_column("purchase_requisitions", "partner_address_snapshot", "TEXT")
    db.session.commit()


def _backfill_demo_partners() -> None:
    partner_defaults = {
        "Northwind Trading": {
            "email": "procurement@northwind.example",
            "phone": "+63 2 8123 1111",
            "address": "Northwind Tower, Makati City, Philippines",
            "partner_type": "supplier",
            "scope_type": "local",
        },
        "Continental Private Supply": {
            "email": "orders@continental.example",
            "phone": "+63 2 8333 2222",
            "address": "Continental Industrial Park, Quezon City, Philippines",
            "partner_type": "supplier",
            "scope_type": "private",
        },
        "Metro Retail Group": {
            "email": "buying@metro.example",
            "phone": "+63 2 8444 3333",
            "address": "Metro Retail Center, Pasig City, Philippines",
            "partner_type": "customer",
            "scope_type": "local",
        },
    }
    from modules.purchasing.models import BusinessPartner

    changed = False
    for partner in BusinessPartner.query.all():
        defaults = partner_defaults.get(partner.name)
        if not defaults:
            continue
        for field, value in defaults.items():
            if field == "address":
                if not partner.address:
                    setattr(partner, field, value)
                    changed = True
            elif not getattr(partner, field, None):
                setattr(partner, field, value)
                changed = True
    if changed:
        db.session.commit()


def seed_demo_data() -> None:
    from modules.purchasing.models import PurchaseRequisitionLineItem

    from core.models import CompanySetting, Permission, Role, User
    from modules.accounting.models import DocumentPrintLayout, SupplierInvoice
    from modules.inventory.models import Product, StockMove
    from modules.purchasing.models import BusinessPartner, POLineItem, PurchaseOrder, PurchaseRequisition, Vendor

    permission_names = [
        "inventory:view",
        "inventory:receive",
        "inventory:tag",
        "purchasing:view",
        "purchasing:create",
        "purchasing:approve",
        "purchasing:partner_manage",
        "accounting:view",
        "accounting:post_ledger",
        "accounting:receive_reports",
        "admin:settings",
        "admin:manage_users",
        "admin:manage_roles",
        "admin:view_permissions",
    ]
    permissions = {}
    for name in permission_names:
        permission = Permission.query.filter_by(name=name).first()
        if not permission:
            permission = Permission(name=name)
            db.session.add(permission)
        permissions[name] = permission

    role_specs = {
        "Inventory Clerk": ["inventory:view", "inventory:receive", "inventory:tag"],
        "Purchasing Officer": ["purchasing:view", "purchasing:create", "purchasing:approve", "purchasing:partner_manage"],
        "Financial Controller": ["accounting:view", "accounting:post_ledger", "accounting:receive_reports", "admin:view_permissions"],
        "ERP Administrator": permission_names,
    }

    roles = {}
    for role_name, role_permissions in role_specs.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name)
            db.session.add(role)
        role.permissions = [permissions[name] for name in role_permissions]
        roles[role_name] = role

    demo_users = [
        ("System Admin", "admin@example.com", "admin123", ["ERP Administrator"]),
        ("Inventory Clerk", "inventory@example.com", "inventory123", ["Inventory Clerk"]),
        ("Purchasing Officer", "purchasing@example.com", "purchase123", ["Purchasing Officer"]),
        ("Financial Controller", "finance@example.com", "finance123", ["Financial Controller"]),
    ]
    for full_name, email, password, user_roles in demo_users:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                full_name=full_name,
                email=email,
                password_hash=generate_password_hash(password),
                is_active=True,
            )
            db.session.add(user)
        user.roles = [roles[name] for name in user_roles]

    if not BusinessPartner.query.first():
        supplier_local = BusinessPartner(
            name="Northwind Trading",
            email="procurement@northwind.example",
            phone="+63 2 8123 1111",
            address="Northwind Tower, Makati City, Philippines",
            partner_type="supplier",
            scope_type="local",
        )
        supplier_private = BusinessPartner(
            name="Continental Private Supply",
            email="orders@continental.example",
            phone="+63 2 8333 2222",
            address="Continental Industrial Park, Quezon City, Philippines",
            partner_type="supplier",
            scope_type="private",
        )
        client_local = BusinessPartner(
            name="Metro Retail Group",
            email="buying@metro.example",
            phone="+63 2 8444 3333",
            address="Metro Retail Center, Pasig City, Philippines",
            partner_type="customer",
            scope_type="local",
        )
        db.session.add_all([supplier_local, supplier_private, client_local])
    partners = BusinessPartner.query.order_by(BusinessPartner.id.asc()).all()
    partner_primary = partners[0] if partners else None
    partner_secondary = partners[1] if len(partners) > 1 else partner_primary
    partner_tertiary = partners[2] if len(partners) > 2 else partner_primary

    if not Vendor.query.first():
        vendor = Vendor(name=partner_primary.name if partner_primary else "Northwind Trading", email=partner_primary.email if partner_primary else "procurement@northwind.example")
        db.session.add(vendor)
    else:
        vendor = Vendor.query.first()

    if not Product.query.first():
        product_a = Product(
            sku="SKU-1001",
            name="Industrial Fastener Kit",
            uom="Box",
            current_stock=100,
            average_cost=18.5000,
            tag_kind="purchase",
            assigned_partner=partner_primary,
        )
        product_b = Product(
            sku="SKU-2002",
            name="Heavy Duty Sealant",
            uom="Carton",
            current_stock=20,
            average_cost=42.0000,
            tag_kind="purchase",
            assigned_partner=partner_secondary,
        )
        db.session.add_all([product_a, product_b])
    else:
        products = Product.query.order_by(Product.id.asc()).all()
        product_a = products[0]
        product_b = products[1] if len(products) > 1 else products[0]

    if not PurchaseRequisition.query.first():
        requisition = PurchaseRequisition(
            serial="PR-2026-0001",
            requested_by=User.query.filter_by(email="purchasing@example.com").first(),
            partner_type="supplier",
            partner=partner_primary,
            partner_name_snapshot=partner_primary.name if partner_primary else "Northwind Trading",
            partner_address_snapshot=partner_primary.address if partner_primary else "Northwind Tower, Makati City, Philippines",
            status="Approved",
            total_estimated_cost=1900,
        )
        db.session.add(requisition)
        db.session.flush()
        db.session.add(
            PurchaseRequisitionLineItem(
                requisition=requisition,
                product=product_a,
                product_sku_snapshot=product_a.sku,
                product_name_snapshot=product_a.name,
                uom_snapshot=product_a.uom,
                quantity=40,
                unit_price=19.5,
                notes="Demo line item",
            )
        )
        db.session.add(
            PurchaseRequisitionLineItem(
                requisition=requisition,
                product=product_b,
                product_sku_snapshot=product_b.sku,
                product_name_snapshot=product_b.name,
                uom_snapshot=product_b.uom,
                quantity=10,
                unit_price=44.0,
                notes="Demo line item",
            )
        )
    else:
        requisition = PurchaseRequisition.query.first()

    if not PurchaseOrder.query.first():
        purchase_order = PurchaseOrder(
            serial="PO-2026-0001",
            requisition=requisition,
            vendor_name=vendor.name,
            partner=partner_primary,
            status="Confirmed",
            total_amount=1900,
        )
        db.session.add(purchase_order)
        db.session.flush()
        db.session.add_all(
            [
                POLineItem(po=purchase_order, product=product_a, quantity=40, unit_price=19.5),
                POLineItem(po=purchase_order, product=product_b, quantity=10, unit_price=44.0),
            ]
        )

    company_setting = CompanySetting.query.first()
    if not company_setting:
        db.session.add(CompanySetting(company_name=current_app.config["APP_NAME"], acronym="INV"))
    else:
        if not company_setting.company_name:
            company_setting.company_name = current_app.config["APP_NAME"]
        if not company_setting.acronym:
            company_setting.acronym = "INV"

    if not DocumentPrintLayout.query.filter_by(target_type="INVOICE").first():
        db.session.add(
            DocumentPrintLayout(
                target_type="INVOICE",
                header_html="<h2>Inventory System</h2><p>Enterprise document stream</p>",
                footer_text="Payment due within agreed terms.",
                custom_css="""
                    body { font-family: Arial, sans-serif; color: #111827; }
                    .invoice-shell { max-width: 960px; margin: 0 auto; padding: 24px; }
                    .invoice-header { border-bottom: 2px solid #0f172a; margin-bottom: 24px; padding-bottom: 16px; }
                """,
            )
        )

    db.session.commit()
