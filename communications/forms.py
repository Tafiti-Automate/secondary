from config.forms import StyledModelForm
from .models import Announcement, ConsentRecord, ConversationMessage, ConversationThread, EmergencyBroadcast, LearningResource


class AnnouncementForm(StyledModelForm):
    class Meta:
        model = Announcement
        fields = ("title", "body", "language", "translations", "audience", "stream", "attachment", "published_at", "expires_at", "is_pinned")


class LearningResourceForm(StyledModelForm):
    class Meta:
        model = LearningResource
        fields = ("title", "description", "subject", "class_level", "stream", "resource_type", "file", "external_url", "is_published")


class ConversationThreadForm(StyledModelForm):
    class Meta:
        model = ConversationThread
        fields = ("subject", "student", "participants")


class ConversationMessageForm(StyledModelForm):
    class Meta:
        model = ConversationMessage
        fields = ("body", "language", "translations", "attachment")


class ConsentRecordForm(StyledModelForm):
    class Meta:
        model = ConsentRecord
        fields = ("student", "consent_type", "policy_version", "status", "guardian", "effective_date", "expires_on", "evidence", "notes")


class EmergencyBroadcastForm(StyledModelForm):
    class Meta:
        model = EmergencyBroadcast
        fields = ("title", "message", "language", "translations", "severity", "audience", "stream", "channels")
