from dataclasses import dataclass, field
from datetime import date

from django.db import models

from .models import UNEBCandidate, UNEBContinuousAssessment, UNEBIntegrationAdapter


DEFAULT_UNEB_COLUMNS = [
    {"header": "Centre No.", "key": "centre_number"}, {"header": "Index No.", "key": "index_number"},
    {"header": "Candidate Name", "key": "candidate_name"}, {"header": "Sex", "key": "gender"},
    {"header": "Level", "key": "examination_level"}, {"header": "Year", "key": "examination_year"},
    {"header": "Subject Code", "key": "subject_code"}, {"header": "Subject", "key": "subject_name"},
    {"header": "Class", "key": "class_level"}, {"header": "Term", "key": "term"},
    {"header": "Component", "key": "component"}, {"header": "Raw Score", "key": "raw_score"},
    {"header": "Maximum", "key": "maximum_score"}, {"header": "Percentage", "key": "percentage_score"},
    {"header": "Evidence Reference", "key": "evidence_reference"},
]


@dataclass
class UNEBPreflightResult:
    examination_level: str
    examination_year: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    records: list = field(default_factory=list)

    @property
    def ready(self):
        return not self.errors and bool(self.records)


def active_uneb_adapter(examination_level, examination_year):
    cycle_date = date(int(examination_year), 1, 1)
    return UNEBIntegrationAdapter.objects.filter(
        examination_level=examination_level,
        status="active",
        effective_from__lte=cycle_date,
        is_deleted=False,
    ).filter(
        models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=cycle_date)
    ).order_by("-effective_from", "-pk").first()


def uneb_export_columns(adapter=None):
    return adapter.columns if adapter and adapter.columns else DEFAULT_UNEB_COLUMNS


def uneb_export_row(item, adapter=None):
    candidate = item.candidate_subject.candidate
    values = {
        "centre_number": candidate.centre_number,
        "index_number": candidate.index_number,
        "candidate_name": candidate.candidate_name,
        "gender": candidate.gender,
        "examination_level": candidate.examination_level.upper(),
        "examination_year": candidate.examination_year,
        "subject_code": item.candidate_subject.subject_code,
        "subject_name": item.candidate_subject.subject.name,
        "class_level": item.class_level.name,
        "term": item.term.name if item.term else "",
        "component": item.get_component_display(),
        "raw_score": float(item.raw_score),
        "maximum_score": float(item.maximum_score),
        "percentage_score": float(item.percentage_score),
        "evidence_reference": item.evidence_reference,
    }
    return [values[column["key"]] for column in uneb_export_columns(adapter)]


def uneb_export_preflight(examination_level, examination_year, adapter=None):
    """Validate the complete candidate cohort before creating a UNEB workbook.

    This is deliberately stricter than validating individual rows. It prevents a
    technically valid subset from being presented as a complete school export.
    The workbook remains a pre-submission aid; the current UNEB template is the
    final authority for every examination cycle.
    """
    level = str(examination_level or "").lower()
    try:
        year = int(examination_year)
    except (TypeError, ValueError):
        return UNEBPreflightResult(level, 0, errors=["A valid examination year is required."])
    result = UNEBPreflightResult(level, year)
    if level not in {"uce", "uace"}:
        result.errors.append("Examination level must be UCE or UACE.")
        return result
    adapter = adapter or active_uneb_adapter(level, year)
    requirements = adapter.requirements if adapter else {}

    candidates = list(
        UNEBCandidate.objects.filter(
            examination_level=level,
            examination_year=year,
            status__in=("verified", "registered"),
            is_deleted=False,
        ).prefetch_related("registered_subjects__subject")
    )
    if not candidates:
        result.errors.append(f"No verified or registered {level.upper()} candidates exist for {year}.")
        return result

    approved = UNEBContinuousAssessment.objects.filter(
        is_deleted=False,
        status="approved",
        candidate_subject__candidate__in=candidates,
        candidate_subject__is_registered=True,
        candidate_subject__is_deleted=False,
    ).select_related(
        "candidate_subject__candidate", "candidate_subject__subject", "class_level", "term"
    )

    for candidate in candidates:
        label = candidate.index_number or candidate.candidate_name or candidate.student.full_name
        if not candidate.index_number:
            result.errors.append(f"{label}: index number is missing.")
        if not candidate.centre_number:
            result.errors.append(f"{label}: centre number is missing.")
        registrations = [
            item for item in candidate.registered_subjects.all()
            if item.is_registered and not item.is_deleted
        ]
        subject_min = int(requirements.get("subject_min", 8 if level == "uce" else 1))
        subject_max = int(requirements.get("subject_max", 9 if level == "uce" else 99))
        if not subject_min <= len(registrations) <= subject_max:
            result.errors.append(
                f"{label}: {level.upper()} requires {subject_min}–{subject_max} registered subjects; found {len(registrations)}."
            )
        codes = [item.subject_code.strip().upper() for item in registrations if item.subject_code]
        if len(codes) != len(registrations):
            result.errors.append(f"{label}: every registered subject needs a UNEB subject code.")
        if len(codes) != len(set(codes)):
            result.errors.append(f"{label}: duplicate UNEB subject codes are registered.")

        for registration in registrations:
            subject_records = approved.filter(candidate_subject=registration)
            if not subject_records.exclude(component="project").exists():
                result.errors.append(
                    f"{label}: approved continuous assessment is missing for {registration.subject.name}."
                )

        require_s3_project = requirements.get("require_s3_project", level == "uce")
        if require_s3_project and not approved.filter(
            candidate_subject__candidate=candidate,
            class_level__level=3,
            component="project",
        ).exists():
            result.errors.append(f"{label}: the approved S3 project score is missing.")

        pending = UNEBContinuousAssessment.objects.filter(
            candidate_subject__candidate=candidate,
            candidate_subject__is_registered=True,
            status__in=("draft", "verified"),
            is_deleted=False,
        ).count()
        if pending:
            result.errors.append(f"{label}: {pending} CA record(s) are still awaiting approval.")

    result.records = list(approved.order_by(
        "candidate_subject__candidate__candidate_name",
        "candidate_subject__subject__name",
        "class_level__level",
        "term__number",
        "component",
    ))
    if not result.records:
        result.errors.append("No approved UNEB continuous-assessment records are available.")
    return result
