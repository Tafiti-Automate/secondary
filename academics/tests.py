from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User

from .models import AcademicYear, Term


class AcademicCalendarTests(TestCase):
    def test_only_one_current_year(self):
        first = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), is_current=True)
        second = AcademicYear.objects.create(name="2027", start_date=date(2027, 1, 1), end_date=date(2027, 12, 31), is_current=True)
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)

    def test_term_must_fit_academic_year(self):
        year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        with self.assertRaises(ValidationError):
            Term.objects.create(academic_year=year, name="Invalid", number=1, start_date=date(2025, 12, 1), end_date=date(2026, 3, 1))

    def test_teacher_cannot_change_academic_structure_api(self):
        teacher = User.objects.create_user("teacher", role="teacher")
        client = APIClient()
        client.force_authenticate(teacher)
        response = client.post("/api/academics/academic-years/", {"name": "2028", "start_date": "2028-01-01", "end_date": "2028-12-31"})
        self.assertEqual(response.status_code, 403)
