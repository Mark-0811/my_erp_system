from flask import Blueprint

accounting_bp = Blueprint("accounting", __name__, url_prefix="/accounting")

from modules.accounting import routes  # noqa: E402,F401
