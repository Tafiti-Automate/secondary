from rest_framework import serializers
from .models import Room, SchedulingRequirement, TimeSlot, TimetableEntry, TimetableGenerationRun


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class TimetableEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableEntry
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class SchedulingRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchedulingRequirement
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class TimetableGenerationRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableGenerationRun
        fields = "__all__"
        read_only_fields = ("requested_by", "status", "generated_count", "unresolved_count", "result", "completed_at", "created_at", "updated_at", "deleted_at", "is_deleted")
