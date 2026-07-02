from datetime import date

from django.test import TestCase
from django.urls import reverse

from academics.models import AcademicYear, ClassLevel, Stream, Term
from accounts.models import User
from students.models import Student
from .models import AttendanceRecord, AttendanceSession


class AttendanceTests(TestCase):
    def test_register_records_each_learner(self):
        year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        term = Term.objects.create(academic_year=year, name="Term I", number=1, start_date=date(2026, 1, 1), end_date=date(2026, 4, 1))
        level = ClassLevel.objects.create(name="S1", level=1, curriculum="lower")
        teacher = User.objects.create_user("teacher", role="teacher")
        stream = Stream.objects.create(name="A", class_level=level, academic_year=year, class_teacher=teacher)
        student = Student.objects.create(first_name="A", last_name="B", gender="female", date_of_birth=date(2012, 1, 1), stream=stream)
        session = AttendanceSession.objects.create(term=term, stream=stream, date=date(2026, 2, 1), taken_by=teacher)
        self.client.force_login(teacher)
        response = self.client.post(reverse("attendance:take", args=[session.pk]), {f"status_{student.pk}": "present"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AttendanceRecord.objects.get(session=session, student=student).status, "present")
