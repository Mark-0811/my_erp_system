# My ERP System

A modular Flask ERP starter built on the Mazer vertical navbar layout.

## Run

```bash
cd my_erp_system
pip install -r requirements.txt
python run.py
```

## Docker

```bash
docker compose up --build
```

## Demo users

The development seed creates sample users. Set or reset passwords locally instead of
committing credentials to the repository.

## Notes

- SQLite is used by default for quick startup.
- Set `DATABASE_URL` to point at PostgreSQL for production.
- The UI pulls Mazer assets from the official CDN references used by the template demo.
- Purchasing now includes business partner classifications for supplier/customer and local/private scope.
- Admin users can manage users, roles, and permissions from `/admin/settings`.
- Logged-in users can edit their profile from `/profile`.
- PDF export uses WeasyPrint when installed.
