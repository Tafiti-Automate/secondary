from rest_framework import serializers
from .models import Announcement, ConsentRecord, ConversationMessage, ConversationThread, EmergencyBroadcast, LearningResource, Notification


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


class ConversationThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationThread
        fields = "__all__"
        read_only_fields = ("created_by", "last_message_at", "created_at", "updated_at", "deleted_at", "is_deleted")


class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationMessage
        fields = "__all__"
        read_only_fields = ("sender", "read_by", "created_at", "updated_at", "deleted_at", "is_deleted")


class ConsentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentRecord
        fields = "__all__"
        read_only_fields = ("captured_by", "created_at", "updated_at", "deleted_at", "is_deleted")


class EmergencyBroadcastSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyBroadcast
        fields = "__all__"
        read_only_fields = ("created_by", "sent_by", "sent_at", "delivery_summary", "acknowledged_by", "created_at", "updated_at", "deleted_at", "is_deleted")
