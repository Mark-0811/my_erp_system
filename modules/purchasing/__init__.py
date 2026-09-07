from flask import Blueprint

purchasing_bp = Blueprint("purchasing", __name__, url_prefix="/purchasing")

from modules.purchasing import routes  # noqa: E402,F401
