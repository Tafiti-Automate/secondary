from django.urls import path, reverse_lazy

from .forms import BankAccountForm, ExpenseCategoryForm, IncomeSourceForm, VendorForm
from .models import BankAccount, ExpenseCategory, IncomeSource, Vendor
from .views import BankTransactionCreateView, BankTransactionListView, BudgetCreateView, BudgetDetailView, BudgetLineCreateView, BudgetListView, BudgetUpdateView, ExpenditureActionView, ExpenditureCreateView, ExpenditureDetailView, ExpenditureListView, ExpenditureUpdateView, FinanceCreateView, FinanceDashboardView, FinanceTableView, FinanceUpdateView, IncomeCreateView, IncomeListView

app_name = "finance"

ENTITY_CONFIG = {
    "categories": (ExpenseCategory, ExpenseCategoryForm, ("Category", "Code", "Active"), ("name", "code", "is_active"), "Expense categories"),
    "vendors": (Vendor, VendorForm, ("Vendor", "Contact", "Phone", "Active"), ("name", "contact_person", "phone", "is_active"), "Vendors"),
    "accounts": (BankAccount, BankAccountForm, ("Account", "Bank", "Account number", "Balance", "Active"), ("name", "bank_name", "account_number", "current_balance", "is_active"), "Bank accounts"),
    "income-sources": (IncomeSource, IncomeSourceForm, ("Income source", "Description", "Active"), ("name", "description", "is_active"), "Income sources"),
}

urlpatterns = [
    path("", FinanceDashboardView.as_view(), name="dashboard"),
    path("budgets/", BudgetListView.as_view(), name="budget-list"),
    path("budgets/add/", BudgetCreateView.as_view(), name="budget-add"),
    path("budgets/<int:pk>/", BudgetDetailView.as_view(), name="budget-detail"),
    path("budgets/<int:pk>/edit/", BudgetUpdateView.as_view(), name="budget-edit"),
    path("budgets/<int:pk>/lines/add/", BudgetLineCreateView.as_view(), name="budget-line-add"),
    path("expenditures/", ExpenditureListView.as_view(), name="expenditure-list"),
    path("expenditures/add/", ExpenditureCreateView.as_view(), name="expenditure-add"),
    path("expenditures/<int:pk>/", ExpenditureDetailView.as_view(), name="expenditure-detail"),
    path("expenditures/<int:pk>/edit/", ExpenditureUpdateView.as_view(), name="expenditure-edit"),
    path("expenditures/<int:pk>/<str:action>/", ExpenditureActionView.as_view(), name="expenditure-action"),
    path("income/", IncomeListView.as_view(), name="income-list"),
    path("income/add/", IncomeCreateView.as_view(), name="income-add"),
    path("transactions/", BankTransactionListView.as_view(), name="transaction-list"),
    path("transactions/add/", BankTransactionCreateView.as_view(), name="transaction-add"),
]

for slug, (model, form_class, columns, fields, title) in ENTITY_CONFIG.items():
    list_name, add_name, edit_name = f"{slug}-list", f"{slug}-add", f"{slug}-edit"
    success = reverse_lazy(f"finance:{list_name}")
    urlpatterns += [
        path(f"{slug}/", FinanceTableView.as_view(model=model, columns=columns, field_paths=fields, page_title=title, create_url_name=f"finance:{add_name}", edit_url_name=f"finance:{edit_name}", search_fields=("name",)), name=list_name),
        path(f"{slug}/add/", FinanceCreateView.as_view(model=model, form_class=form_class, success_url=success, extra_context={"page_title": f"Add {model._meta.verbose_name}", "eyebrow": "Institutional finance", "submit_label": "Save record"}), name=add_name),
        path(f"{slug}/<int:pk>/edit/", FinanceUpdateView.as_view(model=model, form_class=form_class, success_url=success, extra_context={"page_title": f"Edit {model._meta.verbose_name}", "eyebrow": "Institutional finance", "submit_label": "Save changes"}), name=edit_name),
    ]
