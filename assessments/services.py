from decimal import Decimal

from .models import AssessmentResult


def continuous_assessment_score(student, subject, term, stream=None):
    """Return a weighted CA score out of 100 using each task's configured weight."""
    results = AssessmentResult.objects.filter(
        student=student,
        assessment__subject=subject,
        assessment__term=term,
        assessment__status__in=("published", "closed", "moderated"),
        assessment__is_deleted=False,
        is_deleted=False,
    ).select_related("assessment__assessment_type")
    if stream:
        results = results.filter(assessment__stream=stream)
    weighted_scores = []
    for result in results:
        weight = Decimal(result.assessment.effective_weight)
        if weight > 0:
            weighted_scores.append((result.percentage, weight))
    if not weighted_scores:
        return Decimal("0.00")
    total_weight = sum((weight for _, weight in weighted_scores), Decimal("0"))
    if total_weight <= 0:
        return Decimal("0.00")
    weighted = sum((score * weight for score, weight in weighted_scores), Decimal("0"))
    return (weighted / total_weight).quantize(Decimal("0.01"))
