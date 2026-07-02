from config.forms import StyledModelForm
from .models import Announcement, LearningResource


class AnnouncementForm(StyledModelForm):
    class Meta:
        model = Announcement
        fields = ("title", "body", "audience", "stream", "attachment", "published_at", "expires_at", "is_pinned")


class LearningResourceForm(StyledModelForm):
    class Meta:
        model = LearningResource
        fields = ("title", "description", "subject", "class_level", "stream", "resource_type", "file", "external_url", "is_published")
