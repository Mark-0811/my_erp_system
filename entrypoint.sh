#!/bin/sh
set -e

python - <<'PY'
import os
import time

from sqlalchemy import create_engine, text

from run import app
from core import initialize_database

db_url = os.environ.get("DATABASE_URL")
if db_url:
    engine = create_engine(db_url, pool_pre_ping=True)
    for attempt in range(60):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except Exception:
            time.sleep(2)
    else:
        raise SystemExit("Database is not ready after waiting.")

initialize_database(app)
PY

exec gunicorn --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-2}" --threads "${GUNICORN_THREADS:-4}" --timeout "${GUNICORN_TIMEOUT:-120}" "run:app"
