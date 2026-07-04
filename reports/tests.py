from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError

from academics.models import AcademicYear, ClassLevel, Department, Stream, Subject, SubjectAllocation, Term
from assessments.models import (
    Assessment, AssessmentPolicy, AssessmentResult, AssessmentScale, AssessmentType, CompetencyLevel,
    CurriculumFramework, CurriculumTopic, CurriculumValue, LearnerSkillRating,
    LearnerValueRating, LearningOutcome, LearningOutcomeAssessment, PortfolioItem, Skill,
)
from accounts.models import User
from students.models import Enrollment, Student
from .models import ReportCard, ReportLearningOutcomeRating
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

    def test_parent_can_view_only_their_learner_growth_profile(self):
        year = AcademicYear.objects.create(name="2027", start_date=date(2027, 1, 1), end_date=date(2027, 12, 31))
        level = ClassLevel.objects.create(name="S2", level=2, curriculum="lower")
        stream = Stream.objects.create(name="A", class_level=level, academic_year=year)
        parent = User.objects.create_user("growth-parent", role="parent")
        linked = Student.objects.create(first_name="Linked", last_name="Growth", gender="female", date_of_birth=date(2013, 1, 1), stream=stream, parent=parent)
        other = Student.objects.create(first_name="Other", last_name="Growth", gender="male", date_of_birth=date(2013, 1, 1), stream=stream)
        self.client.force_login(parent)
        self.assertEqual(self.client.get(reverse("reports:growth-profile", args=[linked.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("reports:growth-profile", args=[other.pk])).status_code, 404)


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
        scale = AssessmentScale.objects.create(name="Report scale", code="REPORT", is_default=True)
        proficiency = CompetencyLevel.objects.create(scale=scale, name="Proficient", code="PRO-REPORT", numeric_value=3)
        policy = AssessmentPolicy.objects.create(
            name="CBC evidence", academic_year=year, class_level=level, curriculum_stage="lower",
            achievement_scale=scale, ongoing_weight=100, summative_weight=0, summative_frequency="none",
        )
        kind = AssessmentType.objects.create(name="Project", category="project", weight=100)
        assessment = Assessment.objects.create(title="Garden project", assessment_type=kind, term=term, subject=subject, stream=stream, status="published")
        AssessmentResult.objects.create(assessment=assessment, student=student, score=80)
        framework = CurriculumFramework.objects.create(name="Lower 2029", stage="lower")
        topic = CurriculumTopic.objects.create(framework=framework, subject=subject, class_level=level, term_number=1, title="Soil", sequence=1)
        outcome = LearningOutcome.objects.create(topic=topic, statement="Select suitable soil for a crop.")
        LearningOutcomeAssessment.objects.create(student=student, outcome=outcome, term=term, assessment=assessment, scale_level=proficiency, assessed_by=teacher)
        skill = Skill.objects.create(name="Research Skills")
        value = CurriculumValue.objects.create(name="Responsibility", is_assessed=True)
        LearnerSkillRating.objects.create(student=student, skill=skill, term=term, subject=subject, assessment=assessment, level=proficiency, assessed_by=teacher)
        LearnerValueRating.objects.create(student=student, value=value, term=term, subject=subject, assessment=assessment, level=proficiency, assessed_by=teacher)
        PortfolioItem.objects.create(student=student, term=term, stream=stream, subject=subject, category="project", title="Garden record", status="verified", uploaded_by=teacher, verified_by=teacher)

        card = generate_report_card(student, term, teacher, policy)

        self.assertEqual(card.learning_outcome_ratings.get().scale_level, proficiency)
        self.assertEqual(card.skill_ratings.get().skill, skill)
        self.assertEqual(card.value_ratings.get().value, value)
        self.assertIn("Project: 1", card.portfolio_summary)
        card.status = "published"
        card.save()
        transcript = generate_academic_transcript(student, teacher)
        self.assertEqual(transcript.entries.get().score, card.subject_results.get().final_score)
        self.assertTrue(build_report_pdf_bytes(card).startswith(b"%PDF"))
        self.assertTrue(build_transcript_pdf_bytes(transcript).startswith(b"%PDF"))

    def test_legacy_learning_outcome_rating_label_is_rendered(self):
        rating = ReportLearningOutcomeRating(level="met")
        self.assertEqual(rating.display_level, "Met expectation")


class HistoricalReportTests(TestCase):
    def test_report_uses_academic_year_enrolment_after_promotion(self):
        old_year = AcademicYear.objects.create(name="2033", start_date=date(2033, 1, 1), end_date=date(2033, 12, 31))
        new_year = AcademicYear.objects.create(name="2034", start_date=date(2034, 1, 1), end_date=date(2034, 12, 31), is_current=True)
        term = Term.objects.create(academic_year=old_year, name="Term III", number=3, start_date=date(2033, 9, 1), end_date=date(2033, 12, 1))
        s1 = ClassLevel.objects.create(name="Historical S1", level=21, curriculum="lower")
        s2 = ClassLevel.objects.create(name="Historical S2", level=22, curriculum="lower")
        old_stream = Stream.objects.create(name="Old", class_level=s1, academic_year=old_year)
        new_stream = Stream.objects.create(name="New", class_level=s2, academic_year=new_year)
        student = Student.objects.create(first_name="Promoted", last_name="Learner", gender="male", date_of_birth=date(2020, 1, 1), stream=old_stream)
        Enrollment.objects.create(student=student, academic_year=old_year, stream=old_stream)
        teacher = User.objects.create_user("historical-teacher", role="teacher")
        subject = Subject.objects.create(name="Historical English", code="HENG", curriculum_level="lower")
        SubjectAllocation.objects.create(teacher=teacher, subject=subject, stream=old_stream, term=term)
        policy = AssessmentPolicy.objects.create(
            name="Historical policy", academic_year=old_year, class_level=s1,
            curriculum_stage="lower", ongoing_weight=100, summative_weight=0,
            summative_frequency="none",
        )
        kind = AssessmentType.objects.create(name="Historical task", category="project", weight=100)
        assessment = Assessment.objects.create(title="Old class task", assessment_type=kind, term=term, subject=subject, stream=old_stream, status="published")
        AssessmentResult.objects.create(assessment=assessment, student=student, score=75)
        student.stream = new_stream
        student.save()

        card = generate_report_card(student, term, teacher, policy)

        self.assertEqual(card.stream, old_stream)
        self.assertEqual(card.subject_results.get(subject=subject).final_score, 75)
