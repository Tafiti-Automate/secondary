from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from students.models import Student

from .models import ExaminationResult, GradeBoundary, UpperSubjectResult


def _grade_for(plan, score):
    boundaries = GradeBoundary.objects.filter(
        is_deleted=False,
        minimum_score__lte=score,
        maximum_score__gte=score,
    )
    boundaries = boundaries.filter(scale=plan.grade_scale) if plan.grade_scale_id else boundaries.filter(scale__isnull=True)
    return boundaries.order_by("-minimum_score").first()


@transaction.atomic
def process_upper_subject_results(plan, term, stream, user):
    """Compile configured S5/S6 components into final subject results and rankings."""
    if plan.status not in {"approved", "locked"}:
        raise ValidationError("Approve the upper-secondary assessment plan before processing marks.")
    if plan.academic_year_id != term.academic_year_id:
        raise ValidationError("Assessment plan and term belong to different academic years.")
    if plan.class_level_id != stream.class_level_id:
        raise ValidationError("Assessment plan and stream belong to different class levels.")

    components = list(plan.components.filter(is_deleted=False, is_active=True).order_by("sequence", "pk"))
    if sum((item.weight for item in components), Decimal("0")) != Decimal("100"):
        raise ValidationError("Active assessment component weights must total exactly 100%.")

    students = Student.objects.filter(stream=stream, status="active", is_deleted=False).order_by("first_name", "last_name")
    processed = []
    for student in students:
        breakdown = {}
        missing = []
        weighted_total = Decimal("0")
        available_percentages = []
        for component in components:
            result = (
                ExaminationResult.objects.filter(
                    student=student,
                    examination__component=component,
                    examination__term=term,
                    examination__stream=stream,
                    examination__status__in=("approved", "published", "locked"),
                    is_deleted=False,
                )
                .select_related("examination")
                .order_by("-examination__exam_date", "-pk")
                .first()
            )
            if not result:
                if component.is_required:
                    missing.append(component.name)
                breakdown[str(component.pk)] = {
                    "name": component.name,
                    "weight": str(component.weight),
                    "score": None,
                    "percentage": None,
                }
                continue
            percentage = result.percentage
            available_percentages.append(percentage)
            weighted_total += percentage * component.weight / Decimal("100")
            breakdown[str(component.pk)] = {
                "name": component.name,
                "weight": str(component.weight),
                "score": str(result.effective_score),
                "maximum_score": str(result.examination.max_score),
                "percentage": str(percentage),
            }

        final_score = weighted_total.quantize(Decimal("0.01"))
        average = (
            sum(available_percentages, Decimal("0")) / len(available_percentages)
        ).quantize(Decimal("0.01")) if available_percentages else Decimal("0")
        boundary = _grade_for(plan, final_score) if not missing else None
        defaults = {
            "stream": stream,
            "component_breakdown": breakdown,
            "total_score": final_score,
            "average_score": average,
            "grade": boundary.grade if boundary else "",
            "points": boundary.points if boundary else None,
            "remark": (boundary.descriptor or boundary.description) if boundary else ("Incomplete" if missing else ""),
            "passed": not missing and final_score >= plan.pass_mark,
            "has_missing_components": bool(missing),
            "missing_components": missing,
            "processed_by": user,
            "is_deleted": False,
        }
        existing = UpperSubjectResult.objects.filter(plan=plan, student=student, term=term, is_deleted=False).first()
        if existing and existing.status in {"approved", "locked"}:
            processed.append(existing)
            continue
        result, _ = UpperSubjectResult.objects.update_or_create(
            plan=plan,
            student=student,
            term=term,
            defaults=defaults,
        )
        processed.append(result)

    rankable = sorted((item for item in processed if not item.has_missing_components), key=lambda item: item.total_score, reverse=True)
    position = 0
    previous_score = None
    for index, result in enumerate(rankable, 1):
        if result.total_score != previous_score:
            position = index
            previous_score = result.total_score
        result.subject_position = position
        result.save(update_fields=["subject_position", "updated_at"])

    _rank_stream(term, stream)
    return processed


def _rank_stream(term, stream):
    scores = defaultdict(list)
    results = UpperSubjectResult.objects.filter(
        term=term,
        stream=stream,
        has_missing_components=False,
        is_deleted=False,
    ).exclude(status__in=("approved", "locked"))
    for result in results:
        scores[result.student_id].append(result.total_score)
    averages = sorted(
        ((student_id, sum(values, Decimal("0")) / len(values)) for student_id, values in scores.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    positions = {}
    position = 0
    previous_average = None
    for index, (student_id, average) in enumerate(averages, 1):
        if average != previous_average:
            position = index
            previous_average = average
        positions[student_id] = position
    for result in results:
        result.class_position = positions.get(result.student_id)
        result.save(update_fields=["class_position", "updated_at"])
