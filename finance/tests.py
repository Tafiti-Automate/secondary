from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from academics.models import AcademicYear, SchoolProfile
from config.models import SchoolModule
from .models import Budget, Expenditure, ExpenseCategory


class ExpenditureApprovalTests(TestCase):
    def setUp(self):
        self.school = SchoolProfile.objects.create(name="Finance Secondary")
        SchoolModule.objects.create(school=self.school, code="finance", is_enabled=True)
        self.bursar = User.objects.create_user(username="bursar", password="test-pass-123", role="bursar")
        self.headteacher = User.objects.create_user(username="head", password="test-pass-123", role="headteacher")
        self.category = ExpenseCategory.objects.create(name="Utilities", code="UTIL")
        self.expenditure = Expenditure.objects.create(
            category=self.category, description="Electricity bill", amount=Decimal("450000"),
            date_incurred=date(2026, 7, 5), requested_by=self.bursar,
        )

    def test_headteacher_approval_and_bursar_payment_workflow(self):
        self.client.login(username="bursar", password="test-pass-123")
        self.client.post(reverse("finance:expenditure-action", args=[self.expenditure.pk, "submit"]))
        self.expenditure.refresh_from_db()
        self.assertEqual(self.expenditure.status, "pending")

        response = self.client.post(reverse("finance:expenditure-action", args=[self.expenditure.pk, "approve"]))
        self.assertEqual(response.status_code, 403)

        self.client.login(username="head", password="test-pass-123")
        self.client.post(reverse("finance:expenditure-action", args=[self.expenditure.pk, "approve"]))
        self.expenditure.refresh_from_db()
        self.assertEqual(self.expenditure.status, "approved")
        self.assertEqual(self.expenditure.approved_by, self.headteacher)

        self.client.login(username="bursar", password="test-pass-123")
        self.client.post(reverse("finance:expenditure-action", args=[self.expenditure.pk, "pay"]), {"payment_method": "bank", "payment_reference": "BANK-001"})
        self.expenditure.refresh_from_db()
        self.assertEqual(self.expenditure.status, "paid")

    def test_finance_workspace_pages_render(self):
        year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        budget = Budget.objects.create(name="Annual operating budget", academic_year=year, status="open", created_by=self.bursar)
        self.client.login(username="bursar", password="test-pass-123")
        urls = [
            reverse("finance:dashboard"), reverse("finance:budget-list"), reverse("finance:budget-detail", args=[budget.pk]),
            reverse("finance:expenditure-list"), reverse("finance:expenditure-detail", args=[self.expenditure.pk]),
            reverse("finance:income-list"), reverse("finance:transaction-list"), reverse("finance:categories-list"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
