from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from config.models import BaseModel


class ExpenseCategory(BaseModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Vendor(BaseModel):
    name = models.CharField(max_length=150, unique=True)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    tax_number = models.CharField("TIN", max_length=40, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class BankAccount(BaseModel):
    name = models.CharField(max_length=120)
    bank_name = models.CharField(max_length=120)
    account_name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=60, unique=True)
    currency = models.CharField(max_length=8, default="UGX")
    opening_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["bank_name", "name"]

    @property
    def current_balance(self):
        credits = self.transactions.filter(is_deleted=False, transaction_type="credit").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        debits = self.transactions.filter(is_deleted=False, transaction_type="debit").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        return self.opening_balance + credits - debits

    def __str__(self):
        return f"{self.name} · {self.bank_name}"


class Budget(BaseModel):
    STATUSES = [("draft", "Draft"), ("open", "Open"), ("closed", "Closed")]
    name = models.CharField(max_length=140)
    academic_year = models.ForeignKey("academics.AcademicYear", related_name="budgets", on_delete=models.PROTECT)
    term = models.ForeignKey("academics.Term", related_name="budgets", on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUSES, default="draft")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.User", related_name="created_budgets", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-academic_year__start_date", "name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "academic_year"], condition=Q(term__isnull=True), name="unique_annual_finance_budget"),
            models.UniqueConstraint(fields=["name", "academic_year", "term"], condition=Q(term__isnull=False), name="unique_term_finance_budget"),
        ]

    def clean(self):
        if self.term_id and self.term.academic_year_id != self.academic_year_id:
            raise ValidationError({"term": "The selected term must belong to this academic year."})

    @property
    def allocated_amount(self):
        return self.lines.filter(is_deleted=False).aggregate(total=Sum("allocated_amount"))["total"] or Decimal("0.00")

    @property
    def spent_amount(self):
        totals = Expenditure.objects.filter(budget_line__budget=self, is_deleted=False, status__in=("approved", "paid")).aggregate(net=Sum("amount"), vat=Sum("vat_amount"))
        return (totals["net"] or Decimal("0.00")) + (totals["vat"] or Decimal("0.00"))

    @property
    def remaining_amount(self):
        return self.allocated_amount - self.spent_amount

    def __str__(self):
        return self.name


class BudgetLine(BaseModel):
    budget = models.ForeignKey(Budget, related_name="lines", on_delete=models.CASCADE)
    department = models.ForeignKey("academics.Department", related_name="budget_lines", on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(ExpenseCategory, related_name="budget_lines", on_delete=models.PROTECT)
    description = models.CharField(max_length=180, blank=True)
    allocated_amount = models.DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        ordering = ["department__name", "category__name"]
        constraints = [
            models.UniqueConstraint(fields=["budget", "category"], condition=Q(department__isnull=True), name="unique_general_budget_category"),
            models.UniqueConstraint(fields=["budget", "department", "category"], condition=Q(department__isnull=False), name="unique_department_budget_category"),
        ]

    @property
    def spent_amount(self):
        totals = self.expenditures.filter(is_deleted=False, status__in=("approved", "paid")).aggregate(net=Sum("amount"), vat=Sum("vat_amount"))
        return (totals["net"] or Decimal("0.00")) + (totals["vat"] or Decimal("0.00"))

    @property
    def remaining_amount(self):
        return self.allocated_amount - self.spent_amount

    def __str__(self):
        return f"{self.department or 'General'} · {self.category}"


class Expenditure(BaseModel):
    STATUSES = [
        ("draft", "Draft"), ("pending", "Pending approval"), ("approved", "Approved"),
        ("rejected", "Rejected"), ("paid", "Paid"), ("cancelled", "Cancelled"),
    ]
    reference = models.CharField(max_length=32, unique=True, blank=True)
    budget_line = models.ForeignKey(BudgetLine, related_name="expenditures", on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(ExpenseCategory, related_name="expenditures", on_delete=models.PROTECT)
    vendor = models.ForeignKey(Vendor, related_name="expenditures", on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    date_incurred = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=16, choices=STATUSES, default="draft")
    payment_method = models.CharField(max_length=20, choices=[("cash", "Cash"), ("bank", "Bank"), ("mobile_money", "Mobile money"), ("cheque", "Cheque"), ("other", "Other")], blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    attachment = models.FileField(upload_to="finance/expenditures/%Y/", null=True, blank=True)
    requested_by = models.ForeignKey("accounts.User", related_name="requested_expenditures", on_delete=models.SET_NULL, null=True, blank=True)
    approved_by = models.ForeignKey("accounts.User", related_name="approved_expenditures", on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_incurred", "-id"]
        indexes = [models.Index(fields=["reference"]), models.Index(fields=["status", "date_incurred"])]

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero."})
        if self.vat_amount is not None and self.vat_amount < 0:
            raise ValidationError({"vat_amount": "VAT cannot be negative."})
        if self.budget_line_id and self.budget_line.category_id != self.category_id:
            raise ValidationError({"budget_line": "The budget line category must match the expenditure category."})

    def save(self, *args, **kwargs):
        if not self.reference:
            year = (self.date_incurred or timezone.localdate()).year
            prefix = f"EXP-{year}-"
            latest = Expenditure.objects.filter(reference__startswith=prefix).order_by("reference").last()
            try:
                sequence = int(latest.reference.removeprefix(prefix)) + 1 if latest else 1
            except (AttributeError, ValueError):
                sequence = Expenditure.objects.filter(reference__startswith=prefix).count() + 1
            self.reference = f"{prefix}{sequence:06d}"
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def gross_amount(self):
        return self.amount + self.vat_amount

    def __str__(self):
        return f"{self.reference} · {self.description[:60]}"


class IncomeSource(BaseModel):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Income(BaseModel):
    reference = models.CharField(max_length=32, unique=True, blank=True)
    source = models.ForeignKey(IncomeSource, related_name="income_entries", on_delete=models.PROTECT)
    description = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    date_received = models.DateField(default=timezone.localdate)
    external_reference = models.CharField(max_length=100, blank=True)
    bank_account = models.ForeignKey(BankAccount, related_name="income_entries", on_delete=models.SET_NULL, null=True, blank=True)
    received_by = models.ForeignKey("accounts.User", related_name="recorded_income", on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_received", "-id"]

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero."})

    def save(self, *args, **kwargs):
        if not self.reference:
            year = (self.date_received or timezone.localdate()).year
            prefix = f"INC-{year}-"
            latest = Income.objects.filter(reference__startswith=prefix).order_by("reference").last()
            try:
                sequence = int(latest.reference.removeprefix(prefix)) + 1 if latest else 1
            except (AttributeError, ValueError):
                sequence = Income.objects.filter(reference__startswith=prefix).count() + 1
            self.reference = f"{prefix}{sequence:06d}"
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} · {self.description}"


class BankTransaction(BaseModel):
    bank_account = models.ForeignKey(BankAccount, related_name="transactions", on_delete=models.PROTECT)
    transaction_date = models.DateField(default=timezone.localdate)
    transaction_type = models.CharField(max_length=8, choices=[("credit", "Credit"), ("debit", "Debit")])
    description = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True)
    fee_payment = models.ForeignKey("fees.Payment", related_name="bank_transactions", on_delete=models.SET_NULL, null=True, blank=True)
    income = models.ForeignKey(Income, related_name="bank_transactions", on_delete=models.SET_NULL, null=True, blank=True)
    expenditure = models.ForeignKey(Expenditure, related_name="bank_transactions", on_delete=models.SET_NULL, null=True, blank=True)
    is_reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-transaction_date", "-id"]

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero."})

    def __str__(self):
        return f"{self.transaction_date} · {self.description}"
