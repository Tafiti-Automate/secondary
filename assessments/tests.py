from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from academics.models import AcademicYear, ClassLevel, Department, Stream, Subject, SubjectAllocation, Term
from accounts.models import User
from students.models import Student
from .models import (
    Assessment, AssessmentPolicy, AssessmentResult, AssessmentType, CurriculumFramework,
    CurriculumTopic, LearningOutcome, LessonPlan, SchemeOfWork, SchemeWeek,
)
from .services import continuous_assessment_score


class AssessmentTests(TestCase):
    def setUp(self):
        year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        self.term = Term.objects.create(academic_year=year, name="Term I", number=1, start_date=date(2026, 1, 1), end_date=date(2026, 4, 1))
        level = ClassLevel.objects.create(name="S1", level=1, curriculum="lower")
        self.stream = Stream.objects.create(name="A", class_level=level, academic_year=year)
        department = Department.objects.create(name="Languages")
        self.subject = Subject.objects.create(name="English", code="ENG", department=department)
        self.teacher = User.objects.create_user("teacher", role="teacher")
        self.student = Student.objects.create(first_name="A", last_name="B", gender="female", date_of_birth=date(2012, 1, 1), stream=self.stream)
        self.kind = AssessmentType.objects.create(name="Test", category="test", weight=20)
        self.assessment = Assessment.objects.create(title="Test 1", assessment_type=self.kind, term=self.term, subject=self.subject, stream=self.stream, max_score=50, status="published", created_by=self.teacher)

    def test_score_cannot_exceed_maximum(self):
        with self.assertRaises(ValidationError):
            AssessmentResult.objects.create(assessment=self.assessment, student=self.student, score=51)

    def test_weighted_score_uses_percentages(self):
        AssessmentResult.objects.create(assessment=self.assessment, student=self.student, score=40)
        self.assertEqual(continuous_assessment_score(self.student, self.subject, self.term), Decimal("80.00"))

    def test_unallocated_teacher_cannot_see_assessment_api(self):
        other_teacher = User.objects.create_user("other", role="teacher")
        client = APIClient()
        client.force_authenticate(other_teacher)
        response = client.get("/api/assessments/assessments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_advanced_summative_must_be_annual(self):
        advanced = ClassLevel.objects.create(name="S5", level=5, curriculum="upper")
        stream = Stream.objects.create(name="A", class_level=advanced, academic_year=self.term.academic_year)
        with self.assertRaises(ValidationError):
            Assessment.objects.create(title="Invalid term exam", assessment_type=self.kind, term=self.term, subject=self.subject, stream=stream, is_summative=True, assessment_period="end_topic")

    def test_advanced_policy_rejects_termly_summative(self):
        advanced = ClassLevel.objects.create(name="S5", level=5, curriculum="upper")
        with self.assertRaises(ValidationError):
            AssessmentPolicy.objects.create(name="Invalid", academic_year=self.term.academic_year, class_level=advanced, curriculum_stage="advanced", summative_frequency="termly")


class PlanningAndModerationTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(name="2027", start_date=date(2027, 1, 1), end_date=date(2027, 12, 31))
        self.term = Term.objects.create(academic_year=self.year, name="Term I", number=1, start_date=date(2027, 1, 15), end_date=date(2027, 4, 15))
        self.level = ClassLevel.objects.create(name="S2", level=2, curriculum="lower")
        self.stream = Stream.objects.create(name="A", class_level=self.level, academic_year=self.year)
        self.hod = User.objects.create_user("hod", role="teacher")
        self.dos = User.objects.create_user("workflow-dos", role="director_of_studies")
        department = Department.objects.create(name="Sciences", head=self.hod)
        self.subject = Subject.objects.create(name="Biology", code="BIO", department=department, curriculum_level="lower")
        self.allocation = SubjectAllocation.objects.create(teacher=self.hod, subject=self.subject, stream=self.stream, term=self.term)
        self.framework = CurriculumFramework.objects.create(name="Lower CBC 2027", stage="lower")
        self.topic = CurriculumTopic.objects.create(framework=self.framework, subject=self.subject, class_level=self.level, term_number=1, title="Cells", sequence=1)
        self.outcome = LearningOutcome.objects.create(topic=self.topic, statement="Describe and draw cells.", assessment_criteria="Accurate labels", required_evidence="Labelled cell drawing")
        self.student = Student.objects.create(first_name="Ada", last_name="Naki", gender="female", date_of_birth=date(2013, 1, 1), stream=self.stream)

    def test_scheme_and_lesson_plan_validate_allocation_context(self):
        scheme = SchemeOfWork.objects.create(allocation=self.allocation, prepared_by=self.hod)
        week = SchemeWeek.objects.create(scheme=scheme, week_number=1, topic=self.topic, start_date=date(2027, 1, 18), end_date=date(2027, 1, 22))
        week.learning_outcomes.add(self.outcome)
        lesson = LessonPlan.objects.create(
            allocation=self.allocation,
            scheme_week=week,
            title="Introducing cells",
            lesson_date=date(2027, 1, 19),
            topic=self.topic,
            objectives="Identify the main parts of a cell.",
            teaching_activities="Demonstration and questioning.",
            learner_activities="Observe, discuss and draw.",
            assessment_method="Check labelled drawings.",
            prepared_by=self.hod,
        )
        self.assertEqual(lesson.scheme_week, week)
        lesson.lesson_date = date(2027, 5, 1)
        with self.assertRaises(ValidationError):
            lesson.save()

    def test_dos_approval_makes_assessment_evidence_read_only(self):
        kind = AssessmentType.objects.create(name="Practical", category="practical", weight=100)
        assessment = Assessment.objects.create(
            title="Cell practical", assessment_type=kind, term=self.term, subject=self.subject,
            stream=self.stream, topic=self.topic, created_by=self.hod,
        )
        result = AssessmentResult.objects.create(assessment=assessment, student=self.student, score=75)
        assessment.transition("submit", self.hod)
        assessment.transition("hod_approve", self.hod, "Evidence checked.")
        assessment.transition("dos_approve", self.dos, "Approved for reporting.")
        self.assertTrue(assessment.is_workflow_locked)
        self.assertEqual(assessment.reviews.count(), 2)
        result.score = 80
        with self.assertRaises(ValidationError):
            result.save()
