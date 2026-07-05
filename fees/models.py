from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from config.models import BaseModel


class FeeItem(BaseModel):
    CATEGORIES = [
        ("tuition", "Tuition"), ("boarding", "Boarding"), ("meals", "Meals"),
        ("uniform", "Uniform"), ("transport", "Transport"), ("examination", "Examination"),
        ("activity", "Activity"), ("development", "Development"), ("other", "Other"),
    ]
    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=24, choices=CATEGORIES, default="tuition")
    description = models.TextField(blank=True)
    default_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class FeeStructure(BaseModel):
    STATUSES = [("draft", "Draft"), ("published", "Published"), ("closed", "Closed")]
    name = models.CharField(max_length=140)
    term = models.ForeignKey("academics.Term", related_name="fee_structures", on_delete=models.PROTECT)
    class_level = models.ForeignKey("academics.ClassLevel", related_name="fee_structures", on_delete=models.PROTECT)
    stream = models.ForeignKey("academics.Stream", related_name="fee_structures", on_delete=models.PROTECT, null=True, blank=True, help_text="Leave empty to apply to every stream in this class level.")
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUSES, default="draft")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-term__academic_year__start_date", "class_level__level", "name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "term", "class_level"], condition=Q(stream__isnull=True), name="unique_fee_structure_all_streams"),
            models.UniqueConstraint(fields=["name", "term", "class_level", "stream"], condition=Q(stream__isnull=False), name="unique_fee_structure_stream"),
        ]

    def clean(self):
        if self.stream_id and self.stream.class_level_id != self.class_level_id:
            raise ValidationError({"stream": "The selected stream must belong to this class level."})
        if self.due_date and self.term_id and not self.term.start_date <= self.due_date <= self.term.end_date:
            raise ValidationError({"due_date": "The due date must fall within the selected term."})

    @property
    def total_amount(self):
        return self.items.filter(is_deleted=False).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    def __str__(self):
        return f"{self.name} · {self.class_level} · {self.term}"


class FeeStructureItem(BaseModel):
    structure = models.ForeignKey(FeeStructure, related_name="items", on_delete=models.CASCADE)
    fee_item = models.ForeignKey(FeeItem, related_name="structure_items", on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        ordering = ["fee_item__category", "fee_item__name"]
        constraints = [models.UniqueConstraint(fields=["structure", "fee_item"], name="unique_fee_item_per_structure")]

    def __str__(self):
        return f"{self.structure.name} · {self.fee_item.name}"


class StudentInvoice(BaseModel):
    STATUSES = [
        ("draft", "Draft"), ("issued", "Issued"), ("partial", "Part paid"),
        ("paid", "Paid"), ("overdue", "Overdue"), ("cancelled", "Cancelled"),
    ]
    invoice_number = models.CharField(max_length=32, unique=True, blank=True)
    student = models.ForeignKey("students.Student", related_name="invoices", on_delete=models.PROTECT)
    enrollment = models.ForeignKey("students.Enrollment", related_name="invoices", on_delete=models.SET_NULL, null=True, blank=True)
    term = models.ForeignKey("academics.Term", related_name="student_invoices", on_delete=models.PROTECT)
    structure = models.ForeignKey(FeeStructure, related_name="invoices", on_delete=models.SET_NULL, null=True, blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUSES, default="draft")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.User", related_name="created_invoices", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        indexes = [models.Index(fields=["invoice_number"]), models.Index(fields=["status", "due_date"])]
        constraints = [models.UniqueConstraint(fields=["student", "structure"], condition=Q(is_deleted=False, structure__isnull=False), name="unique_active_structure_invoice")]

    def clean(self):
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            raise ValidationError({"due_date": "The due date cannot be before the issue date."})
        if self.enrollment_id and self.enrollment.student_id != self.student_id:
            raise ValidationError({"enrollment": "This enrolment does not belong to the selected student."})
        if self.enrollment_id and self.term_id and self.enrollment.academic_year_id != self.term.academic_year_id:
            raise ValidationError({"enrollment": "The enrolment and term must be in the same academic year."})

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = (self.issue_date or timezone.localdate()).year
            prefix = f"INV-{year}-"
            latest = StudentInvoice.objects.filter(invoice_number__startswith=prefix).order_by("invoice_number").last()
            try:
                sequence = int(latest.invoice_number.removeprefix(prefix)) + 1 if latest else 1
            except (AttributeError, ValueError):
                sequence = StudentInvoice.objects.filter(invoice_number__startswith=prefix).count() + 1
            self.invoice_number = f"{prefix}{sequence:06d}"
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return self.lines.filter(is_deleted=False).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    @property
    def adjustment_total(self):
        charges = self.adjustments.filter(is_deleted=False, adjustment_type="charge").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        deductions = self.adjustments.filter(is_deleted=False, adjustment_type__in=("discount", "waiver", "credit")).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        return charges - deductions

    @property
    def total_amount(self):
        return max(Decimal("0.00"), self.subtotal + self.adjustment_total)

    @property
    def amount_paid(self):
        return self.payments.filter(is_deleted=False, is_reversed=False).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    @property
    def balance(self):
        return max(Decimal("0.00"), self.total_amount - self.amount_paid)

    def refresh_status(self, commit=True):
        if self.status == "cancelled":
            return self.status
        if self.total_amount and self.amount_paid >= self.total_amount:
            status = "paid"
        elif self.amount_paid > 0:
            status = "partial"
        elif self.due_date < timezone.localdate() and self.status != "draft":
            status = "overdue"
        else:
            status = "issued" if self.status != "draft" else "draft"
        if status != self.status:
            self.status = status
            if commit:
                StudentInvoice.objects.filter(pk=self.pk).update(status=status)
        return status

    def __str__(self):
        return f"{self.invoice_number} · {self.student.full_name}"


class InvoiceLine(BaseModel):
    invoice = models.ForeignKey(StudentInvoice, related_name="lines", on_delete=models.CASCADE)
    fee_item = models.ForeignKey(FeeItem, related_name="invoice_lines", on_delete=models.PROTECT, null=True, blank=True)
    description = models.CharField(max_length=180)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit_amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False)

    class Meta:
        ordering = ["id"]

    def clean(self):
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than zero."})
        if self.unit_amount is not None and self.unit_amount < 0:
            raise ValidationError({"unit_amount": "Amount cannot be negative."})

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_amount
        self.full_clean()
        super().save(*args, **kwargs)
        self.invoice.refresh_status()

    def __str__(self):
        return self.description


class InvoiceAdjustment(BaseModel):
    TYPES = [("discount", "Discount"), ("waiver", "Waiver"), ("credit", "Credit"), ("charge", "Additional charge")]
    invoice = models.ForeignKey(StudentInvoice, related_name="adjustments", on_delete=models.CASCADE)
    adjustment_type = models.CharField(max_length=16, choices=TYPES)
    description = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    approved_by = models.ForeignKey("accounts.User", related_name="approved_fee_adjustments", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Adjustment amount must be greater than zero."})

    def __str__(self):
        return f"{self.get_adjustment_type_display()} · {self.amount}"


class Payment(BaseModel):
    METHODS = [("cash", "Cash"), ("bank", "Bank deposit"), ("mobile_money", "Mobile money"), ("card", "Card"), ("cheque", "Cheque"), ("other", "Other")]
    receipt_number = models.CharField(max_length=32, unique=True, blank=True)
    invoice = models.ForeignKey(StudentInvoice, related_name="payments", on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=20, choices=METHODS, default="cash")
    reference = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey("accounts.User", related_name="recorded_fee_payments", on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    is_reversed = models.BooleanField(default=False)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey("accounts.User", related_name="reversed_fee_payments", on_delete=models.SET_NULL, null=True, blank=True)
    reversal_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        indexes = [models.Index(fields=["receipt_number"]), models.Index(fields=["payment_date", "is_reversed"])]

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Payment amount must be greater than zero."})
        if self.amount is not None and self.invoice_id and not self.is_reversed:
            available = self.invoice.balance
            if self.pk:
                previous = Payment.objects.filter(pk=self.pk, is_reversed=False).values_list("amount", flat=True).first()
                available += previous or Decimal("0.00")
            if self.amount > available:
                raise ValidationError({"amount": "Payment cannot exceed the current invoice balance."})

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            year = (self.payment_date or timezone.localdate()).year
            prefix = f"RCT-{year}-"
            latest = Payment.objects.filter(receipt_number__startswith=prefix).order_by("receipt_number").last()
            try:
                sequence = int(latest.receipt_number.removeprefix(prefix)) + 1 if latest else 1
            except (AttributeError, ValueError):
                sequence = Payment.objects.filter(receipt_number__startswith=prefix).count() + 1
            self.receipt_number = f"{prefix}{sequence:06d}"
        self.full_clean()
        super().save(*args, **kwargs)
        self.invoice.refresh_status()

    def __str__(self):
        return f"{self.receipt_number} · {self.amount}"
