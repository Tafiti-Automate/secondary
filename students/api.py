from django.db import models
from rest_framework import viewsets

from config.mixins import ACADEMIC_MANAGERS, ACADEMIC_STAFF
from config.permissions import IsAcademicManager, IsReadOnlyOrAcademicStaff
from .models import Enrollment, Guardian, Student, StudentGuardian, StudentMovement, StudentPromotion, StudentSubjectRegistration
from .serializers import EnrollmentSerializer, GuardianSerializer, StudentGuardianSerializer, StudentMovementSerializer, StudentPromotionSerializer, StudentSerializer, StudentSubjectRegistrationSerializer


class ScopedStudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.filter(is_deleted=False).select_related("stream", "subject_combination")
    serializer_class = StudentSerializer
    permission_classes = [IsReadOnlyOrAcademicStaff]
    search_fields = ["student_number", "admission_number", "first_name", "last_name", "other_names"]
    ordering_fields = ["student_number", "admission_number", "first_name", "last_name", "date_admitted"]

    def get_permissions(self):
        if self.request.method not in {"GET", "HEAD", "OPTIONS"}:
            return [IsAcademicManager()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.role in ACADEMIC_MANAGERS or user.is_superuser:
            return qs
        if user.role == "teacher":
            return qs.filter(models.Q(stream__class_teacher=user) | models.Q(stream__subject_allocations__teacher=user, stream__subject_allocations__is_deleted=False)).distinct()
        if user.role == "student":
            return qs.filter(user=user)
        if user.role == "parent":
            return qs.filter(models.Q(parent=user) | models.Q(guardian_links__guardian__user=user)).distinct()
        return qs.none()

    def perform_destroy(self, instance):
        instance.soft_delete()


class ManagerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAcademicManager]

    def get_queryset(self):
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.soft_delete()


GuardianViewSet = type("GuardianViewSet", (ManagerViewSet,), {"queryset": Guardian.objects.all(), "serializer_class": GuardianSerializer, "search_fields": ["first_name", "last_name", "phone"]})
StudentGuardianViewSet = type("StudentGuardianViewSet", (ManagerViewSet,), {"queryset": StudentGuardian.objects.all(), "serializer_class": StudentGuardianSerializer})
EnrollmentViewSet = type("EnrollmentViewSet", (ManagerViewSet,), {"queryset": Enrollment.objects.all(), "serializer_class": EnrollmentSerializer})
SubjectRegistrationViewSet = type("SubjectRegistrationViewSet", (ManagerViewSet,), {"queryset": StudentSubjectRegistration.objects.all(), "serializer_class": StudentSubjectRegistrationSerializer})


class PromotionViewSet(ManagerViewSet):
    queryset = StudentPromotion.objects.all()
    serializer_class = StudentPromotionSerializer

    def perform_create(self, serializer):
        serializer.save(approved_by=self.request.user)


class StudentMovementViewSet(ManagerViewSet):
    queryset = StudentMovement.objects.all()
    serializer_class = StudentMovementSerializer

    def perform_create(self, serializer):
        serializer.save(authorised_by=self.request.user)
