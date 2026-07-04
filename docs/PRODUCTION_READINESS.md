# Production readiness

The application is ready for a controlled school pilot only after the readiness command passes and the school signs the acceptance checklist.

## Required gate

Run these commands against a production-like copy of the school data:

```bash
python manage.py check --deploy
python manage.py check_school_readiness --production --fail-on-warnings
python manage.py test
python manage.py makemigrations --check --dry-run
```

Before a UNEB preparation export, also run:

```bash
python manage.py check_school_readiness \
  --academic-year 2026 \
  --uneb-level uce \
  --uneb-year 2026
```

The UNEB workbook is a pre-submission aid. An authorised examinations officer must compare it with the current UNEB circular and upload template and submit through UNEB's authorised channel.

## Curriculum data

The school must obtain authorised NCDC curriculum source files and import every offered subject, class and term from **Curriculum & outcomes → Import curriculum**. The import is atomic, updates matching coded records and rejects unknown generic skills or values. `check_school_readiness` fails when an active teaching allocation has no imported topic with a learning outcome.

Do not copy or redistribute complete NCDC syllabus text without confirming the school's permission to do so. Preserve the source title, version and implementation year on the curriculum framework.

## Hosting and privacy

- Use PostgreSQL, HTTPS, a strong secrets-managed `SECRET_KEY`, restrictive `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
- Restrict database, media, log and backup access to authorised operators. Learner profiles, medical notes, photographs, marks and evidence files are sensitive records.
- Give every person an individual account. Do not share teacher or management passwords.
- Remove demonstration accounts and data; require password changes for initial accounts.
- Review academic-manager privileges at the start and end of every term.
- Configure central logs and alerts without logging marks, medical information, passwords or authentication tokens.
- Document retention periods and an approved process for access, correction, export and deletion requests.
- Test incident response, account suspension and backup restoration before go-live.

## Backup gate

Run `scripts/backup_production.sh` daily from a protected host and copy backups to encrypted off-site storage. Run `scripts/verify_backup.sh BACKUP_DIRECTORY` after each backup. Perform a quarterly restoration drill into an isolated database and record the recovery time and evidence.
