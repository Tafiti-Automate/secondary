from rest_framework import serializers
from .models import (
    ExamSession, Examination, ExaminationResult, GradeBoundary, GradeScale, UNEBCandidate,
    UNEBCandidateSubject, UNEBContinuousAssessment, UNEBExportBatch, UNEBIntegrationAdapter,
    UpperAssessmentComponent, UpperAssessmentPlan, UpperSubjectResult,
)


def serializer_for(model, read_only=()):
    meta = type("Meta", (), {"model": model, "fields": "__all__", "read_only_fields": ("created_at", "updated_at", "deleted_at", "is_deleted") + tuple(read_only)})
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})


GradeScaleSerializer = serializer_for(GradeScale)
GradeBoundarySerializer = serializer_for(GradeBoundary)
ExamSessionSerializer = serializer_for(ExamSession)
ExaminationSerializer = serializer_for(Examination, ("created_by", "submitted_at", "moderated_by", "moderated_at", "approved_by", "approved_at", "published", "locked"))
ExaminationResultSerializer = serializer_for(ExaminationResult, ("marked_by", "grade", "points", "descriptor", "approved"))
UNEBCandidateSerializer = serializer_for(UNEBCandidate, ("verified_by", "verified_at"))
UNEBCandidateSubjectSerializer = serializer_for(UNEBCandidateSubject)
UNEBContinuousAssessmentSerializer = serializer_for(UNEBContinuousAssessment, ("entered_by", "verified_by", "approved_by", "percentage_score", "verified_at", "approved_at"))
UNEBExportBatchSerializer = serializer_for(UNEBExportBatch, ("generated_by", "generated_at", "record_count", "checksum"))
UNEBIntegrationAdapterSerializer = serializer_for(UNEBIntegrationAdapter, ("approved_by", "approved_at"))
UpperAssessmentPlanSerializer = serializer_for(UpperAssessmentPlan, ("approved_by", "approved_at"))
UpperAssessmentComponentSerializer = serializer_for(UpperAssessmentComponent)
UpperSubjectResultSerializer = serializer_for(UpperSubjectResult, (
    "component_breakdown", "total_score", "average_score", "grade", "points", "remark",
    "passed", "class_position", "subject_position", "has_missing_components",
    "missing_components", "processed_by", "status", "moderated_by", "moderated_at",
    "approved_by", "approved_at", "locked_by", "locked_at",
))
