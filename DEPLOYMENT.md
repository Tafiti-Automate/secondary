# Production deployment

## Vercel with Neon PostgreSQL

SQLite cannot be used by this application on Vercel because the deployed
application filesystem is read-only and ephemeral. Create or select a Neon
project, open **Connect**, enable **Connection pooling**, and copy the connection
URL.

Add these variables in **Vercel → Project → Settings → Environment Variables**
for Production (and Preview if previews should use the database):

```text
DATABASE_URL=postgresql://...-pooler.../neondb?sslmode=require&channel_binding=require
SECRET_KEY=<a-long-random-secret>
DEBUG=False
```

Use Neon's direct, non-pooler connection URL to apply schema migrations from a
trusted local or CI environment:

```bash
export DATABASE_URL='postgresql://.../neondb?sslmode=require&channel_binding=require'
python manage.py migrate
python manage.py createsuperuser
```

Do not commit either Neon connection URL. Redeploy the Vercel project after
adding or changing its environment variables.

## PostgreSQL and application settings

Copy `.env.example` to a secrets-managed environment and replace every placeholder. Production startup fails operationally if PostgreSQL or secrets are unavailable; do not use the local SQLite database.

```bash
export SECRET_KEY='a-long-random-value'
export DEBUG=False
export ALLOWED_HOSTS='school.example.ug'
export CSRF_TRUSTED_ORIGINS='https://school.example.ug'
export DB_ENGINE=postgresql
export DB_NAME=school_academics
export DB_USER=school_app
export DB_PASSWORD='strong-database-password'
export DB_HOST=db
export DB_PORT=5432
export DB_SSLMODE=require
```

Then run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
```

Terminate TLS at a trusted reverse proxy or load balancer. Set `SECURE_SSL_REDIRECT=True`, secure cookie settings, and a non-zero HSTS duration only after HTTPS works on every subdomain.

## Containers

```bash
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Persist PostgreSQL and `/app/media`, back both up daily, and test restoration regularly. Uploaded learner photographs and academic attachments contain sensitive information and require private storage controls.

## Before go-live

- Replace all demonstration passwords and do not run `seed_data.py` in production.
- Configure outbound email and the approved SMS/WhatsApp provider for the school.
- Run `python manage.py process_notifications --retry-failed` from a scheduled worker when using queued provider delivery.
- Put Redis or another shared backend behind `CACHES` when running multiple workers.
- Configure centralized logs, uptime monitoring and database/storage backups.
- Import the school-authorised NCDC curriculum files for every offered subject/class/term.
- Run `python manage.py check_school_readiness --production --fail-on-warnings` and resolve every finding.
- Run `python manage.py check --deploy`, the full test suite, and a restore drill.
- Before a UNEB workbook, run `python manage.py check_school_readiness --uneb-level uce --uneb-year YYYY`.
- Train the academic office on term closing, exam approval, report publication and result locking.

The operational security, backup and acceptance gates are detailed in
`docs/PRODUCTION_READINESS.md` and `docs/SCHOOL_ACCEPTANCE_CHECKLIST.md`.
