from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from werkzeug.security import generate_password_hash

from core import db
from core.decorators import any_permission_required
from core.models import CompanySetting, Permission, Role, User
from modules.admin import admin_bp


def _admin_flags() -> dict[str, bool]:
    return {
        "can_manage_users": current_user.has_permission("admin:manage_users") or current_user.has_permission("admin:settings"),
        "can_manage_roles": current_user.has_permission("admin:manage_roles") or current_user.has_permission("admin:settings"),
        "can_view_permissions": current_user.has_permission("admin:view_permissions") or current_user.has_permission("admin:settings"),
    }


@admin_bp.route("/settings", methods=["GET", "POST"])
@any_permission_required("admin:settings")
def settings():
    company_setting = CompanySetting.get_solo()

    if request.method == "POST":
        company_setting.company_name = request.form.get("company_name", company_setting.company_name).strip() or company_setting.company_name
        company_setting.acronym = request.form.get("acronym", company_setting.acronym).strip().upper() or company_setting.acronym
        db.session.commit()
        flash("Company settings updated.", "success")
        return redirect(url_for("admin.settings"))

    return render_template(
        "admin/settings.html",
        company_setting=company_setting,
        **_admin_flags(),
    )


@admin_bp.route("/users", methods=["GET", "POST"])
@any_permission_required("admin:manage_users", "admin:settings")
def users():
    user_search = request.args.get("user_search", "").strip()
    all_roles = Role.query.order_by(Role.name.asc()).all()
    user_query = User.query
    if user_search:
        like = f"%{user_search}%"
        user_query = user_query.filter((User.full_name.ilike(like)) | (User.email.ilike(like)))
    users = user_query.order_by(User.full_name.asc()).all()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_user":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()
            if not full_name or not email or not password:
                flash("Full name, email, and password are required to create a user.", "warning")
                return redirect(url_for("admin.users", user_search=user_search))
            if User.query.filter_by(email=email).first():
                flash("A user with that email already exists.", "warning")
                return redirect(url_for("admin.users", user_search=user_search))
            user = User(
                full_name=full_name,
                email=email,
                password_hash=generate_password_hash(password),
                is_active=request.form.get("is_active") == "on",
            )
            role_ids = [int(role_id) for role_id in request.form.getlist("role_ids")]
            user.roles = [role for role in all_roles if role.id in role_ids]
            db.session.add(user)
            db.session.commit()
            flash(f"Created user {user.full_name}.", "success")
        elif action == "update_user":
            user = db.session.get(User, int(request.form["user_id"]))
            if user:
                user.full_name = request.form.get("full_name", user.full_name).strip() or user.full_name
                user.email = request.form.get("email", user.email).strip() or user.email
                user.is_active = request.form.get("is_active") == "on"
                role_ids = [int(role_id) for role_id in request.form.getlist("role_ids")]
                user.roles = [role for role in all_roles if role.id in role_ids]
                db.session.commit()
                flash(f"Updated access for {user.full_name}.", "success")
        return redirect(url_for("admin.users", user_search=user_search))

    return render_template(
        "admin/users.html",
        users=users,
        all_roles=all_roles,
        user_search=user_search,
        **_admin_flags(),
    )


@admin_bp.route("/roles", methods=["GET", "POST"])
@any_permission_required("admin:manage_roles", "admin:view_permissions", "admin:settings")
def roles():
    role_search = request.args.get("role_search", "").strip()
    permission_search = request.args.get("permission_search", "").strip()

    role_query = Role.query
    permission_query = Permission.query
    if role_search:
        role_query = role_query.filter(Role.name.ilike(f"%{role_search}%"))
    if permission_search:
        permission_query = permission_query.filter(Permission.name.ilike(f"%{permission_search}%"))

    roles = role_query.order_by(Role.name.asc()).all()
    permissions = permission_query.order_by(Permission.name.asc()).all()
    all_permissions = Permission.query.order_by(Permission.name.asc()).all()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_role":
            role_name = request.form.get("role_name", "").strip()
            if not role_name:
                flash("Role name is required.", "warning")
            elif Role.query.filter_by(name=role_name).first():
                flash("That role already exists.", "warning")
            else:
                db.session.add(Role(name=role_name))
                db.session.commit()
                flash(f"Created role {role_name}.", "success")
        elif action == "update_role":
            role = db.session.get(Role, int(request.form["role_id"]))
            if role:
                role.name = request.form.get("name", role.name).strip() or role.name
                permission_ids = [int(permission_id) for permission_id in request.form.getlist("permission_ids")]
                role.permissions = [permission for permission in all_permissions if permission.id in permission_ids]
                db.session.commit()
                flash(f"Updated permissions for {role.name}.", "success")
        return redirect(url_for("admin.roles", role_search=role_search, permission_search=permission_search))

    return render_template(
        "admin/roles.html",
        roles=roles,
        permissions=permissions,
        all_permissions=all_permissions,
        role_search=role_search,
        permission_search=permission_search,
        **_admin_flags(),
    )
