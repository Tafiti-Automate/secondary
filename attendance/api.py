from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from uuid import UUID
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.permissions import IsAcademicManager, IsReadOnlyOrAcademicManager, IsReadOnlyOrAcademicStaff
from .models import AttendanceAlert, AttendanceIdentity, AttendanceIntervention, AttendanceRecord, AttendanceSession, TeacherAttendance
from .serializers import AttendanceAlertSerializer, AttendanceIdentitySerializer, AttendanceInterventionSerializer, AttendanceRecordSerializer, AttendanceSessionSerializer, TeacherAttendanceSerializer


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsReadOnlyOrAcademicStaff]

    def get_queryset(self):
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.soft_delete()


class AttendanceSessionViewSet(BaseViewSet):
    queryset = AttendanceSession.objects.all()
    serializer_class = AttendanceSessionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "teacher":
            return qs.filter(Q(taken_by=user) | Q(stream__class_teacher=user) | Q(stream__subject_allocations__teacher=user)).distinct()
        if user.role == "student":
            return qs.filter(stream__students__user=user)
        if user.role == "parent":
            return qs.filter(Q(stream__students__parent=user) | Q(stream__students__guardian_links__guardian__user=user)).distinct()
        return qs

    def perform_create(self, serializer):
        serializer.save(taken_by=self.request.user)


class AttendanceRecordViewSet(BaseViewSet):
    queryset = AttendanceRecord.objects.all()
    serializer_class = AttendanceRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "teacher":
            return qs.filter(Q(session__taken_by=user) | Q(session__stream__class_teacher=user) | Q(session__stream__subject_allocations__teacher=user)).distinct()
        if user.role == "student":
            return qs.filter(student__user=user)
        if user.role == "parent":
            return qs.filter(Q(student__parent=user) | Q(student__guardian_links__guardian__user=user)).distinct()
        return qs

    @action(detail=False, methods=["post"], url_path="offline-sync")
    @transaction.atomic
    def offline_sync(self, request):
        """Idempotently accept a device queue; retrying the same capture IDs is safe."""
        payload = request.data if isinstance(request.data, list) else request.data.get("records", [])
        if not isinstance(payload, list) or len(payload) > 500:
            return Response({"detail": "Submit a list of at most 500 records."}, status=status.HTTP_400_BAD_REQUEST)
        sessions = AttendanceSessionViewSet()
        sessions.request = request
        allowed_sessions = sessions.get_queryset()
        saved, errors = [], []
        for index, item in enumerate(payload):
            data = dict(item)
            if not data.get("capture_id"):
                errors.append({"index": index, "capture_id": ["This field is required for offline sync."]})
                continue
            try:
                normalized_capture_id = UUID(str(data["capture_id"]))
            except (TypeError, ValueError, AttributeError):
                errors.append({"index": index, "capture_id": ["Enter a valid UUID."]})
                continue
            existing = AttendanceRecord.objects.filter(capture_id=normalized_capture_id).first()
            serializer = self.get_serializer(existing, data=data)
            if not serializer.is_valid():
                errors.append({"index": index, **serializer.errors})
                continue
            clean = serializer.validated_data
            session = allowed_sessions.filter(pk=clean["session"].pk).first()
            if not session or clean["student"].stream_id != session.stream_id:
                errors.append({"index": index, "detail": "Session or learner is outside your attendance scope."})
                continue
            if existing and (existing.session_id != session.pk or existing.student_id != clean["student"].pk):
                errors.append({"index": index, "detail": "Capture ID is already bound to another attendance record."})
                continue
            source = clean.get("source", "offline")
            if source not in {"offline", "qr", "biometric"}:
                source = "offline"
            record, created = AttendanceRecord.objects.update_or_create(
                capture_id=clean["capture_id"],
                defaults={
                    "session": session, "student": clean["student"], "status": clean.get("status", "present"),
                    "arrival_time": clean.get("arrival_time"), "reason": clean.get("reason", ""),
                    "notes": clean.get("notes", ""), "source": source,
                    "device_id": clean.get("device_id", ""), "captured_at": clean.get("captured_at") or timezone.now(),
                    "is_deleted": False,
                },
            )
            saved.append({"capture_id": str(record.capture_id), "id": record.pk, "created": created})
        response_status = status.HTTP_207_MULTI_STATUS if errors and saved else (status.HTTP_400_BAD_REQUEST if errors else status.HTTP_200_OK)
        return Response({"saved": saved, "errors": errors}, status=response_status)


class TeacherAttendanceViewSet(BaseViewSet):
    queryset = TeacherAttendance.objects.all()
    serializer_class = TeacherAttendanceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "teacher" and not user.is_superuser:
            return qs.filter(teacher=user)
        if user.role not in {"super_admin", "headteacher", "director_of_studies"} and not user.is_superuser:
            return qs.none()
        return qs

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class AttendanceIdentityViewSet(BaseViewSet):
    queryset = AttendanceIdentity.objects.all()
    serializer_class = AttendanceIdentitySerializer
    permission_classes = [IsAcademicManager]

    def perform_create(self, serializer):
        serializer.save(enrolled_by=self.request.user)


class AttendanceAlertViewSet(BaseViewSet):
    queryset = AttendanceAlert.objects.all()
    serializer_class = AttendanceAlertSerializer
    permission_classes = [IsReadOnlyOrAcademicManager]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser or self.request.user.role in {"super_admin", "headteacher", "director_of_studies"}:
            return qs
        if self.request.user.role == "teacher":
            return qs.filter(Q(assigned_to=self.request.user) | Q(student__stream__class_teacher=self.request.user)).distinct()
        return qs.none()


class AttendanceInterventionViewSet(BaseViewSet):
    queryset = AttendanceIntervention.objects.all()
    serializer_class = AttendanceInterventionSerializer
    permission_classes = [IsReadOnlyOrAcademicManager]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser or self.request.user.role in {"super_admin", "headteacher", "director_of_studies"}:
            return qs
        if self.request.user.role == "teacher":
            return qs.filter(Q(alert__assigned_to=self.request.user) | Q(student__stream__class_teacher=self.request.user)).distinct()
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)
