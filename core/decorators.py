from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def permission_required(permission_name: str):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.has_permission(permission_name):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def any_permission_required(*permission_names: str):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not any(current_user.has_permission(permission_name) for permission_name in permission_names):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
