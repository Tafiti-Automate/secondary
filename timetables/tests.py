from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase

from academics.models import AcademicYear, ClassLevel, Department, Stream, Subject, Term
from accounts.models import User
from .models import Room, TimeSlot, TimetableEntry


class TimetableConflictTests(TestCase):
    def test_teacher_cannot_be_double_booked(self):
        year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        term = Term.objects.create(academic_year=year, name="Term I", number=1, start_date=date(2026, 1, 1), end_date=date(2026, 4, 1))
        level = ClassLevel.objects.create(name="S1", level=1, curriculum="lower")
        stream_a = Stream.objects.create(name="A", class_level=level, academic_year=year)
        stream_b = Stream.objects.create(name="B", class_level=level, academic_year=year)
        teacher = User.objects.create_user("teacher", role="teacher")
        subject = Subject.objects.create(name="English", code="ENG", department=Department.objects.create(name="Languages"))
        slot = TimeSlot.objects.create(name="P1", start_time=time(8), end_time=time(8, 40))
        TimetableEntry.objects.create(term=term, stream=stream_a, day_of_week=1, time_slot=slot, subject=subject, teacher=teacher)
        with self.assertRaises(ValidationError):
            TimetableEntry.objects.create(term=term, stream=stream_b, day_of_week=1, time_slot=slot, subject=subject, teacher=teacher)
