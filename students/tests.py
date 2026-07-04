from datetime import date

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from academics.models import AcademicYear, ClassLevel, Stream, Subject, SubjectAllocation, Term
from accounts.models import User
from rest_framework.test import APIClient
from .models import Enrollment, Guardian, Student, StudentGuardian, StudentMovement


class StudentAdmissionTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        self.term = Term.objects.create(academic_year=self.year, name="Term III", number=3, start_date=date(2026, 9, 1), end_date=date(2026, 12, 1))
        level = ClassLevel.objects.create(name="S1", level=1, curriculum="lower")
        self.stream = Stream.objects.create(name="A", class_level=level, academic_year=self.year)

    def test_admission_number_is_generated(self):
        student = Student.objects.create(first_name="Amina", last_name="Kato", gender="female", date_of_birth=date(2012, 1, 1), stream=self.stream, date_admitted=date(2026, 2, 1))
        self.assertRegex(student.admission_number, r"^2026/\d{4}$")
        self.assertRegex(student.student_number, r"^STU-\d{6}$")

    def test_parent_only_sees_linked_student(self):
        parent = User.objects.create_user("parent", role="parent")
        guardian = Guardian.objects.create(user=parent, first_name="Parent", last_name="One", phone="0700000000")
        linked = Student.objects.create(first_name="Linked", last_name="Learner", gender="female", date_of_birth=date(2012, 1, 1), stream=self.stream)
        other = Student.objects.create(first_name="Other", last_name="Learner", gender="male", date_of_birth=date(2012, 1, 1), stream=self.stream)
        StudentGuardian.objects.create(student=linked, guardian=guardian, is_primary=True)
        self.client.force_login(parent)
        self.assertEqual(self.client.get(reverse("students:detail", args=[linked.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("students:detail", args=[other.pk])).status_code, 404)

    def test_manager_can_import_csv_atomically(self):
        manager = User.objects.create_user("dos", role="director_of_studies")
        self.client.force_login(manager)
        payload = b"first_name,last_name,gender,date_of_birth\nJoan,Atim,female,2012-04-05\n"
        upload = SimpleUploadedFile("students.csv", payload, content_type="text/csv")
        response = self.client.post(reverse("students:import"), {"academic_year": self.stream.academic_year_id, "stream": self.stream.pk, "csv_file": upload})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Student.objects.filter(first_name="Joan", last_name="Atim").exists())

    def test_bulk_completion_graduates_students_without_destination_stream(self):
        manager = User.objects.create_user("dos", role="director_of_studies")
        student = Student.objects.create(first_name="Final", last_name="Learner", gender="female", date_of_birth=date(2010, 1, 1), stream=self.stream)
        Enrollment.objects.create(student=student, academic_year=self.year, stream=self.stream)
        self.client.force_login(manager)

        response = self.client.post(reverse("students:bulk-promotion"), {
            "term": self.term.pk,
            "from_stream": self.stream.pk,
            "decision": "completed",
            "apply_to": "all",
            "remarks": "Completed final year.",
        })

        self.assertEqual(response.status_code, 302)
        student.refresh_from_db()
        self.assertEqual(student.status, "graduated")
        self.assertFalse(student.is_active)
        self.assertTrue(StudentMovement.objects.filter(student=student, movement_type="graduation", is_deleted=False).exists())
        self.assertEqual(Enrollment.objects.get(student=student, academic_year=self.year).status, "completed")

    def test_teacher_api_does_not_expose_private_identity_or_medical_fields(self):
        teacher = User.objects.create_user("privacy-teacher", role="teacher")
        subject = Subject.objects.create(name="Privacy English", code="PENG", curriculum_level="lower")
        SubjectAllocation.objects.create(teacher=teacher, subject=subject, stream=self.stream, term=self.term)
        Student.objects.create(
            first_name="Private", last_name="Learner", gender="female",
            date_of_birth=date(2012, 1, 1), stream=self.stream,
            national_id="SECRET-NIN", medical_information="Sensitive medical note",
            allergies="Sensitive allergy", special_needs="Learning accommodation",
        )
        client = APIClient()
        client.force_authenticate(teacher)

        response = client.get("/api/students/students/")

        self.assertEqual(response.status_code, 200)
        record = response.data["results"][0]
        self.assertNotIn("national_id", record)
        self.assertNotIn("medical_information", record)
        self.assertNotIn("allergies", record)
        self.assertEqual(record["special_needs"], "Learning accommodation")
