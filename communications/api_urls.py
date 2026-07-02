from rest_framework import viewsets
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.routers import DefaultRouter

from config.permissions import IsReadOnlyOrAcademicManager, IsReadOnlyOrAcademicStaff
from .models import Announcement, LearningResource, Notification
from .serializers import AnnouncementSerializer, LearningResourceSerializer, NotificationSerializer


class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.filter(is_deleted=False)
    serializer_class = AnnouncementSerializer
    permission_classes = [IsReadOnlyOrAcademicManager]

    def get_queryset(self):
        user = self.request.user
        qs = Announcement.objects.filter(is_deleted=False, published_at__lte=timezone.now()).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now()))
        if user.is_superuser or user.role in {"super_admin", "headteacher", "director_of_studies"}:
            return qs
        audiences = ["all"]
        if user.role == "teacher":
            audiences += ["staff", "teachers"]
        elif user.role == "student":
            audiences += ["students", "stream"]
            qs = qs.filter(Q(stream__isnull=True) | Q(stream__students__user=user))
        elif user.role == "parent":
            audiences += ["parents", "stream"]
            qs = qs.filter(Q(stream__isnull=True) | Q(stream__students__parent=user) | Q(stream__students__guardian_links__guardian__user=user)).distinct()
        return qs.filter(audience__in=audiences)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ResourceViewSet(viewsets.ModelViewSet):
    queryset = LearningResource.objects.filter(is_deleted=False)
    serializer_class = LearningResourceSerializer
    permission_classes = [IsReadOnlyOrAcademicStaff]

    def get_queryset(self):
        qs = LearningResource.objects.filter(is_deleted=False)
        user = self.request.user
        if user.role in {"student", "parent"}:
            qs = qs.filter(is_published=True)
        if user.role == "student" and hasattr(user, "student_profile") and user.student_profile.stream_id:
            qs = qs.filter(class_level=user.student_profile.stream.class_level).filter(Q(stream__isnull=True) | Q(stream=user.student_profile.stream))
        return qs

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user, is_deleted=False)


router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("resources", ResourceViewSet, basename="resource")
router.register("notifications", NotificationViewSet, basename="notification")
urlpatterns = router.urls
