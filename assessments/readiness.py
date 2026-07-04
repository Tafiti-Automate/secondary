from dataclasses import dataclass, field

from academics.models import SubjectAllocation
from exams.models import UpperAssessmentPlan

from .models import AssessmentPolicy, CurriculumFramework, CurriculumTopic, LessonPlan, SchemeOfWork


@dataclass
class CurriculumCoverageResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_allocations: int = 0

    @property
    def ready(self):
        return not self.errors


def curriculum_coverage_for_year(academic_year):
    """Check that every offered subject/class/term has usable curriculum data."""
    result = CurriculumCoverageResult()
    frameworks = {
        item.stage: item
        for item in CurriculumFramework.objects.filter(is_active=True, is_deleted=False).order_by("-implementation_year")
    }
    for stage, label in (("lower", "Lower Secondary"), ("advanced", "Advanced Secondary")):
        if stage not in frameworks:
            result.errors.append(f"No active {label} curriculum framework is configured.")

    allocations = SubjectAllocation.objects.filter(
        stream__academic_year=academic_year,
        term__academic_year=academic_year,
        is_active=True,
        is_deleted=False,
    ).select_related("subject", "stream__class_level", "term")
    seen = set()
    for allocation in allocations:
        key = (allocation.subject_id, allocation.stream.class_level_id, allocation.term_id)
        if key in seen:
            continue
        seen.add(key)
        result.checked_allocations += 1
        class_level = allocation.stream.class_level
        stage = "lower" if class_level.curriculum == "lower" else "advanced"
        topics = CurriculumTopic.objects.filter(
            framework__stage=stage,
            framework__is_active=True,
            framework__is_deleted=False,
            subject=allocation.subject,
            class_level=class_level,
            term_number=allocation.term.number,
            is_deleted=False,
            learning_outcomes__is_deleted=False,
        ).distinct()
        label = f"{class_level} {allocation.subject.name} {allocation.term.name}"
        if not topics.exists():
            result.errors.append(f"{label}: no active topic with a learning outcome is imported.")

        if not SchemeOfWork.objects.filter(allocation__subject=allocation.subject, allocation__stream=allocation.stream, allocation__term=allocation.term, is_deleted=False).exists():
            result.warnings.append(f"{label}: no scheme of work has been created.")
        if not LessonPlan.objects.filter(allocation__subject=allocation.subject, allocation__stream=allocation.stream, allocation__term=allocation.term, is_deleted=False).exists():
            result.warnings.append(f"{label}: no lesson plan has been created.")

        policy = AssessmentPolicy.objects.filter(
            academic_year=academic_year,
            class_level=class_level,
            purpose="internal",
            is_active=True,
            is_deleted=False,
        ).first()
        if not policy:
            result.errors.append(f"{class_level}: no active internal assessment policy is configured.")

        if class_level.curriculum == "upper":
            plan = UpperAssessmentPlan.objects.filter(
                academic_year=academic_year,
                class_level=class_level,
                subject=allocation.subject,
                status__in=("approved", "locked"),
                is_deleted=False,
            ).first()
            if not plan:
                result.errors.append(f"{class_level} {allocation.subject.name}: no approved S5/S6 assessment plan exists.")

    if not result.checked_allocations:
        result.errors.append(f"No active teaching allocations exist for {academic_year}.")
    return result
