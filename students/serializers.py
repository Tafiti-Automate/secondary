from rest_framework import serializers

from .models import Enrollment, Guardian, Student, StudentAccommodation, StudentAchievement, StudentGuardian, StudentInterest, StudentMovement, StudentPromotion, StudentSubjectRegistration


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    stream_name = serializers.CharField(source="stream.__str__", read_only=True)

    class Meta:
        model = Student
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.role == "teacher" and not user.is_superuser:
            for field in ("national_id", "medical_information", "blood_group", "allergies"):
                data.pop(field, None)
        return data


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


class StudentAccommodationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAccommodation
        fields = "__all__"
        read_only_fields = ("recorded_by", "reviewed_by", "reviewed_at", "created_at", "updated_at", "deleted_at", "is_deleted")


class StudentInterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentInterest
        fields = "__all__"
        read_only_fields = ("recorded_by", "created_at", "updated_at", "deleted_at", "is_deleted")


class StudentAchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAchievement
        fields = "__all__"
        read_only_fields = ("verified_by", "verified_at", "created_at", "updated_at", "deleted_at", "is_deleted")
