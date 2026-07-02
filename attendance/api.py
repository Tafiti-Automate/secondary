from rest_framework import viewsets
from django.db.models import Q
from config.permissions import IsReadOnlyOrAcademicStaff
from .models import AttendanceRecord, AttendanceSession, TeacherAttendance
from .serializers import AttendanceRecordSerializer, AttendanceSessionSerializer, TeacherAttendanceSerializer


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
