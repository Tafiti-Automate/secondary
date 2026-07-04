from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class TimelineEvent:
    occurred_on: date
    category: str
    title: str
    description: str = ""
    tone: str = "slate"
    source: object | None = None


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value


def learner_timeline(student):
    """Compose one chronological learner story from authoritative module records."""
    events = [TimelineEvent(student.date_admitted, "admission", "Admitted to the school", student.previous_school, "emerald", student)]
    for enrollment in student.enrollments.filter(is_deleted=False).select_related("academic_year", "stream__class_level"):
        events.append(TimelineEvent(
            enrollment.enrolled_on, "enrolment", f"Enrolled in {enrollment.stream}",
            f"{enrollment.academic_year} · {enrollment.get_status_display()}", "blue", enrollment,
        ))
    for movement in student.movements.filter(is_deleted=False):
        events.append(TimelineEvent(
            movement.effective_date, "movement", movement.get_movement_type_display(),
            movement.reason or movement.destination or movement.previous_school, "amber", movement,
        ))
    for promotion in student.promotions.filter(is_deleted=False).select_related("from_stream", "to_stream"):
        destination = f" → {promotion.to_stream}" if promotion.to_stream else ""
        events.append(TimelineEvent(
            promotion.decision_date, "progression", promotion.get_decision_display(),
            f"{promotion.from_stream or 'Unplaced'}{destination}. {promotion.remarks}".strip(), "violet", promotion,
        ))
    for achievement in student.achievements.filter(is_deleted=False):
        events.append(TimelineEvent(
            achievement.achievement_date, "achievement", achievement.title,
            f"{achievement.get_level_display()} · {achievement.description}".strip(" ·"), "emerald", achievement,
        ))
    for accommodation in student.accommodations.filter(is_deleted=False):
        events.append(TimelineEvent(
            accommodation.start_date, "support", accommodation.title,
            accommodation.support_strategy, "cyan", accommodation,
        ))
    for report in student.report_cards.filter(is_deleted=False, status__in=("published", "locked")).select_related("term"):
        events.append(TimelineEvent(
            _as_date(report.published_at or report.updated_at), "report", f"Published report · {report.term}",
            f"Average {report.average_score}% · {report.get_promotion_decision_display()}", "indigo", report,
        ))
    return sorted(events, key=lambda item: (item.occurred_on or date.min, item.title), reverse=True)
