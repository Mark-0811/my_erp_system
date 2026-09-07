from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin

from core import db

user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
)

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    roles = db.relationship("Role", secondary=user_roles, back_populates="users", lazy="selectin")

    def has_permission(self, permission_name: str) -> bool:
        return permission_name in self.permission_names

    @property
    def permission_names(self) -> set[str]:
        permissions = set()
        for role in self.roles:
            permissions.update(permission.name for permission in role.permissions)
        return permissions

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Role(TimestampMixin, db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    users = db.relationship("User", secondary=user_roles, back_populates="roles", lazy="selectin")
    permissions = db.relationship("Permission", secondary=role_permissions, back_populates="roles", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class Permission(TimestampMixin, db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False, index=True)
    roles = db.relationship("Role", secondary=role_permissions, back_populates="permissions", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Permission {self.name}>"


class CompanySetting(TimestampMixin, db.Model):
    __tablename__ = "company_settings"

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False, default="Inventory System")
    acronym = db.Column(db.String(20), nullable=False, default="INV")

    @classmethod
    def get_solo(cls) -> "CompanySetting":
        setting = cls.query.order_by(cls.id.asc()).first()
        if not setting:
            setting = cls(company_name="Inventory System", acronym="INV")
            db.session.add(setting)
            db.session.flush()
        return setting
