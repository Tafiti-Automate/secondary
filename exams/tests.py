from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User

from academics.models import AcademicYear, ClassLevel, Department, Stream, Subject, SubjectAllocation, Term
from students.models import Student
from .models import (
    ExamSession, Examination, ExaminationResult, GradeBoundary, GradeScale, UNEBCandidate,
    UNEBCandidateSubject, UNEBContinuousAssessment, UpperAssessmentComponent, UpperAssessmentPlan,
)
from .readiness import uneb_export_preflight
from .services import process_upper_subject_results


class ExaminationTests(TestCase):
    def setUp(self):
        year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        term = Term.objects.create(academic_year=year, name="Term I", number=1, start_date=date(2026, 1, 1), end_date=date(2026, 4, 1))
        level = ClassLevel.objects.create(name="S1", level=1, curriculum="lower")
        stream = Stream.objects.create(name="A", class_level=level, academic_year=year)
        subject = Subject.objects.create(name="English", code="ENG", department=Department.objects.create(name="Languages"))
        scale = GradeScale.objects.create(name="School scale")
        GradeBoundary.objects.create(scale=scale, minimum_score=80, maximum_score=100, grade="A", points=1)
        GradeBoundary.objects.create(scale=scale, minimum_score=0, maximum_score=79.99, grade="B", points=2)
        session = ExamSession.objects.create(term=term, name="End term", start_date=date(2026, 3, 1), end_date=date(2026, 3, 5), grade_scale=scale)
        self.exam = Examination.objects.create(title="English", session=session, term=term, subject=subject, stream=stream, max_score=50)
        self.student = Student.objects.create(first_name="A", last_name="B", gender="female", date_of_birth=date(2012, 1, 1), stream=stream)

    def test_grade_is_computed_automatically(self):
        result = ExaminationResult.objects.create(examination=self.exam, student=self.student, score=45)
        self.assertEqual(result.grade, "A")
        self.assertEqual(result.points, 1)

    def test_status_updates_lock_flags(self):
        self.exam.status = "locked"
        self.exam.save()
        self.assertTrue(self.exam.locked)
        self.assertTrue(self.exam.published)

    def test_locked_result_cannot_be_changed_through_api(self):
        manager = User.objects.create_user("dos", role="director_of_studies")
        result = ExaminationResult.objects.create(examination=self.exam, student=self.student, score=40)
        self.exam.status = "locked"
        self.exam.save()
        client = APIClient()
        client.force_authenticate(manager)
        response = client.patch(f"/api/exams/results/{result.pk}/", {"score": "20.00"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_uce_candidate_rejects_lower_class_student(self):
        with self.assertRaises(ValidationError):
            UNEBCandidate.objects.create(student=self.student, examination_level="uce", examination_year=2026, centre_number="U001", gender="female")


class UpperSecondaryProcessingTests(TestCase):
    def test_weighted_components_are_processed_into_final_result(self):
        year = AcademicYear.objects.create(name="2028", start_date=date(2028, 1, 1), end_date=date(2028, 12, 31))
        term = Term.objects.create(academic_year=year, name="Term III", number=3, start_date=date(2028, 9, 1), end_date=date(2028, 12, 1))
        level = ClassLevel.objects.create(name="S5", level=5, curriculum="upper")
        stream = Stream.objects.create(name="Science", class_level=level, academic_year=year)
        subject = Subject.objects.create(name="Physics", code="PHY", curriculum_level="upper", department=Department.objects.create(name="Physics"))
        student = Student.objects.create(first_name="Isaac", last_name="Okello", gender="male", date_of_birth=date(2010, 1, 1), stream=stream)
        manager = User.objects.create_user("upper-dos", role="director_of_studies")
        scale = GradeScale.objects.create(name="A-Level scale", curriculum_level="upper")
        GradeBoundary.objects.create(scale=scale, minimum_score=70, maximum_score=100, grade="A", points=6)
        GradeBoundary.objects.create(scale=scale, minimum_score=0, maximum_score=69.99, grade="O", points=1)
        plan = UpperAssessmentPlan.objects.create(academic_year=year, class_level=level, subject=subject, name="S5 Physics", grade_scale=scale)
        coursework = UpperAssessmentComponent.objects.create(plan=plan, name="Coursework", component_type="coursework", weight=40, maximum_score=100)
        exam_component = UpperAssessmentComponent.objects.create(plan=plan, name="Annual summative", component_type="annual_summative", weight=60, maximum_score=100, sequence=2)
        plan.status, plan.approved_by = "approved", manager
        plan.save()
        annual_session = ExamSession.objects.create(
            term=term, name="Annual assessment", exam_type="annual",
            start_date=date(2028, 11, 1), end_date=date(2028, 11, 5),
        )
        coursework_exam = Examination.objects.create(title="Physics coursework", term=term, subject=subject, stream=stream, component=coursework, status="approved", is_school_summative=False)
        final_exam = Examination.objects.create(title="Physics final", session=annual_session, term=term, subject=subject, stream=stream, component=exam_component, status="approved")
        ExaminationResult.objects.create(examination=coursework_exam, student=student, score=80)
        ExaminationResult.objects.create(examination=final_exam, student=student, score=70)

        [result] = process_upper_subject_results(plan, term, stream, manager)

        self.assertEqual(result.total_score, Decimal("74.00"))
        self.assertEqual(result.grade, "A")
        self.assertEqual(result.subject_position, 1)
        result.transition("moderate", manager)
        result.transition("approve", manager)
        headteacher = User.objects.create_user("upper-head", role="headteacher")
        result.transition("lock", headteacher)
        self.assertEqual(result.status, "locked")
        result.remark = "Changed after lock"
        with self.assertRaises(ValidationError):
            result.save()

    def test_aligned_plan_rejects_term_test_component(self):
        year = AcademicYear.objects.create(name="2030", start_date=date(2030, 1, 1), end_date=date(2030, 12, 31))
        level = ClassLevel.objects.create(name="S5-2030", level=15, curriculum="upper")
        subject = Subject.objects.create(name="Advanced Biology", code="ABIO", curriculum_level="upper")
        plan = UpperAssessmentPlan.objects.create(academic_year=year, class_level=level, subject=subject, name="Aligned Biology")
        with self.assertRaises(ValidationError):
            UpperAssessmentComponent.objects.create(plan=plan, name="Midterm", component_type="midterm", weight=20)


class UNEBReadinessTests(TestCase):
    def test_preflight_requires_all_subject_ca_and_s3_project(self):
        year = AcademicYear.objects.create(name="2031", start_date=date(2031, 1, 1), end_date=date(2031, 12, 31))
        level = ClassLevel.objects.create(name="S4-2031", level=4, curriculum="lower")
        stream = Stream.objects.create(name="Candidate", class_level=level, academic_year=year)
        student = Student.objects.create(first_name="UNEB", last_name="Learner", gender="female", date_of_birth=date(2015, 1, 1), stream=stream)
        candidate = UNEBCandidate.objects.create(
            student=student, examination_level="uce", examination_year=2031,
            index_number="U0001/001", centre_number="U0001", gender="female", status="registered",
        )
        for index in range(8):
            subject = Subject.objects.create(name=f"Subject {index}", code=f"SUB{index}", curriculum_level="lower")
            UNEBCandidateSubject.objects.create(candidate=candidate, subject=subject, subject_code=f"S{index}")

        preflight = uneb_export_preflight("uce", 2031)

        self.assertFalse(preflight.ready)
        self.assertTrue(any("continuous assessment is missing" in error for error in preflight.errors))
        self.assertTrue(any("S3 project score is missing" in error for error in preflight.errors))

    def test_teacher_can_list_allocated_upper_results_api(self):
        year = AcademicYear.objects.create(name="2032", start_date=date(2032, 1, 1), end_date=date(2032, 12, 31))
        term = Term.objects.create(academic_year=year, name="Term III", number=3, start_date=date(2032, 9, 1), end_date=date(2032, 12, 1))
        level = ClassLevel.objects.create(name="S5-2032", level=16, curriculum="upper")
        stream = Stream.objects.create(name="A", class_level=level, academic_year=year)
        subject = Subject.objects.create(name="Advanced Physics", code="APHY", curriculum_level="upper")
        teacher = User.objects.create_user("allocated-upper-teacher", role="teacher")
        SubjectAllocation.objects.create(teacher=teacher, subject=subject, stream=stream, term=term)
        client = APIClient()
        client.force_authenticate(teacher)

        response = client.get("/api/exams/upper-subject-results/")

        self.assertEqual(response.status_code, 200)
