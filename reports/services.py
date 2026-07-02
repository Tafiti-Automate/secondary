from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count

from assessments.models import (
    AssessmentPolicy, AssessmentResult, CompetencyAssessment, LearnerSkillRating,
    LearnerValueRating, LearningOutcomeAssessment, PortfolioItem,
)
from assessments.services import continuous_assessment_score
from attendance.models import AttendanceRecord
from exams.models import ExaminationResult, GradeBoundary, UpperSubjectResult
from students.models import Student
from .models import (
    AcademicTranscript, ReportCard, ReportCompetencyRating, ReportLearningOutcomeRating,
    ReportSkillRating, ReportSubjectResult, ReportValueRating, TranscriptEntry,
)


def grade_for(score, scale=None):
    if score is None:
        return None
    boundaries = GradeBoundary.objects.filter(is_deleted=False, minimum_score__lte=score, maximum_score__gte=score)
    boundaries = boundaries.filter(scale=scale) if scale else boundaries.filter(scale__isnull=True)
    return boundaries.order_by("-minimum_score").first()


def resolve_policy(student, term, policy=None):
    if policy:
        if policy.academic_year_id != term.academic_year_id:
            raise ValidationError("Assessment policy and term must belong to the same academic year.")
        if policy.class_level_id and student.stream and policy.class_level_id != student.stream.class_level_id:
            raise ValidationError("Assessment policy does not match the learner's class level.")
        return policy
    if not student.stream_id:
        raise ValidationError("Student must have a current stream before report generation.")
    policy = AssessmentPolicy.objects.filter(academic_year=term.academic_year, class_level=student.stream.class_level, is_active=True, is_deleted=False, purpose="internal").first()
    if not policy:
        raise ValidationError(f"No active internal assessment policy is configured for {student.stream.class_level}.")
    return policy


@transaction.atomic
def generate_report_card(student, term, user, policy=None):
    policy = resolve_policy(student, term, policy)
    card, _ = ReportCard.objects.get_or_create(
        student=student, term=term,
        defaults={"stream": student.stream, "generated_by": user, "assessment_policy": policy},
    )
    if card.status == "locked":
        return card
    card.stream, card.generated_by, card.assessment_policy = student.stream, user, policy
    card.ca_weight, card.exam_weight = policy.ongoing_weight, policy.summative_weight

    subject_ids = set(student.stream.subject_allocations.filter(term=term, is_deleted=False).values_list("subject_id", flat=True)) if student.stream else set()
    enrollment = student.enrollments.filter(academic_year=term.academic_year, is_deleted=False).first()
    if enrollment:
        subject_ids.update(enrollment.subject_registrations.filter(status="active", is_deleted=False).values_list("subject_id", flat=True))
    subject_ids.update(student.exam_results.filter(examination__term=term, is_deleted=False).values_list("examination__subject_id", flat=True))
    subject_ids.update(student.assessment_results.filter(assessment__term=term, is_deleted=False).values_list("assessment__subject_id", flat=True))

    from academics.models import Subject
    missing_count = 0
    for subject in Subject.objects.filter(pk__in=subject_ids):
        ongoing_qs = AssessmentResult.objects.filter(student=student, assessment__subject=subject, assessment__term=term, assessment__status__in=("published", "closed", "moderated"), is_deleted=False)
        ongoing_available = ongoing_qs.exists()
        ongoing = continuous_assessment_score(student, subject, term, student.stream) if ongoing_available else Decimal("0.00")
        exam_result = ExaminationResult.objects.filter(student=student, examination__term=term, examination__subject=subject, examination__status__in=("approved", "published", "locked"), is_deleted=False).select_related("examination__session__grade_scale").order_by("-examination__exam_date", "-pk").first()
        summative_available = bool(exam_result)
        summative_required = policy.summative_frequency == "termly" or (policy.summative_frequency == "annual" and term.number == 3)
        exam = exam_result.percentage if exam_result else Decimal("0.00")
        complete = ongoing_available and (summative_available or not summative_required)
        if complete:
            if summative_required:
                final = ((ongoing * policy.ongoing_weight / 100) + (exam * policy.summative_weight / 100)).quantize(Decimal("0.01"))
            else:
                final = ongoing
        else:
            final = None
            missing_count += 1
        scale = exam_result.examination.session.grade_scale if exam_result and exam_result.examination.session_id else None
        boundary = grade_for(final, scale)
        reasons = []
        if not ongoing_available:
            reasons.append("No ongoing assessment evidence")
        if summative_required and not summative_available:
            reasons.append("Required summative result missing")
        ReportSubjectResult.objects.update_or_create(
            report_card=card, subject=subject,
            defaults={
                "continuous_assessment_score": ongoing, "examination_score": exam, "final_score": final,
                "grade": boundary.grade if boundary else "", "points": boundary.points if boundary else None,
                "descriptor": (boundary.descriptor or boundary.description) if boundary else "",
                "teacher_remark": exam_result.teacher_remark if exam_result else "",
                "ongoing_available": ongoing_available, "summative_available": summative_available,
                "summative_required": summative_required, "missing_reason": "; ".join(reasons), "is_deleted": False,
            },
        )
    results = card.subject_results.filter(is_deleted=False, final_score__isnull=False)
    card.total_score = sum((result.final_score for result in results), Decimal("0"))
    card.average_score = (card.total_score / results.count()).quantize(Decimal("0.01")) if results.exists() else Decimal("0")
    card.has_missing_marks, card.missing_mark_count = bool(missing_count), missing_count
    attendance = AttendanceRecord.objects.filter(student=student, session__term=term, session__session_type="daily", is_deleted=False).values("status").annotate(total=Count("id"))
    attendance_map = {item["status"]: item["total"] for item in attendance}
    card.attendance_present = attendance_map.get("present", 0)
    card.attendance_absent = attendance_map.get("absent", 0) + attendance_map.get("sick", 0) + attendance_map.get("excused", 0)
    card.attendance_late = attendance_map.get("late", 0)
    card.class_size = Student.objects.filter(stream=student.stream, is_deleted=False, is_active=True).count() if student.stream else 0
    if not policy.show_class_position:
        card.class_position = None
    card.save()
    competency_ids = CompetencyAssessment.objects.filter(student=student, assessment__term=term, is_deleted=False, scale_level__isnull=False).values_list("competency_id", flat=True).distinct()
    for competency_id in competency_ids:
        latest = CompetencyAssessment.objects.filter(student=student, assessment__term=term, competency_id=competency_id, is_deleted=False, scale_level__isnull=False).select_related("scale_level", "competency").order_by("-created_at").first()
        ReportCompetencyRating.objects.update_or_create(report_card=card, competency=latest.competency, defaults={"level": latest.scale_level, "comment": latest.comment, "is_deleted": False})

    outcome_ids = LearningOutcomeAssessment.objects.filter(student=student, term=term, is_deleted=False).values_list("outcome_id", flat=True).distinct()
    card.learning_outcome_ratings.filter(is_deleted=False).exclude(outcome_id__in=outcome_ids).update(is_deleted=True)
    for outcome_id in outcome_ids:
        latest = LearningOutcomeAssessment.objects.filter(student=student, term=term, outcome_id=outcome_id, is_deleted=False).select_related("outcome").order_by("-assessed_at", "-pk").first()
        ReportLearningOutcomeRating.objects.update_or_create(
            report_card=card,
            outcome=latest.outcome,
            defaults={"level": latest.level, "comment": latest.comment[:180], "is_deleted": False},
        )

    skill_ids = LearnerSkillRating.objects.filter(student=student, term=term, is_deleted=False).values_list("skill_id", flat=True).distinct()
    card.skill_ratings.filter(is_deleted=False).exclude(skill_id__in=skill_ids).update(is_deleted=True)
    for skill_id in skill_ids:
        latest = LearnerSkillRating.objects.filter(student=student, term=term, skill_id=skill_id, is_deleted=False).select_related("skill", "level").order_by("-assessed_at", "-pk").first()
        ReportSkillRating.objects.update_or_create(
            report_card=card,
            skill=latest.skill,
            defaults={"level": latest.level, "comment": latest.comment[:180], "is_deleted": False},
        )

    value_ids = LearnerValueRating.objects.filter(student=student, term=term, is_deleted=False).values_list("value_id", flat=True).distinct()
    card.value_ratings.filter(is_deleted=False).exclude(value_id__in=value_ids).update(is_deleted=True)
    for value_id in value_ids:
        latest = LearnerValueRating.objects.filter(student=student, term=term, value_id=value_id, is_deleted=False).select_related("value", "level").order_by("-assessed_at", "-pk").first()
        ReportValueRating.objects.update_or_create(
            report_card=card,
            value=latest.value,
            defaults={"level": latest.level, "comment": latest.comment[:180], "is_deleted": False},
        )

    portfolio = PortfolioItem.objects.filter(student=student, term=term, status="verified", is_deleted=False)
    category_counts = portfolio.values("category").annotate(total=Count("id")).order_by("category")
    if category_counts:
        labels = dict(PortfolioItem.CATEGORY_CHOICES)
        card.portfolio_summary = "; ".join(f"{labels.get(item['category'], item['category'])}: {item['total']}" for item in category_counts)
    else:
        card.portfolio_summary = "No verified portfolio evidence for this term."
    card.save(update_fields=["portfolio_summary", "updated_at"])
    return card


@transaction.atomic
def generate_stream_reports(stream, term, user, policy=None):
    policy = policy or AssessmentPolicy.objects.filter(academic_year=term.academic_year, class_level=stream.class_level, purpose="internal", is_active=True, is_deleted=False).first()
    if not policy:
        raise ValidationError(f"Configure an internal assessment policy for {stream.class_level} first.")
    cards = [generate_report_card(student, term, user, policy) for student in Student.objects.filter(stream=stream, is_deleted=False, is_active=True)]
    if policy.show_class_position:
        rankable = sorted([card for card in cards if not card.has_missing_marks], key=lambda card: card.average_score, reverse=True)
        for position, card in enumerate(rankable, 1):
            card.class_position = position
            card.class_size = len(cards)
            card.save(update_fields=["class_position", "class_size", "updated_at"])
    return cards


@transaction.atomic
def generate_academic_transcript(student, user, purpose=""):
    """Create a draft transcript from published/locked reports and processed upper-secondary results."""
    transcript = AcademicTranscript.objects.create(student=student, issued_by=user, purpose=purpose)
    entry_count = 0
    cards = ReportCard.objects.filter(student=student, status__in=("published", "locked"), is_deleted=False).select_related("term__academic_year", "stream__class_level")
    for card in cards:
        for result in card.subject_results.filter(is_deleted=False, final_score__isnull=False).select_related("subject"):
            TranscriptEntry.objects.update_or_create(
                transcript=transcript,
                academic_year=card.term.academic_year,
                term=card.term,
                subject=result.subject,
                defaults={
                    "class_level": card.stream.class_level,
                    "score": result.final_score,
                    "grade": result.grade,
                    "points": result.points,
                    "remark": result.descriptor or result.teacher_remark,
                    "is_deleted": False,
                },
            )
            entry_count += 1

    upper_results = UpperSubjectResult.objects.filter(
        student=student,
        status__in=("approved", "locked"),
        has_missing_components=False,
        is_deleted=False,
    ).select_related("plan__subject", "plan__academic_year", "plan__class_level", "term")
    for result in upper_results:
        TranscriptEntry.objects.update_or_create(
            transcript=transcript,
            academic_year=result.plan.academic_year,
            term=result.term,
            subject=result.plan.subject,
            defaults={
                "class_level": result.plan.class_level,
                "score": result.total_score,
                "grade": result.grade,
                "points": result.points,
                "remark": result.remark,
                "is_deleted": False,
            },
        )
        entry_count += 1

    if not entry_count:
        raise ValidationError("No approved or published academic results are available for this learner.")
    return transcript
