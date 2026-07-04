from collections import defaultdict

from django.db.models import Avg, Count, Q

from assessments.models import CompetencyAssessment, LearnerSkillRating, LearningOutcomeAssessment
from attendance.models import AttendanceRecord
from .models import ReportCard


def learner_growth_profile(student):
    """Build longitudinal, curriculum-referenced series without flattening evidence into one mark."""
    outcomes = LearningOutcomeAssessment.objects.filter(
        student=student, is_deleted=False,
    ).select_related("term__academic_year", "outcome__topic__subject", "scale_level").order_by(
        "term__academic_year__start_date", "term__number", "assessed_at",
    )
    outcome_series = defaultdict(list)
    for item in outcomes:
        value = item.scale_level.numeric_value if item.scale_level_id else None
        cohort_average = LearningOutcomeAssessment.objects.filter(
            outcome=item.outcome,
            term=item.term,
            scale_level__isnull=False,
            is_deleted=False,
        ).aggregate(value=Avg("scale_level__numeric_value"))["value"]
        outcome_series[item.outcome].append({
            "term": str(item.term),
            "level": item.display_level,
            "value": value,
            "cohort_average": round(float(cohort_average), 2) if cohort_average is not None else None,
            "comment": item.comment,
        })

    competencies = CompetencyAssessment.objects.filter(
        student=student, scale_level__isnull=False, is_deleted=False,
    ).select_related("assessment__term__academic_year", "competency", "scale_level").order_by(
        "assessment__term__academic_year__start_date", "assessment__term__number",
    )
    competency_series = defaultdict(list)
    for item in competencies:
        competency_series[item.competency].append({
            "term": str(item.assessment.term),
            "level": item.scale_level.name,
            "value": item.scale_level.numeric_value,
        })

    skills = LearnerSkillRating.objects.filter(
        student=student, is_deleted=False,
    ).select_related("term__academic_year", "skill", "level").order_by(
        "term__academic_year__start_date", "term__number", "assessed_at",
    )
    skill_series = defaultdict(list)
    for item in skills:
        skill_series[item.skill].append({
            "term": str(item.term), "level": item.level.name, "value": item.level.numeric_value,
        })

    reports = ReportCard.objects.filter(
        student=student, status__in=("published", "locked"), has_missing_marks=False, is_deleted=False,
    ).select_related("term__academic_year", "stream").order_by("term__academic_year__start_date", "term__number")
    attainment = [{
        "term": str(card.term), "average": float(card.average_score), "stream": str(card.stream),
    } for card in reports]

    attendance = AttendanceRecord.objects.filter(student=student, is_deleted=False).values(
        "session__term__academic_year__name", "session__term__number",
    ).annotate(
        total=Count("id"), present=Count("id", filter=Q(status="present")),
    ).order_by("session__term__academic_year__name", "session__term__number")
    attendance_series = [{
        "term": f"{item['session__term__academic_year__name']} T{item['session__term__number']}",
        "rate": round(item["present"] / item["total"] * 100, 1) if item["total"] else 0,
    } for item in attendance]

    return {
        "outcome_series": dict(outcome_series),
        "competency_series": dict(competency_series),
        "skill_series": dict(skill_series),
        "attainment": attainment,
        "attendance": attendance_series,
        "achievements": student.achievements.filter(is_deleted=False).order_by("-achievement_date"),
    }
