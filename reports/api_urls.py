from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from config.mixins import ACADEMIC_MANAGERS
from config.permissions import IsReadOnlyOrAcademicManager, IsReadOnlyOrAcademicStaff
from .models import AcademicTranscript, ReportCard
from .serializers import AcademicTranscriptSerializer, ReportCardSerializer
from .services import generate_academic_transcript


class ReportCardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReportCard.objects.none()
    serializer_class = ReportCardSerializer
    permission_classes = [IsReadOnlyOrAcademicStaff]

    def get_queryset(self):
        qs = ReportCard.objects.filter(is_deleted=False).select_related("student", "term", "stream").prefetch_related("subject_results", "competency_ratings", "learning_outcome_ratings", "skill_ratings", "value_ratings")
        user = self.request.user
        if user.role == "teacher":
            return qs.filter(Q(stream__class_teacher=user) | Q(stream__subject_allocations__teacher=user, stream__subject_allocations__is_deleted=False)).distinct()
        if user.role == "student":
            return qs.filter(student__user=user, status__in=("published", "locked"))
        if user.role == "parent":
            return qs.filter(Q(student__parent=user) | Q(student__guardian_links__guardian__user=user), status__in=("published", "locked")).distinct()
        return qs


class AcademicTranscriptViewSet(viewsets.ModelViewSet):
    queryset = AcademicTranscript.objects.filter(is_deleted=False).select_related("student").prefetch_related("entries")
    serializer_class = AcademicTranscriptSerializer
    permission_classes = [IsReadOnlyOrAcademicManager]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role in ACADEMIC_MANAGERS:
            return qs
        if user.role == "teacher":
            return qs.filter(Q(student__stream__class_teacher=user) | Q(student__stream__subject_allocations__teacher=user)).distinct()
        if user.role == "student":
            return qs.filter(student__user=user, status="issued")
        if user.role == "parent":
            return qs.filter(Q(student__parent=user) | Q(student__guardian_links__guardian__user=user), status="issued").distinct()
        return qs.none()

    @action(detail=False, methods=["post"])
    def generate(self, request):
        from students.models import Student
        try:
            student = Student.objects.get(pk=request.data.get("student"), is_deleted=False)
            transcript = generate_academic_transcript(student, request.user, request.data.get("purpose", ""))
        except Student.DoesNotExist:
            return Response({"detail": "Valid student identifier is required."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            from django.core.exceptions import ValidationError
            if isinstance(exc, ValidationError):
                return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
            raise
        return Response(self.get_serializer(transcript).data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save(issued_by=self.request.user)


router = DefaultRouter()
router.register("report-cards", ReportCardViewSet, basename="report-card")
router.register("transcripts", AcademicTranscriptViewSet, basename="academic-transcript")
urlpatterns = router.urls
