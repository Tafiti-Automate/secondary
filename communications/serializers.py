from rest_framework import serializers
from .models import Announcement, LearningResource, Notification


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at", "deleted_at", "is_deleted")


class LearningResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningResource
        fields = "__all__"
        read_only_fields = ("uploaded_by", "created_at", "updated_at", "deleted_at", "is_deleted")


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = ("recipient", "status", "sent_at", "error_message", "created_at", "updated_at", "deleted_at", "is_deleted")
