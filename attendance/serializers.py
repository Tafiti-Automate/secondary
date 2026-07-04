from rest_framework import serializers
from .models import AttendanceAlert, AttendanceIdentity, AttendanceIntervention, AttendanceRecord, AttendanceSession, TeacherAttendance


class AttendanceSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceSession
        fields = "__all__"
        read_only_fields = ("taken_by", "created_at", "updated_at", "deleted_at", "is_deleted")


class AttendanceRecordSerializer(serializers.ModelSerializer):
    capture_id = serializers.UUIDField(required=False)

    class Meta:
        model = AttendanceRecord
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class TeacherAttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherAttendance
        fields = "__all__"
        read_only_fields = ("recorded_by", "created_at", "updated_at", "deleted_at", "is_deleted")


class AttendanceIdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceIdentity
        fields = "__all__"
        read_only_fields = ("enrolled_by", "created_at", "updated_at", "deleted_at", "is_deleted")


class AttendanceAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceAlert
        fields = "__all__"
        read_only_fields = ("resolved_by", "resolved_at", "created_at", "updated_at", "deleted_at", "is_deleted")


class AttendanceInterventionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceIntervention
        fields = "__all__"
        read_only_fields = ("recorded_by", "created_at", "updated_at", "deleted_at", "is_deleted")
