from collections import defaultdict
from decimal import Decimal

from .models import AssessmentResult


def continuous_assessment_score(student, subject, term, stream=None):
    """Return a weighted CA score out of 100 using type averages."""
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
    grouped = defaultdict(list)
    weights = {}
    for result in results:
        assessment_type = result.assessment.assessment_type
        grouped[assessment_type.pk].append(result.percentage)
        weights[assessment_type.pk] = Decimal(assessment_type.weight)
    if not grouped:
        return Decimal("0.00")
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return Decimal("0.00")
    weighted = sum((sum(scores) / len(scores)) * weights[key] for key, scores in grouped.items())
    return (weighted / total_weight).quantize(Decimal("0.01"))
