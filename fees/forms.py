from django import forms

from config.forms import StyledModelForm
from students.models import Enrollment, Student
from .models import FeeItem, FeeStructure, FeeStructureItem, InvoiceAdjustment, InvoiceLine, Payment, StudentInvoice


class FeeItemForm(StyledModelForm):
    class Meta:
        model = FeeItem
        fields = ("name", "category", "description", "default_amount", "is_active")


class FeeStructureForm(StyledModelForm):
    class Meta:
        model = FeeStructure
        fields = ("name", "term", "class_level", "stream", "due_date", "status", "notes")


class FeeStructureItemForm(StyledModelForm):
    class Meta:
        model = FeeStructureItem
        fields = ("fee_item", "amount", "is_mandatory")


class StudentInvoiceForm(StyledModelForm):
    class Meta:
        model = StudentInvoice
        fields = ("student", "term", "structure", "issue_date", "due_date", "notes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(is_deleted=False, is_active=True).select_related("stream")
        self.fields["structure"].queryset = FeeStructure.objects.filter(is_deleted=False, status="published").select_related("term", "class_level", "stream")

    def clean(self):
        cleaned = super().clean()
        student, term, structure = cleaned.get("student"), cleaned.get("term"), cleaned.get("structure")
        if structure and term and structure.term_id != term.pk:
            self.add_error("structure", "This fee structure belongs to a different term.")
        if student and structure and student.stream_id:
            if student.stream.class_level_id != structure.class_level_id:
                self.add_error("structure", "This fee structure does not apply to the learner's class.")
            elif structure.stream_id and structure.stream_id != student.stream_id:
                self.add_error("structure", "This fee structure applies to another stream.")
        if student and term and not Enrollment.objects.filter(student=student, academic_year=term.academic_year, is_deleted=False).exists():
            self.add_error("student", "This learner has no enrolment in the term's academic year.")
        return cleaned


class InvoiceLineForm(StyledModelForm):
    class Meta:
        model = InvoiceLine
        fields = ("fee_item", "description", "quantity", "unit_amount")


class InvoiceAdjustmentForm(StyledModelForm):
    class Meta:
        model = InvoiceAdjustment
        fields = ("adjustment_type", "description", "amount")


class PaymentForm(StyledModelForm):
    class Meta:
        model = Payment
        fields = ("amount", "payment_date", "method", "reference", "notes")

    def __init__(self, *args, invoice=None, **kwargs):
        self.invoice = invoice
        super().__init__(*args, **kwargs)
        if invoice and not self.is_bound:
            self.fields["amount"].initial = invoice.balance
        if invoice:
            self.fields["amount"].help_text = f"Current outstanding balance: UGX {invoice.balance:,.2f}"

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if self.invoice and amount > self.invoice.balance:
            raise forms.ValidationError("Payment cannot exceed the current invoice balance. Use an adjustment or credit workflow for overpayments.")
        return amount
