from rest_framework import viewsets
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.routers import DefaultRouter

from config.permissions import IsReadOnlyOrAcademicManager, IsReadOnlyOrAcademicStaff
from .models import Announcement, ConsentRecord, ConversationMessage, ConversationThread, EmergencyBroadcast, LearningResource, Notification
from .serializers import AnnouncementSerializer, ConsentRecordSerializer, ConversationMessageSerializer, ConversationThreadSerializer, EmergencyBroadcastSerializer, LearningResourceSerializer, NotificationSerializer
from .access import conversation_scope


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


class ConversationThreadViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationThreadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ConversationThread.objects.filter(is_deleted=False)
        return qs if self.request.user.is_superuser else qs.filter(participants=self.request.user)

    def perform_create(self, serializer):
        people, students = conversation_scope(self.request.user)
        participant_ids = {person.pk for person in serializer.validated_data.get("participants", [])}
        if participant_ids - set(people.filter(pk__in=participant_ids).values_list("pk", flat=True)):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("One or more participants are outside your communication scope.")
        student = serializer.validated_data.get("student")
        if student and not students.filter(pk=student.pk).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("That learner is outside your communication scope.")
        thread = serializer.save(created_by=self.request.user)
        thread.participants.add(self.request.user)


class ConversationMessageViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ConversationMessage.objects.filter(thread__participants=self.request.user, is_deleted=False).distinct()

    def perform_create(self, serializer):
        thread = serializer.validated_data["thread"]
        if not thread.participants.filter(pk=self.request.user.pk).exists() and not self.request.user.is_superuser:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a participant in this conversation.")
        serializer.save(sender=self.request.user)


class ConsentRecordViewSet(viewsets.ModelViewSet):
    serializer_class = ConsentRecordSerializer
    permission_classes = [IsReadOnlyOrAcademicManager]

    def get_queryset(self):
        qs = ConsentRecord.objects.filter(is_deleted=False)
        user = self.request.user
        if user.is_superuser or user.role in {"super_admin", "headteacher", "director_of_studies"}:
            return qs
        if user.role == "student":
            return qs.filter(student__user=user)
        if user.role == "parent":
            return qs.filter(Q(guardian=user) | Q(student__parent=user) | Q(student__guardian_links__guardian__user=user)).distinct()
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(captured_by=self.request.user)


class EmergencyBroadcastViewSet(viewsets.ModelViewSet):
    serializer_class = EmergencyBroadcastSerializer
    permission_classes = [IsReadOnlyOrAcademicManager]

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.role in {"super_admin", "headteacher", "director_of_studies"}:
            return EmergencyBroadcast.objects.filter(is_deleted=False)
        return EmergencyBroadcast.objects.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("resources", ResourceViewSet, basename="resource")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("conversations", ConversationThreadViewSet, basename="conversation")
router.register("messages", ConversationMessageViewSet, basename="conversation-message")
router.register("consents", ConsentRecordViewSet, basename="consent")
router.register("emergency", EmergencyBroadcastViewSet, basename="emergency-broadcast")
urlpatterns = router.urls
