from rest_framework import serializers
from .models import AttendanceRecord, AttendanceSession, TeacherAttendance


class AttendanceSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceSession
        fields = "__all__"
        read_only_fields = ("taken_by", "created_at", "updated_at", "deleted_at", "is_deleted")


class AttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class TeacherAttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherAttendance
        fields = "__all__"
        read_only_fields = ("recorded_by", "created_at", "updated_at", "deleted_at", "is_deleted")
