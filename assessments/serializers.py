from rest_framework import serializers

from .models import (
    ActivityOfIntegration, Assessment, AssessmentEvidence, AssessmentPolicy, AssessmentResult,
    AssessmentReview, AssessmentScale, AssessmentSubmission, AssessmentType, Competency, CompetencyAssessment,
    CompetencyIndicator, CompetencyLevel, CurriculumFramework, CurriculumLearningArea,
    CurriculumTopic, CurriculumValue, EvidenceAsset, LearnerSkillRating, LearnerValueRating, LearningOutcome,
    LearningOutcomeAssessment, LessonPlan, PortfolioItem, ProjectMilestone, Rubric, RubricCriterion, RubricLevel,
    ProjectTeam, ProjectTeamMember, RubricRating, SchemeOfWork, SchemeWeek, Skill, TeacherObservation,
)


def serializer_for(model, read_only=()):
    meta = type("Meta", (), {"model": model, "fields": "__all__", "read_only_fields": ("created_at", "updated_at", "deleted_at", "is_deleted") + tuple(read_only)})
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})


CompetencySerializer = serializer_for(Competency)
AssessmentScaleSerializer = serializer_for(AssessmentScale)
CompetencyLevelSerializer = serializer_for(CompetencyLevel)
CompetencyIndicatorSerializer = serializer_for(CompetencyIndicator)
AssessmentTypeSerializer = serializer_for(AssessmentType)
AssessmentSerializer = serializer_for(Assessment, ("created_by", "workflow_status", "submitted_by", "submitted_at", "workflow_locked_at"))
AssessmentResultSerializer = serializer_for(AssessmentResult, ("marked_by", "marked_at"))
CompetencyAssessmentSerializer = serializer_for(CompetencyAssessment, ("assessed_by",))
AssessmentSubmissionSerializer = serializer_for(AssessmentSubmission, ("student", "submitted_at", "status"))
CurriculumFrameworkSerializer = serializer_for(CurriculumFramework)
CurriculumValueSerializer = serializer_for(CurriculumValue)
CurriculumTopicSerializer = serializer_for(CurriculumTopic)
LearningOutcomeSerializer = serializer_for(LearningOutcome)
ActivityOfIntegrationSerializer = serializer_for(ActivityOfIntegration)
RubricSerializer = serializer_for(Rubric)
RubricCriterionSerializer = serializer_for(RubricCriterion)
RubricLevelSerializer = serializer_for(RubricLevel)
RubricRatingSerializer = serializer_for(RubricRating)
AssessmentPolicySerializer = serializer_for(AssessmentPolicy)
AssessmentEvidenceSerializer = serializer_for(AssessmentEvidence, ("captured_by", "captured_at"))
CurriculumLearningAreaSerializer = serializer_for(CurriculumLearningArea)
SchemeOfWorkSerializer = serializer_for(SchemeOfWork, ("prepared_by", "submitted_at", "reviewed_by", "reviewed_at"))
SchemeWeekSerializer = serializer_for(SchemeWeek)
LessonPlanSerializer = serializer_for(LessonPlan, ("prepared_by", "reviewed_by", "reviewed_at"))
SkillSerializer = serializer_for(Skill)
LearningOutcomeAssessmentSerializer = serializer_for(LearningOutcomeAssessment, ("assessed_by", "assessed_at"))
LearnerSkillRatingSerializer = serializer_for(LearnerSkillRating, ("assessed_by", "assessed_at"))
LearnerValueRatingSerializer = serializer_for(LearnerValueRating, ("assessed_by", "assessed_at"))
PortfolioItemSerializer = serializer_for(PortfolioItem, ("uploaded_by", "verified_by", "verified_at"))
ProjectMilestoneSerializer = serializer_for(ProjectMilestone)
TeacherObservationSerializer = serializer_for(TeacherObservation, ("observed_by",))
AssessmentReviewSerializer = serializer_for(AssessmentReview, ("reviewer", "reviewed_at"))
EvidenceAssetSerializer = serializer_for(EvidenceAsset, ("captured_by",))
ProjectTeamSerializer = serializer_for(ProjectTeam)
ProjectTeamMemberSerializer = serializer_for(ProjectTeamMember)
