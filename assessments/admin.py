from django.contrib import admin

from .models import (
    ActivityOfIntegration, Assessment, AssessmentEvidence, AssessmentPolicy, AssessmentResult,
    AssessmentReview, AssessmentScale, AssessmentSubmission, AssessmentType, Competency, CompetencyAssessment,
    CompetencyIndicator, CompetencyLevel, CurriculumFramework, CurriculumLearningArea,
    CurriculumTopic, CurriculumValue, LearnerSkillRating, LearnerValueRating, LearningOutcome,
    LearningOutcomeAssessment, LessonPlan, PortfolioItem, ProjectMilestone, Rubric, RubricCriterion, RubricLevel,
    RubricRating, SchemeOfWork, SchemeWeek, Skill, TeacherObservation,
)


admin.site.register([
    AssessmentScale, Competency, CompetencyLevel, CompetencyIndicator, CurriculumFramework, CurriculumValue,
    CurriculumLearningArea, CurriculumTopic, LearningOutcome, ActivityOfIntegration, Rubric,
    RubricCriterion, RubricLevel, RubricRating, AssessmentPolicy, AssessmentType, Assessment,
    AssessmentResult, CompetencyAssessment, AssessmentSubmission, AssessmentEvidence,
    SchemeOfWork, SchemeWeek, LessonPlan, Skill, LearningOutcomeAssessment, LearnerSkillRating,
    LearnerValueRating, PortfolioItem, ProjectMilestone, TeacherObservation, AssessmentReview,
])
