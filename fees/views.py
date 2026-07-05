from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from config.audit import record_audit
from config.crud import AuditedFormMixin
from config.mixins import FinanceStaffRequiredMixin, ModuleRequiredMixin
from students.models import Enrollment
from .forms import FeeItemForm, FeeStructureForm, FeeStructureItemForm, InvoiceAdjustmentForm, InvoiceLineForm, PaymentForm, StudentInvoiceForm
from .models import FeeItem, FeeStructure, FeeStructureItem, InvoiceAdjustment, InvoiceLine, Payment, StudentInvoice


FINANCE_ROLES = {"super_admin", "headteacher", "director_of_studies", "bursar"}


class FeeStaffAccessMixin(ModuleRequiredMixin, FinanceStaffRequiredMixin):
    required_module = "fees"


class FeeUserAccessMixin(ModuleRequiredMixin, LoginRequiredMixin):
    required_module = "fees"


def scoped_invoices(user):
    queryset = StudentInvoice.objects.filter(is_deleted=False).select_related("student__stream", "term", "structure")
    if user.is_superuser or user.role in FINANCE_ROLES:
        return queryset
    if user.role == "student":
        return queryset.filter(student__user=user)
    if user.role == "parent":
        return queryset.filter(Q(student__parent=user) | Q(student__guardian_links__guardian__user=user)).distinct()
    return queryset.none()


class FeeDashboardView(FeeStaffAccessMixin, TemplateView):
    template_name = "fees/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoices = StudentInvoice.objects.filter(is_deleted=False).exclude(status="cancelled").select_related("student", "term")
        for invoice in invoices.filter(due_date__lt=timezone.localdate(), status="issued"):
            invoice.refresh_status()
        payments = Payment.objects.filter(is_deleted=False, is_reversed=False)
        billed = sum((invoice.total_amount for invoice in invoices), Decimal("0.00"))
        collected = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        context.update({
            "billed": billed,
            "collected": collected,
            "outstanding": max(Decimal("0.00"), billed - collected),
            "collection_rate": (collected / billed * 100) if billed else 0,
            "overdue_count": invoices.filter(due_date__lt=timezone.localdate()).exclude(status__in=("paid", "cancelled", "draft")).count(),
            "recent_payments": payments.select_related("invoice__student", "recorded_by")[:8],
            "recent_invoices": invoices[:8],
        })
        return context


class FeeItemListView(FeeStaffAccessMixin, ListView):
    model = FeeItem
    queryset = FeeItem.objects.filter(is_deleted=False)
    template_name = "fees/item_list.html"
    context_object_name = "fee_items"


class FeeItemCreateView(FeeStaffAccessMixin, AuditedFormMixin, CreateView):
    model = FeeItem
    form_class = FeeItemForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("fees:item-list")
    audit_action = "create"
    extra_context = {"page_title": "Add fee item", "eyebrow": "Fees & billing", "submit_label": "Save fee item"}


class FeeItemUpdateView(FeeStaffAccessMixin, AuditedFormMixin, UpdateView):
    model = FeeItem
    form_class = FeeItemForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("fees:item-list")
    audit_action = "update"
    extra_context = {"page_title": "Edit fee item", "eyebrow": "Fees & billing", "submit_label": "Save changes"}


class FeeStructureListView(FeeStaffAccessMixin, ListView):
    model = FeeStructure
    template_name = "fees/structure_list.html"
    context_object_name = "structures"
    paginate_by = 20

    def get_queryset(self):
        return FeeStructure.objects.filter(is_deleted=False).select_related("term__academic_year", "class_level", "stream")


class FeeStructureDetailView(FeeStaffAccessMixin, DetailView):
    model = FeeStructure
    template_name = "fees/structure_detail.html"
    context_object_name = "structure"

    def get_queryset(self):
        return FeeStructure.objects.filter(is_deleted=False).select_related("term__academic_year", "class_level", "stream").prefetch_related("items__fee_item")


class FeeStructureCreateView(FeeStaffAccessMixin, AuditedFormMixin, CreateView):
    model = FeeStructure
    form_class = FeeStructureForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Create fee structure", "eyebrow": "Fees & billing", "submit_label": "Create structure"}

    def get_success_url(self):
        return reverse("fees:structure-detail", args=[self.object.pk])


class FeeStructureUpdateView(FeeStaffAccessMixin, AuditedFormMixin, UpdateView):
    model = FeeStructure
    form_class = FeeStructureForm
    template_name = "shared/form.html"
    audit_action = "update"
    extra_context = {"page_title": "Edit fee structure", "eyebrow": "Fees & billing", "submit_label": "Save changes"}

    def get_success_url(self):
        return reverse("fees:structure-detail", args=[self.object.pk])


class FeeStructureItemCreateView(FeeStaffAccessMixin, AuditedFormMixin, CreateView):
    model = FeeStructureItem
    form_class = FeeStructureItemForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Add structure item", "eyebrow": "Fees & billing", "submit_label": "Add fee item"}

    def dispatch(self, request, *args, **kwargs):
        self.structure = get_object_or_404(FeeStructure.objects.filter(is_deleted=False), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.structure = self.structure
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("fees:structure-detail", args=[self.structure.pk])


class GenerateInvoicesView(FeeStaffAccessMixin, View):
    def post(self, request, pk):
        structure = get_object_or_404(FeeStructure.objects.filter(is_deleted=False), pk=pk)
        if structure.status != "published":
            messages.error(request, "Publish the fee structure before generating invoices.")
            return HttpResponseRedirect(reverse("fees:structure-detail", args=[pk]))
        items = list(structure.items.filter(is_deleted=False).select_related("fee_item"))
        if not items:
            messages.error(request, "Add at least one fee item before generating invoices.")
            return HttpResponseRedirect(reverse("fees:structure-detail", args=[pk]))
        enrollments = Enrollment.objects.filter(
            academic_year=structure.term.academic_year,
            stream__class_level=structure.class_level,
            is_deleted=False,
        ).exclude(status="withdrawn").select_related("student", "stream")
        if structure.stream_id:
            enrollments = enrollments.filter(stream=structure.stream)
        created = 0
        with transaction.atomic():
            for enrollment in enrollments:
                invoice, was_created = StudentInvoice.objects.get_or_create(
                    student=enrollment.student,
                    term=structure.term,
                    structure=structure,
                    is_deleted=False,
                    defaults={
                        "enrollment": enrollment, "issue_date": timezone.localdate(),
                        "due_date": structure.due_date, "status": "issued", "created_by": request.user,
                    },
                )
                if was_created:
                    InvoiceLine.objects.bulk_create([
                        InvoiceLine(invoice=invoice, fee_item=item.fee_item, description=item.fee_item.name, quantity=1, unit_amount=item.amount, amount=item.amount)
                        for item in items
                    ])
                    created += 1
        record_audit(request, "generate", structure, f"Generated {created} student invoice(s) from {structure}")
        messages.success(request, f"Generated {created} new invoice(s). Existing invoices were left unchanged.")
        return HttpResponseRedirect(reverse("fees:structure-detail", args=[pk]))


class InvoiceListView(FeeStaffAccessMixin, ListView):
    model = StudentInvoice
    template_name = "fees/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 25

    def get_queryset(self):
        queryset = scoped_invoices(self.request.user)
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "")
        if query:
            queryset = queryset.filter(Q(invoice_number__icontains=query) | Q(student__first_name__icontains=query) | Q(student__last_name__icontains=query) | Q(student__student_number__icontains=query))
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = StudentInvoice.STATUSES
        return context


class MyFeesView(FeeUserAccessMixin, ListView):
    model = StudentInvoice
    template_name = "fees/my_fees.html"
    context_object_name = "invoices"

    def get_queryset(self):
        return scoped_invoices(self.request.user)


class InvoiceDetailView(FeeUserAccessMixin, DetailView):
    model = StudentInvoice
    template_name = "fees/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return scoped_invoices(self.request.user).prefetch_related("lines__fee_item", "adjustments", "payments__recorded_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage_fees"] = self.request.user.is_superuser or self.request.user.role in FINANCE_ROLES
        return context


class InvoiceCreateView(FeeStaffAccessMixin, AuditedFormMixin, CreateView):
    model = StudentInvoice
    form_class = StudentInvoiceForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Issue student invoice", "eyebrow": "Fees & billing", "submit_label": "Issue invoice"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.status = "issued"
        form.instance.enrollment = Enrollment.objects.filter(student=form.instance.student, academic_year=form.instance.term.academic_year, is_deleted=False).first()
        with transaction.atomic():
            response = super().form_valid(form)
            if form.instance.structure_id:
                InvoiceLine.objects.bulk_create([
                    InvoiceLine(invoice=self.object, fee_item=item.fee_item, description=item.fee_item.name, quantity=1, unit_amount=item.amount, amount=item.amount)
                    for item in form.instance.structure.items.filter(is_deleted=False).select_related("fee_item")
                ])
        return response

    def get_success_url(self):
        return reverse("fees:invoice-detail", args=[self.object.pk])


class InvoiceLineCreateView(FeeStaffAccessMixin, AuditedFormMixin, CreateView):
    model = InvoiceLine
    form_class = InvoiceLineForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Add invoice line", "eyebrow": "Fees & billing", "submit_label": "Add line"}

    def dispatch(self, request, *args, **kwargs):
        self.invoice = get_object_or_404(StudentInvoice.objects.filter(is_deleted=False), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.invoice = self.invoice
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("fees:invoice-detail", args=[self.invoice.pk])


class InvoiceAdjustmentCreateView(FeeStaffAccessMixin, AuditedFormMixin, CreateView):
    model = InvoiceAdjustment
    form_class = InvoiceAdjustmentForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Add invoice adjustment", "eyebrow": "Fees & billing", "submit_label": "Apply adjustment"}

    def dispatch(self, request, *args, **kwargs):
        self.invoice = get_object_or_404(StudentInvoice.objects.filter(is_deleted=False), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.invoice = self.invoice
        form.instance.approved_by = self.request.user
        response = super().form_valid(form)
        self.invoice.refresh_status()
        return response

    def get_success_url(self):
        return reverse("fees:invoice-detail", args=[self.invoice.pk])


class PaymentCreateView(FeeStaffAccessMixin, AuditedFormMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Record fee payment", "eyebrow": "Fees & billing", "submit_label": "Record payment"}

    def dispatch(self, request, *args, **kwargs):
        self.invoice = get_object_or_404(StudentInvoice.objects.filter(is_deleted=False).exclude(status="cancelled"), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["invoice"] = self.invoice
        return kwargs

    def form_valid(self, form):
        form.instance.invoice = self.invoice
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("fees:receipt", args=[self.object.pk])


class ReceiptView(FeeUserAccessMixin, DetailView):
    model = Payment
    template_name = "fees/receipt.html"
    context_object_name = "payment"

    def get_queryset(self):
        return Payment.objects.filter(invoice__in=scoped_invoices(self.request.user), is_deleted=False).select_related("invoice__student", "invoice__term", "recorded_by")


class ReversePaymentView(FeeStaffAccessMixin, View):
    def post(self, request, pk):
        payment = get_object_or_404(Payment.objects.filter(is_deleted=False, is_reversed=False), pk=pk)
        payment.is_reversed = True
        payment.reversed_at = timezone.now()
        payment.reversed_by = request.user
        payment.reversal_reason = request.POST.get("reason", "Payment reversed by authorised finance user.")
        payment.save()
        record_audit(request, "reverse", payment, f"Reversed payment {payment.receipt_number}")
        messages.success(request, f"Payment {payment.receipt_number} was reversed and the invoice balance updated.")
        return HttpResponseRedirect(reverse("fees:invoice-detail", args=[payment.invoice_id]))
