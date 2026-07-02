from rest_framework import serializers

from .models import Enrollment, Guardian, Student, StudentGuardian, StudentMovement, StudentPromotion, StudentSubjectRegistration


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    stream_name = serializers.CharField(source="stream.__str__", read_only=True)

    class Meta:
        model = Student
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class GuardianSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = Guardian
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class StudentGuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentGuardian
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class StudentPromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentPromotion
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted", "approved_by")


class StudentSubjectRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentSubjectRegistration
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


class StudentMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentMovement
        fields = "__all__"
        read_only_fields = ("authorised_by", "created_at", "updated_at", "deleted_at", "is_deleted")
