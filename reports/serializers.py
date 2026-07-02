from rest_framework import serializers
from .models import (
    AcademicTranscript, ReportCard, ReportCompetencyRating, ReportLearningOutcomeRating,
    ReportSkillRating, ReportSubjectResult, ReportValueRating, TranscriptEntry,
)


class ReportSubjectResultSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = ReportSubjectResult
        fields = "__all__"


class ReportCompetencyRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportCompetencyRating
        fields = "__all__"


class ReportLearningOutcomeRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportLearningOutcomeRating
        fields = "__all__"


class ReportSkillRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportSkillRating
        fields = "__all__"


class ReportValueRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportValueRating
        fields = "__all__"


class ReportCardSerializer(serializers.ModelSerializer):
    subject_results = ReportSubjectResultSerializer(many=True, read_only=True)
    competency_ratings = ReportCompetencyRatingSerializer(many=True, read_only=True)
    learning_outcome_ratings = ReportLearningOutcomeRatingSerializer(many=True, read_only=True)
    skill_ratings = ReportSkillRatingSerializer(many=True, read_only=True)
    value_ratings = ReportValueRatingSerializer(many=True, read_only=True)

    class Meta:
        model = ReportCard
        fields = "__all__"
        read_only_fields = ("generated_by", "published_at", "created_at", "updated_at", "deleted_at", "is_deleted")


class TranscriptEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TranscriptEntry
        fields = "__all__"


class AcademicTranscriptSerializer(serializers.ModelSerializer):
    entries = TranscriptEntrySerializer(many=True, read_only=True)

    class Meta:
        model = AcademicTranscript
        fields = "__all__"
        read_only_fields = ("serial_number", "issued_by", "issued_at", "created_at", "updated_at", "deleted_at", "is_deleted")
