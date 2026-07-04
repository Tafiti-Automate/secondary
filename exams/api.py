from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Exists, OuterRef, Q

from config.mixins import ACADEMIC_MANAGERS
from config.permissions import IsAcademicManager, IsAcademicStaff, IsReadOnlyOrAcademicManager, IsReadOnlyOrAcademicStaff
from academics.models import Stream, SubjectAllocation, Term
from .models import (
    ExamSession, Examination, ExaminationResult, GradeBoundary, GradeScale, UNEBCandidate,
    UNEBCandidateSubject, UNEBContinuousAssessment, UNEBExportBatch, UNEBIntegrationAdapter,
    UpperAssessmentComponent, UpperAssessmentPlan, UpperSubjectResult,
)
from .serializers import (
    ExamSessionSerializer, ExaminationResultSerializer, ExaminationSerializer,
    GradeBoundarySerializer, GradeScaleSerializer, UNEBCandidateSerializer,
    UNEBCandidateSubjectSerializer, UNEBContinuousAssessmentSerializer,
    UNEBExportBatchSerializer, UNEBIntegrationAdapterSerializer, UpperAssessmentComponentSerializer,
    UpperAssessmentPlanSerializer, UpperSubjectResultSerializer,
)
from .services import process_upper_subject_results


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsReadOnlyOrAcademicStaff]

    def get_queryset(self):
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.soft_delete()


GradeScaleViewSet = type("GradeScaleViewSet", (BaseViewSet,), {"queryset": GradeScale.objects.all(), "serializer_class": GradeScaleSerializer, "permission_classes": [IsReadOnlyOrAcademicManager]})
GradeBoundaryViewSet = type("GradeBoundaryViewSet", (BaseViewSet,), {"queryset": GradeBoundary.objects.all(), "serializer_class": GradeBoundarySerializer, "permission_classes": [IsReadOnlyOrAcademicManager]})
ExamSessionViewSet = type("ExamSessionViewSet", (BaseViewSet,), {"queryset": ExamSession.objects.all(), "serializer_class": ExamSessionSerializer, "permission_classes": [IsReadOnlyOrAcademicManager]})
UNEBCandidateViewSet = type("UNEBCandidateViewSet", (BaseViewSet,), {"queryset": UNEBCandidate.objects.all(), "serializer_class": UNEBCandidateSerializer, "permission_classes": [IsAcademicManager]})
UNEBCandidateSubjectViewSet = type("UNEBCandidateSubjectViewSet", (BaseViewSet,), {"queryset": UNEBCandidateSubject.objects.all(), "serializer_class": UNEBCandidateSubjectSerializer, "permission_classes": [IsAcademicManager]})
UNEBExportBatchViewSet = type("UNEBExportBatchViewSet", (BaseViewSet,), {"queryset": UNEBExportBatch.objects.all(), "serializer_class": UNEBExportBatchSerializer, "permission_classes": [IsAcademicManager]})


class UNEBIntegrationAdapterViewSet(BaseViewSet):
    queryset = UNEBIntegrationAdapter.objects.all()
    serializer_class = UNEBIntegrationAdapterSerializer
    permission_classes = [IsReadOnlyOrAcademicManager]

    def perform_create(self, serializer):
        status_value = serializer.validated_data.get("status", "draft")
        serializer.save(approved_by=self.request.user if status_value == "active" else None)

    def perform_update(self, serializer):
        status_value = serializer.validated_data.get("status", serializer.instance.status)
        serializer.save(approved_by=self.request.user if status_value == "active" else serializer.instance.approved_by)


class UpperAssessmentPlanViewSet(BaseViewSet):
    queryset = UpperAssessmentPlan.objects.all()
    serializer_class = UpperAssessmentPlanSerializer
    permission_classes = [IsReadOnlyOrAcademicManager]

    def perform_create(self, serializer):
        serializer.save(status="draft")

    def perform_update(self, serializer):
        requested_status = serializer.validated_data.get("status", serializer.instance.status)
        if requested_status in {"approved", "locked"}:
            serializer.save(approved_by=self.request.user)
        else:
            serializer.save()

    @action(detail=True, methods=["post"])
    def process(self, request, pk=None):
        plan = self.get_object()
        try:
            term = Term.objects.get(pk=request.data.get("term"), is_deleted=False)
            stream = Stream.objects.get(pk=request.data.get("stream"), is_deleted=False)
        except (Term.DoesNotExist, Stream.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Valid term and stream identifiers are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            results = process_upper_subject_results(plan, term, stream, request.user)
        except Exception as exc:
            from django.core.exceptions import ValidationError
            if isinstance(exc, ValidationError):
                return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
            raise
        return Response(UpperSubjectResultSerializer(results, many=True).data)


UpperAssessmentComponentViewSet = type(
    "UpperAssessmentComponentViewSet",
    (BaseViewSet,),
    {
        "queryset": UpperAssessmentComponent.objects.all(),
        "serializer_class": UpperAssessmentComponentSerializer,
        "permission_classes": [IsReadOnlyOrAcademicManager],
    },
)


class UpperSubjectResultViewSet(BaseViewSet):
    queryset = UpperSubjectResult.objects.all()
    serializer_class = UpperSubjectResultSerializer
    permission_classes = [IsReadOnlyOrAcademicStaff]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role in ACADEMIC_MANAGERS:
            return qs
        if user.role == "teacher":
            allocation = SubjectAllocation.objects.filter(
                teacher=user,
                subject_id=OuterRef("plan__subject_id"),
                stream_id=OuterRef("stream_id"),
                term_id=OuterRef("term_id"),
                is_deleted=False,
                is_active=True,
            )
            return qs.annotate(is_allocated=Exists(allocation)).filter(Q(is_allocated=True) | Q(plan__subject__department__head=user))
        if user.role == "student":
            return qs.filter(student__user=user, status__in=("approved", "locked"))
        if user.role == "parent":
            return qs.filter(student__guardian_links__guardian__user=user, status__in=("approved", "locked")).distinct()
        return qs.none()

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        result = self.get_object()
        try:
            result.transition(request.data.get("operation", ""), request.user)
        except Exception as exc:
            from django.core.exceptions import ValidationError
            if isinstance(exc, ValidationError):
                return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
            raise
        return Response(self.get_serializer(result).data)


class UNEBContinuousAssessmentViewSet(BaseViewSet):
    queryset = UNEBContinuousAssessment.objects.all()
    serializer_class = UNEBContinuousAssessmentSerializer
    permission_classes = [IsAcademicStaff]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == "teacher":
            return qs.filter(candidate_subject__subject__allocations__teacher=self.request.user, candidate_subject__subject__allocations__is_deleted=False).distinct()
        return qs

    def perform_create(self, serializer):
        status_value = serializer.validated_data.get("status", "draft")
        if self.request.user.role == "teacher":
            status_value = "draft"
        serializer.save(entered_by=self.request.user, status=status_value)


class ExaminationViewSet(BaseViewSet):
    queryset = Examination.objects.all()
    serializer_class = ExaminationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "teacher" and not user.is_superuser:
            allocation = SubjectAllocation.objects.filter(teacher=user, subject_id=OuterRef("subject_id"), stream_id=OuterRef("stream_id"), term_id=OuterRef("term_id"), is_deleted=False, is_active=True)
            qs = qs.annotate(is_allocated=Exists(allocation)).filter(is_allocated=True)
        elif user.role == "student":
            qs = qs.filter(stream__students__user=user, status__in=("published", "locked"))
        elif user.role == "parent":
            qs = qs.filter(stream__students__guardian_links__guardian__user=user, status__in=("published", "locked")).distinct()
        return qs

    def perform_create(self, serializer):
        status_value = serializer.validated_data.get("status", "draft")
        if self.request.user.role == "teacher" and status_value not in {"draft", "entry"}:
            status_value = "draft"
        serializer.save(created_by=self.request.user, status=status_value)

    def perform_update(self, serializer):
        if serializer.instance.status == "locked":
            from rest_framework.exceptions import ValidationError
            raise ValidationError("A locked examination cannot be changed.")
        status_value = serializer.validated_data.get("status", serializer.instance.status)
        if self.request.user.role == "teacher" and status_value not in {"draft", "entry"}:
            status_value = serializer.instance.status
        serializer.save(status=status_value)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        examination = self.get_object()
        operation = request.data.get("operation")
        if operation not in {"submit", "moderate", "approve", "publish", "lock", "reopen"}:
            return Response({"detail": "Invalid transition."}, status=status.HTTP_400_BAD_REQUEST)
        allowed_states = {"submit": {"draft", "entry"}, "moderate": {"submitted"}, "approve": {"moderated"}, "publish": {"approved"}, "lock": {"published"}, "reopen": {"submitted", "moderated", "approved", "published"}}
        if examination.status not in allowed_states[operation]:
            return Response({"detail": "Transition is invalid from the current state."}, status=status.HTTP_409_CONFLICT)
        if operation != "submit" and request.user.role not in ACADEMIC_MANAGERS and not request.user.is_superuser:
            return Response({"detail": "Academic management approval is required."}, status=status.HTTP_403_FORBIDDEN)
        examination.transition(operation, request.user)
        return Response(self.get_serializer(examination).data)


class ExaminationResultViewSet(BaseViewSet):
    queryset = ExaminationResult.objects.all()
    serializer_class = ExaminationResultSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == "teacher":
            allocation = SubjectAllocation.objects.filter(teacher=self.request.user, subject_id=OuterRef("examination__subject_id"), stream_id=OuterRef("examination__stream_id"), term_id=OuterRef("examination__term_id"), is_deleted=False, is_active=True)
            return qs.annotate(is_allocated=Exists(allocation)).filter(is_allocated=True)
        if self.request.user.role == "student":
            return qs.filter(student__user=self.request.user, examination__status__in=("published", "locked"))
        if self.request.user.role == "parent":
            return qs.filter(student__guardian_links__guardian__user=self.request.user, examination__status__in=("published", "locked")).distinct()
        return qs

    def perform_create(self, serializer):
        if serializer.validated_data["examination"].status == "locked":
            from rest_framework.exceptions import ValidationError
            raise ValidationError("This examination is locked.")
        serializer.save(marked_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.examination.status == "locked":
            from rest_framework.exceptions import ValidationError
            raise ValidationError("This examination is locked.")
        serializer.save(marked_by=self.request.user)
