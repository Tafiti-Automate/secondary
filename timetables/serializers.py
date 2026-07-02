from rest_framework import serializers
from .models import Room, TimeSlot, TimetableEntry


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
