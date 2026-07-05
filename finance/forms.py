from config.forms import StyledModelForm
from .models import BankAccount, BankTransaction, Budget, BudgetLine, Expenditure, ExpenseCategory, Income, IncomeSource, Vendor


class ExpenseCategoryForm(StyledModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ("name", "code", "description", "is_active")


class VendorForm(StyledModelForm):
    class Meta:
        model = Vendor
        fields = ("name", "contact_person", "phone", "email", "address", "tax_number", "is_active")


class BankAccountForm(StyledModelForm):
    class Meta:
        model = BankAccount
        fields = ("name", "bank_name", "account_name", "account_number", "currency", "opening_balance", "is_active")


class BudgetForm(StyledModelForm):
    class Meta:
        model = Budget
        fields = ("name", "academic_year", "term", "status", "notes")


class BudgetLineForm(StyledModelForm):
    class Meta:
        model = BudgetLine
        fields = ("department", "category", "description", "allocated_amount")


class ExpenditureForm(StyledModelForm):
    class Meta:
        model = Expenditure
        fields = ("budget_line", "category", "vendor", "description", "amount", "vat_amount", "date_incurred", "payment_method", "payment_reference", "attachment")


class IncomeSourceForm(StyledModelForm):
    class Meta:
        model = IncomeSource
        fields = ("name", "description", "is_active")


class IncomeForm(StyledModelForm):
    class Meta:
        model = Income
        fields = ("source", "description", "amount", "date_received", "external_reference", "bank_account", "notes")


class BankTransactionForm(StyledModelForm):
    class Meta:
        model = BankTransaction
        fields = ("bank_account", "transaction_date", "transaction_type", "description", "amount", "reference", "fee_payment", "income", "expenditure", "is_reconciled", "notes")
