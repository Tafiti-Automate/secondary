from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from academics.models import AcademicYear, ClassLevel, Department, Stream, Subject, SubjectAllocation, Term
from accounts.models import User
from students.models import Student
from .models import (
    Assessment, AssessmentPolicy, AssessmentResult, AssessmentType, CompetencyLevel,
    CurriculumFramework, CurriculumTopic, CurriculumValue, LearnerSkillRating,
    LearnerValueRating, LearningOutcome, LearningOutcomeAssessment, LessonPlan,
    PortfolioItem, SchemeOfWork, SchemeWeek, Skill, TeacherObservation,
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


class CBCEvidencePortalTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(name="2028", start_date=date(2028, 1, 1), end_date=date(2028, 12, 31), is_current=True)
        self.term = Term.objects.create(academic_year=self.year, name="Term I", number=1, start_date=date(2028, 1, 10), end_date=date(2028, 4, 10), is_current=True)
        self.level = ClassLevel.objects.create(name="S3", level=3, curriculum="lower")
        self.stream = Stream.objects.create(name="North", class_level=self.level, academic_year=self.year)
        self.teacher = User.objects.create_user("cbc-teacher", role="teacher", password="pass")
        self.parent = User.objects.create_user("cbc-parent", role="parent", password="pass")
        self.student_user = User.objects.create_user("cbc-student", role="student", password="pass")
        department = Department.objects.create(name="CBC Sciences", head=self.teacher)
        self.subject = Subject.objects.create(name="Integrated Science", code="SCI-CBC", department=department, curriculum_level="lower")
        SubjectAllocation.objects.create(teacher=self.teacher, subject=self.subject, stream=self.stream, term=self.term)
        self.student = Student.objects.create(
            user=self.student_user, parent=self.parent, first_name="Mirembe", last_name="Ayo",
            gender="female", date_of_birth=date(2013, 5, 1), stream=self.stream,
        )
        framework = CurriculumFramework.objects.create(name="CBC Portal 2028", stage="lower")
        topic = CurriculumTopic.objects.create(framework=framework, subject=self.subject, class_level=self.level, term_number=1, title="Living things", sequence=1)
        self.value = CurriculumValue.objects.create(name="Responsibility", is_assessed=True)
        self.outcome = LearningOutcome.objects.create(topic=topic, statement="Classify living things accurately.", assessment_criteria="Uses observable features")
        self.outcome.values.add(self.value)
        self.skill = Skill.objects.create(name="Observation skill")
        self.level_rating = CompetencyLevel.objects.create(name="Proficient", code="P", numeric_value=3)
        kind = AssessmentType.objects.create(name="Field observation", category="fieldwork", weight=20)
        self.assessment = Assessment.objects.create(
            title="School garden survey", assessment_type=kind, term=self.term, subject=self.subject,
            stream=self.stream, topic=topic, status="published", created_by=self.teacher,
        )
        self.assessment.learning_outcomes.add(self.outcome)

    def test_teacher_records_all_cbc_evidence_categories(self):
        self.client.force_login(self.teacher)
        url = reverse("assessments:cbc-evidence", args=[self.assessment.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"section": "outcomes", f"rating_{self.student.pk}_{self.outcome.pk}": "met"})
        self.assertRedirects(response, f"{url}?section=outcomes")
        self.client.post(url, {"section": "skills", f"rating_{self.student.pk}_{self.skill.pk}": self.level_rating.pk})
        self.client.post(url, {"section": "values", f"rating_{self.student.pk}_{self.value.pk}": self.level_rating.pk})
        self.assertTrue(LearningOutcomeAssessment.objects.filter(assessment=self.assessment, student=self.student, level="met").exists())
        self.assertTrue(LearnerSkillRating.objects.filter(assessment=self.assessment, student=self.student, skill=self.skill).exists())
        self.assertTrue(LearnerValueRating.objects.filter(assessment=self.assessment, student=self.student, value=self.value).exists())

    def test_unallocated_teacher_cannot_open_cbc_workspace(self):
        outsider = User.objects.create_user("cbc-outsider", role="teacher", password="pass")
        self.client.force_login(outsider)
        response = self.client.get(reverse("assessments:cbc-evidence", args=[self.assessment.pk]))
        self.assertEqual(response.status_code, 404)

    def test_observation_and_portfolio_verification_workflow(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse("assessments:portfolio-list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("assessments:portfolio-add")).status_code, 200)
        observation_response = self.client.post(reverse("assessments:observation-add"), {
            "student": self.student.pk, "term": self.term.pk, "subject": self.subject.pk,
            "assessment": self.assessment.pk, "category": "participation",
            "observation_date": date(2028, 2, 1), "note": "Explained the classification choices clearly.",
        })
        self.assertEqual(observation_response.status_code, 302)
        self.assertTrue(TeacherObservation.objects.filter(student=self.student, observed_by=self.teacher).exists())

        self.client.force_login(self.student_user)
        create_response = self.client.post(reverse("assessments:portfolio-add"), {
            "student": self.student.pk, "term": self.term.pk, "subject": self.subject.pk,
            "assessment": self.assessment.pk, "learning_outcome": self.outcome.pk,
            "category": "project", "title": "Garden classification chart",
            "description": "A chart grouping plants and animals observed in the school garden.",
            "reflection_notes": "I improved how I use visible features to classify organisms.",
        })
        self.assertEqual(create_response.status_code, 302)
        item = PortfolioItem.objects.get(student=self.student)
        self.assertEqual(item.status, "submitted")

        self.client.force_login(self.parent)
        self.assertEqual(self.client.get(reverse("assessments:portfolio-detail", args=[item.pk])).status_code, 404)

        self.client.force_login(self.teacher)
        verify_response = self.client.post(reverse("assessments:portfolio-workflow", args=[item.pk, "verify"]), {"teacher_feedback": "Clear, relevant evidence."})
        self.assertRedirects(verify_response, reverse("assessments:portfolio-detail", args=[item.pk]))
        item.refresh_from_db()
        self.assertEqual(item.status, "verified")
        self.assertEqual(item.verified_by, self.teacher)

        self.client.force_login(self.parent)
        self.assertEqual(self.client.get(reverse("assessments:portfolio-detail", args=[item.pk])).status_code, 200)
