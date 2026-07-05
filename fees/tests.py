from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from academics.models import AcademicYear, ClassLevel, SchoolProfile, Stream, Term
from config.models import SchoolModule
from students.models import Enrollment, Student
from .models import FeeItem, FeeStructure, FeeStructureItem, Payment, StudentInvoice


class FeeWorkflowTests(TestCase):
    def setUp(self):
        self.school = SchoolProfile.objects.create(name="Billing Secondary")
        SchoolModule.objects.create(school=self.school, code="fees", is_enabled=True)
        self.bursar = User.objects.create_user(username="bursar", password="test-pass-123", role="bursar")
        self.year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), is_current=True)
        self.term = Term.objects.create(academic_year=self.year, name="Term II", number=2, start_date=date(2026, 5, 1), end_date=date(2026, 8, 31), is_current=True)
        self.level = ClassLevel.objects.create(name="S1", curriculum="lower", level=1)
        self.stream = Stream.objects.create(name="A", class_level=self.level, academic_year=self.year)
        self.student = Student.objects.create(first_name="Amina", last_name="Nabirye", gender="female", date_of_birth=date(2012, 3, 2), stream=self.stream)
        self.enrollment = Enrollment.objects.create(student=self.student, academic_year=self.year, stream=self.stream)
        self.item = FeeItem.objects.create(name="Tuition", category="tuition", default_amount=Decimal("500000"))
        self.structure = FeeStructure.objects.create(name="S1 Term II", term=self.term, class_level=self.level, due_date=date(2026, 7, 31), status="published")
        FeeStructureItem.objects.create(structure=self.structure, fee_item=self.item, amount=Decimal("500000"))
        self.client.login(username="bursar", password="test-pass-123")

    def test_bulk_generation_is_idempotent(self):
        url = reverse("fees:structure-generate", args=[self.structure.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(StudentInvoice.objects.count(), 1)
        invoice = StudentInvoice.objects.get()
        self.assertEqual(invoice.total_amount, Decimal("500000"))
        self.assertEqual(invoice.balance, Decimal("500000"))

    def test_payment_updates_invoice_status_and_balance(self):
        self.client.post(reverse("fees:structure-generate", args=[self.structure.pk]))
        invoice = StudentInvoice.objects.get()
        Payment.objects.create(invoice=invoice, amount=Decimal("200000"), method="cash", recorded_by=self.bursar)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "partial")
        self.assertEqual(invoice.balance, Decimal("300000"))
        Payment.objects.create(invoice=invoice, amount=Decimal("300000"), method="bank", recorded_by=self.bursar)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(invoice.balance, Decimal("0"))

    def test_payment_form_rejects_overpayment(self):
        self.client.post(reverse("fees:structure-generate", args=[self.structure.pk]))
        invoice = StudentInvoice.objects.get()
        response = self.client.post(reverse("fees:payment-add", args=[invoice.pk]), {
            "amount": "500001", "payment_date": "2026-07-05", "method": "cash", "reference": "", "notes": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment cannot exceed")
        self.assertEqual(Payment.objects.count(), 0)

    def test_fee_workspace_pages_render(self):
        self.client.post(reverse("fees:structure-generate", args=[self.structure.pk]))
        invoice = StudentInvoice.objects.get()
        payment = Payment.objects.create(invoice=invoice, amount=Decimal("100000"), method="cash", recorded_by=self.bursar)
        urls = [
            reverse("fees:dashboard"), reverse("fees:item-list"), reverse("fees:structure-list"),
            reverse("fees:structure-detail", args=[self.structure.pk]), reverse("fees:invoice-list"),
            reverse("fees:invoice-detail", args=[invoice.pk]), reverse("fees:receipt", args=[payment.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
