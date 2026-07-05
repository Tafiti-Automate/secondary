from django.contrib import admin

from .models import BankAccount, BankTransaction, Budget, BudgetLine, Expenditure, ExpenseCategory, Income, IncomeSource, Vendor

admin.site.register((BankAccount, BankTransaction, Budget, BudgetLine, Expenditure, ExpenseCategory, Income, IncomeSource, Vendor))
