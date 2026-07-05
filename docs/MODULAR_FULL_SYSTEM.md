# Modular and full-system operation

This project is one secondary-school product, not separate academic and full-system forks. Every Django app remains installed and migrated. `SchoolModule` records decide which areas a school may see and use at runtime.

## Presets

The safe default for an existing installation with no module records is **Academic only**. This preserves the original client package after the new migration is deployed.

```bash
# Existing academic-only customer
python manage.py configure_modules academic

# Customer buying the complete platform
python manage.py configure_modules full
python manage.py sync_staff_accounts
```

Super administrators, headteachers and directors of studies can select a custom combination from **Management → Modules & plan**. Saving a configuration takes effect immediately. Navigation is updated and middleware blocks direct web and API paths for disabled modules.

`sync_staff_accounts` creates staff profiles for existing teachers, the headteacher, DOS, bursar and administrators without changing their login credentials. Complete their employment and bank details afterward in Staff management.

## Module catalogue

Academic modules are academic structure, students and admissions, assessment and CBC, examinations and UNEB, attendance, timetables, communication, and reports and analytics.

The full-system additions are:

- **Staff management:** employment and contact profiles, departments, portal account links, payment details and documents.
- **Fees and billing:** reusable fee items, class/stream structures, bulk invoice generation from academic enrolments, individual charges and adjustments, payments, reversals, balances and receipts. Parents and students see only their linked accounts.
- **Institutional finance:** categories, vendors, bank accounts, budgets and department allocations, other income, controlled expenditure approval and payment, bank transaction and reconciliation records. Fee collections are read directly from the fee ledger and are not duplicated as other income.

Global search follows both enabled modules and the signed-in user's data scope.

## Production rollout with Neon

Deploy the code first, then apply migrations from a trusted machine using the Neon direct connection URL (not from a Vercel request):

```bash
export DATABASE_URL='postgresql://...direct-neon-url...?sslmode=require'
python manage.py migrate
python manage.py configure_modules academic   # preserve the current client package
python manage.py check
python manage.py check_school_readiness --production
```

For a full-system customer, use `configure_modules full`, then configure fee items, a published fee structure, expense categories, bank accounts and an open budget before enforcing `--fail-on-warnings`.

Never commit Neon credentials or customer secrets. Vercel's filesystem is ephemeral, so uploaded staff documents, photos, payment evidence and expenditure attachments require persistent private object storage before production use.

## Permission boundaries

- Headteacher and super administrator approve or reject expenditure.
- Bursar records collections, income and paid expenditure but cannot approve a pending request.
- Academic managers configure modules and staff.
- Parents and students can view only invoices associated with linked learner records.
- Payment reversal preserves the receipt record and audit trail instead of deleting money history.

## Verification

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py check
python manage.py test
```
