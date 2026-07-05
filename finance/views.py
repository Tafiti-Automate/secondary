from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from academics.models import Term
from config.audit import record_audit
from config.crud import AuditedFormMixin
from config.mixins import FinanceStaffRequiredMixin, ModuleRequiredMixin
from config.tables import ModelTableView
from fees.models import Payment
from .forms import BankAccountForm, BankTransactionForm, BudgetForm, BudgetLineForm, ExpenditureForm, ExpenseCategoryForm, IncomeForm, IncomeSourceForm, VendorForm
from .models import BankAccount, BankTransaction, Budget, BudgetLine, Expenditure, ExpenseCategory, Income, IncomeSource, Vendor


class FinanceAccessMixin(ModuleRequiredMixin, FinanceStaffRequiredMixin):
    required_module = "finance"


class FinanceDashboardView(FinanceAccessMixin, TemplateView):
    template_name = "finance/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_term = Term.objects.filter(is_current=True, is_deleted=False).first()
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")
        try:
            start_date = timezone.datetime.strptime(start, "%Y-%m-%d").date() if start else (current_term.start_date if current_term else timezone.localdate().replace(day=1))
            end_date = timezone.datetime.strptime(end, "%Y-%m-%d").date() if end else (current_term.end_date if current_term else timezone.localdate())
        except ValueError:
            start_date, end_date = timezone.localdate().replace(day=1), timezone.localdate()
        fee_income = Payment.objects.filter(is_deleted=False, is_reversed=False, payment_date__range=(start_date, end_date)).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        other_income = Income.objects.filter(is_deleted=False, date_received__range=(start_date, end_date)).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        expenses = Expenditure.objects.filter(is_deleted=False, status="paid", date_incurred__range=(start_date, end_date))
        expense_amounts = expenses.aggregate(net=Sum("amount"), vat=Sum("vat_amount"))
        expense_total = (expense_amounts["net"] or Decimal("0.00")) + (expense_amounts["vat"] or Decimal("0.00"))
        total_income = fee_income + other_income
        context.update({
            "start_date": start_date, "end_date": end_date,
            "fee_income": fee_income, "other_income": other_income, "total_income": total_income,
            "expense_total": expense_total, "net_cash_flow": total_income - expense_total,
            "pending_count": Expenditure.objects.filter(is_deleted=False, status="pending").count(),
            "pending_expenditures": Expenditure.objects.filter(is_deleted=False, status="pending").select_related("category", "vendor", "requested_by")[:8],
            "recent_income": Income.objects.filter(is_deleted=False).select_related("source", "received_by")[:6],
            "recent_expenses": Expenditure.objects.filter(is_deleted=False).select_related("category", "vendor")[:6],
            "budgets": Budget.objects.filter(is_deleted=False, status="open").select_related("academic_year", "term")[:6],
        })
        return context


class FinanceTableView(FinanceAccessMixin, ModelTableView):
    eyebrow = "Institutional finance"


class FinanceCreateView(FinanceAccessMixin, AuditedFormMixin, CreateView):
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"eyebrow": "Institutional finance", "submit_label": "Save record"}


class FinanceUpdateView(FinanceAccessMixin, AuditedFormMixin, UpdateView):
    template_name = "shared/form.html"
    audit_action = "update"
    extra_context = {"eyebrow": "Institutional finance", "submit_label": "Save changes"}


class BudgetListView(FinanceAccessMixin, ListView):
    model = Budget
    template_name = "finance/budget_list.html"
    context_object_name = "budgets"

    def get_queryset(self):
        return Budget.objects.filter(is_deleted=False).select_related("academic_year", "term", "created_by")


class BudgetDetailView(FinanceAccessMixin, DetailView):
    model = Budget
    template_name = "finance/budget_detail.html"
    context_object_name = "budget"

    def get_queryset(self):
        return Budget.objects.filter(is_deleted=False).select_related("academic_year", "term").prefetch_related("lines__department", "lines__category")


class BudgetCreateView(FinanceCreateView):
    model = Budget
    form_class = BudgetForm
    extra_context = {"page_title": "Create budget", "eyebrow": "Institutional finance", "submit_label": "Create budget"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("finance:budget-detail", args=[self.object.pk])


class BudgetUpdateView(FinanceUpdateView):
    model = Budget
    form_class = BudgetForm
    extra_context = {"page_title": "Edit budget", "eyebrow": "Institutional finance", "submit_label": "Save budget"}

    def get_success_url(self):
        return reverse("finance:budget-detail", args=[self.object.pk])


class BudgetLineCreateView(FinanceCreateView):
    model = BudgetLine
    form_class = BudgetLineForm
    extra_context = {"page_title": "Add budget line", "eyebrow": "Institutional finance", "submit_label": "Add budget line"}

    def dispatch(self, request, *args, **kwargs):
        self.budget = get_object_or_404(Budget.objects.filter(is_deleted=False), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.budget = self.budget
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("finance:budget-detail", args=[self.budget.pk])


class ExpenditureListView(FinanceAccessMixin, ListView):
    model = Expenditure
    template_name = "finance/expenditure_list.html"
    context_object_name = "expenditures"
    paginate_by = 25

    def get_queryset(self):
        queryset = Expenditure.objects.filter(is_deleted=False).select_related("category", "vendor", "budget_line", "requested_by", "approved_by")
        query, status = self.request.GET.get("q", "").strip(), self.request.GET.get("status", "")
        if query:
            queryset = queryset.filter(Q(reference__icontains=query) | Q(description__icontains=query) | Q(vendor__name__icontains=query))
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Expenditure.STATUSES
        return context


class ExpenditureDetailView(FinanceAccessMixin, DetailView):
    model = Expenditure
    template_name = "finance/expenditure_detail.html"
    context_object_name = "expenditure"

    def get_queryset(self):
        return Expenditure.objects.filter(is_deleted=False).select_related("category", "vendor", "budget_line__budget", "requested_by", "approved_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_approve"] = self.request.user.is_superuser or self.request.user.role in {"super_admin", "headteacher"}
        return context


class ExpenditureCreateView(FinanceCreateView):
    model = Expenditure
    form_class = ExpenditureForm
    extra_context = {"page_title": "Record expenditure request", "eyebrow": "Institutional finance", "submit_label": "Save draft"}

    def form_valid(self, form):
        form.instance.requested_by = self.request.user
        form.instance.status = "draft"
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("finance:expenditure-detail", args=[self.object.pk])


class ExpenditureUpdateView(FinanceUpdateView):
    model = Expenditure
    form_class = ExpenditureForm
    extra_context = {"page_title": "Edit expenditure request", "eyebrow": "Institutional finance", "submit_label": "Save draft"}

    def get_queryset(self):
        return Expenditure.objects.filter(is_deleted=False, status__in=("draft", "rejected"))

    def get_success_url(self):
        return reverse("finance:expenditure-detail", args=[self.object.pk])


class ExpenditureActionView(FinanceAccessMixin, View):
    def post(self, request, pk, action):
        expenditure = get_object_or_404(Expenditure.objects.filter(is_deleted=False), pk=pk)
        old_status = expenditure.status
        if action == "submit" and expenditure.status in {"draft", "rejected"}:
            expenditure.status = "pending"
            expenditure.rejection_reason = ""
        elif action in {"approve", "reject"}:
            if not (request.user.is_superuser or request.user.role in {"super_admin", "headteacher"}):
                raise PermissionDenied("Only the headteacher or a super administrator may approve expenditure.")
            if expenditure.status != "pending":
                messages.error(request, "Only pending expenditure can be approved or rejected.")
                return HttpResponseRedirect(reverse("finance:expenditure-detail", args=[pk]))
            expenditure.status = "approved" if action == "approve" else "rejected"
            expenditure.approved_by = request.user if action == "approve" else None
            expenditure.approved_at = timezone.now() if action == "approve" else None
            expenditure.rejection_reason = request.POST.get("reason", "").strip() or f"Rejected by {request.user}." if action == "reject" else ""
        elif action == "pay" and expenditure.status == "approved":
            payment_method = request.POST.get("payment_method", expenditure.payment_method)
            if not payment_method:
                messages.error(request, "Select the payment method before marking this expenditure as paid.")
                return HttpResponseRedirect(reverse("finance:expenditure-detail", args=[pk]))
            expenditure.status = "paid"
            expenditure.payment_method = payment_method
            if request.POST.get("payment_reference"):
                expenditure.payment_reference = request.POST["payment_reference"]
        else:
            messages.error(request, "That workflow action is not available for the current status.")
            return HttpResponseRedirect(reverse("finance:expenditure-detail", args=[pk]))
        expenditure.save()
        record_audit(request, action, expenditure, f"Changed {expenditure.reference} from {old_status} to {expenditure.status}")
        messages.success(request, f"Expenditure is now {expenditure.get_status_display().lower()}.")
        return HttpResponseRedirect(reverse("finance:expenditure-detail", args=[pk]))


class IncomeListView(FinanceAccessMixin, ListView):
    model = Income
    queryset = Income.objects.filter(is_deleted=False).select_related("source", "bank_account", "received_by")
    template_name = "finance/income_list.html"
    context_object_name = "income_entries"
    paginate_by = 25


class IncomeCreateView(FinanceCreateView):
    model = Income
    form_class = IncomeForm
    success_url = reverse_lazy("finance:income-list")
    extra_context = {"page_title": "Record other income", "eyebrow": "Institutional finance", "submit_label": "Record income"}

    def form_valid(self, form):
        form.instance.received_by = self.request.user
        response = super().form_valid(form)
        if self.object.bank_account_id:
            BankTransaction.objects.create(
                bank_account=self.object.bank_account, transaction_date=self.object.date_received,
                transaction_type="credit", description=self.object.description, amount=self.object.amount,
                reference=self.object.external_reference or self.object.reference, income=self.object,
            )
        return response


class BankTransactionListView(FinanceAccessMixin, ListView):
    model = BankTransaction
    queryset = BankTransaction.objects.filter(is_deleted=False).select_related("bank_account")
    template_name = "finance/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 30


class BankTransactionCreateView(FinanceCreateView):
    model = BankTransaction
    form_class = BankTransactionForm
    success_url = reverse_lazy("finance:transaction-list")
    extra_context = {"page_title": "Add bank transaction", "eyebrow": "Institutional finance", "submit_label": "Save transaction"}
