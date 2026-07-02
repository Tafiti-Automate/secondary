from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError

from academics.models import AcademicYear, ClassLevel, Department, Stream, Subject, SubjectAllocation, Term
from assessments.models import (
    Assessment, AssessmentPolicy, AssessmentResult, AssessmentType, CompetencyLevel,
    CurriculumFramework, CurriculumTopic, CurriculumValue, LearnerSkillRating,
    LearnerValueRating, LearningOutcome, LearningOutcomeAssessment, PortfolioItem, Skill,
)
from accounts.models import User
from students.models import Student
from .models import ReportCard
from .services import generate_academic_transcript, generate_report_card
from .views import build_report_pdf_bytes, build_transcript_pdf_bytes


class ReportVisibilityTests(TestCase):
    def test_parent_cannot_view_draft_report(self):
        year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        term = Term.objects.create(academic_year=year, name="Term I", number=1, start_date=date(2026, 1, 1), end_date=date(2026, 4, 1))
        level = ClassLevel.objects.create(name="S1", level=1, curriculum="lower")
        stream = Stream.objects.create(name="A", class_level=level, academic_year=year)
        parent = User.objects.create_user("parent", role="parent")
        student = Student.objects.create(first_name="A", last_name="B", gender="female", date_of_birth=date(2012, 1, 1), stream=stream, parent=parent)
        card = ReportCard.objects.create(student=student, term=term, stream=stream, status="draft")
        self.client.force_login(parent)
        self.assertEqual(self.client.get(reverse("reports:detail", args=[card.pk])).status_code, 404)

    def test_parent_can_view_published_report(self):
        year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        term = Term.objects.create(academic_year=year, name="Term I", number=1, start_date=date(2026, 1, 1), end_date=date(2026, 4, 1))
        level = ClassLevel.objects.create(name="S1", level=1, curriculum="lower")
        stream = Stream.objects.create(name="A", class_level=level, academic_year=year)
        parent = User.objects.create_user("parent", role="parent")
        student = Student.objects.create(first_name="A", last_name="B", gender="female", date_of_birth=date(2012, 1, 1), stream=stream, parent=parent)
        card = ReportCard.objects.create(student=student, term=term, stream=stream, status="published")
        self.client.force_login(parent)
        self.assertEqual(self.client.get(reverse("reports:detail", args=[card.pk])).status_code, 200)


class MissingEvidenceTests(TestCase):
    def test_missing_evidence_is_not_converted_to_zero(self):
        year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        term = Term.objects.create(academic_year=year, name="Term I", number=1, start_date=date(2026, 1, 1), end_date=date(2026, 4, 1))
        level = ClassLevel.objects.create(name="S1", level=1, curriculum="lower")
        stream = Stream.objects.create(name="A", class_level=level, academic_year=year)
        teacher = User.objects.create_user("teacher", role="teacher")
        subject = Subject.objects.create(name="English", code="ENG", department=Department.objects.create(name="Languages"))
        SubjectAllocation.objects.create(teacher=teacher, subject=subject, stream=stream, term=term)
        student = Student.objects.create(first_name="A", last_name="B", gender="female", date_of_birth=date(2012, 1, 1), stream=stream)
        policy = AssessmentPolicy.objects.create(name="Internal", academic_year=year, class_level=level, curriculum_stage="lower", summative_frequency="termly")
        card = generate_report_card(student, term, teacher, policy)
        result = card.subject_results.get(subject=subject)
        self.assertIsNone(result.final_score)
        self.assertTrue(card.has_missing_marks)
        with self.assertRaises(ValidationError):
            card.publish()


class CompetencyReportTests(TestCase):
    def test_report_compiles_outcomes_skills_values_portfolio_and_transcript(self):
        year = AcademicYear.objects.create(name="2029", start_date=date(2029, 1, 1), end_date=date(2029, 12, 31))
        term = Term.objects.create(academic_year=year, name="Term I", number=1, start_date=date(2029, 1, 10), end_date=date(2029, 4, 10))
        level = ClassLevel.objects.create(name="S3", level=3, curriculum="lower")
        stream = Stream.objects.create(name="A", class_level=level, academic_year=year)
        teacher = User.objects.create_user("report-teacher", role="teacher")
        subject = Subject.objects.create(name="Agriculture", code="AGR", curriculum_level="lower", department=Department.objects.create(name="Agriculture"))
        SubjectAllocation.objects.create(teacher=teacher, subject=subject, stream=stream, term=term)
        student = Student.objects.create(first_name="Lydia", last_name="Auma", gender="female", date_of_birth=date(2012, 1, 1), stream=stream)
        policy = AssessmentPolicy.objects.create(
            name="CBC evidence", academic_year=year, class_level=level, curriculum_stage="lower",
            ongoing_weight=100, summative_weight=0, summative_frequency="none",
        )
        kind = AssessmentType.objects.create(name="Project", category="project", weight=100)
        assessment = Assessment.objects.create(title="Garden project", assessment_type=kind, term=term, subject=subject, stream=stream, status="published")
        AssessmentResult.objects.create(assessment=assessment, student=student, score=80)
        framework = CurriculumFramework.objects.create(name="Lower 2029", stage="lower")
        topic = CurriculumTopic.objects.create(framework=framework, subject=subject, class_level=level, term_number=1, title="Soil", sequence=1)
        outcome = LearningOutcome.objects.create(topic=topic, statement="Select suitable soil for a crop.")
        LearningOutcomeAssessment.objects.create(student=student, outcome=outcome, term=term, assessment=assessment, level="met", assessed_by=teacher)
        proficiency = CompetencyLevel.objects.create(name="Proficient", code="PRO-REPORT", numeric_value=3)
        skill = Skill.objects.create(name="Research Skills")
        value = CurriculumValue.objects.create(name="Responsibility", is_assessed=True)
        LearnerSkillRating.objects.create(student=student, skill=skill, term=term, subject=subject, assessment=assessment, level=proficiency, assessed_by=teacher)
        LearnerValueRating.objects.create(student=student, value=value, term=term, subject=subject, assessment=assessment, level=proficiency, assessed_by=teacher)
        PortfolioItem.objects.create(student=student, term=term, stream=stream, subject=subject, category="project", title="Garden record", status="verified", uploaded_by=teacher, verified_by=teacher)

        card = generate_report_card(student, term, teacher, policy)

        self.assertEqual(card.learning_outcome_ratings.get().level, "met")
        self.assertEqual(card.skill_ratings.get().skill, skill)
        self.assertEqual(card.value_ratings.get().value, value)
        self.assertIn("Project: 1", card.portfolio_summary)
        card.status = "published"
        card.save()
        transcript = generate_academic_transcript(student, teacher)
        self.assertEqual(transcript.entries.get().score, card.subject_results.get().final_score)
        self.assertTrue(build_report_pdf_bytes(card).startswith(b"%PDF"))
        self.assertTrue(build_transcript_pdf_bytes(transcript).startswith(b"%PDF"))
