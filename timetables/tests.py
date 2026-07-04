from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from academics.models import AcademicYear, ClassLevel, Department, Stream, Subject, SubjectAllocation, Term
from accounts.models import User
from .models import Room, TimeSlot, TimetableEntry
from .services import generate_conflict_free_timetable


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

    def test_generator_places_lessons_without_conflicts(self):
        year = AcademicYear.objects.create(name="2028", start_date=date(2028, 1, 1), end_date=date(2028, 12, 31))
        term = Term.objects.create(academic_year=year, name="Term I", number=1, start_date=date(2028, 1, 1), end_date=date(2028, 4, 1))
        level = ClassLevel.objects.create(name="S2", level=2, curriculum="lower")
        stream = Stream.objects.create(name="A", class_level=level, academic_year=year)
        teacher = User.objects.create_user("generator-teacher", role="teacher")
        manager = User.objects.create_user("generator-dos", role="director_of_studies")
        subject = Subject.objects.create(name="Biology", code="BIO-GEN")
        SubjectAllocation.objects.create(teacher=teacher, subject=subject, stream=stream, term=term, lessons_per_week=2)
        TimeSlot.objects.create(name="P1", start_time=time(8), end_time=time(8, 40))
        TimeSlot.objects.create(name="P2", start_time=time(9), end_time=time(9, 40), display_order=2)
        Room.objects.create(name="Room 1", capacity=80)

        run = generate_conflict_free_timetable(term, manager)

        entries = TimetableEntry.objects.filter(term=term, stream=stream, subject=subject)
        self.assertEqual(run.status, "completed")
        self.assertEqual(entries.count(), 2)
        self.assertEqual(entries.values("day_of_week", "time_slot").distinct().count(), 2)
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse("timetables:generate")).status_code, 200)
