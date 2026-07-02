from rest_framework.routers import DefaultRouter

from .api import (
    ActivityOfIntegrationViewSet, AssessmentEvidenceViewSet, AssessmentPolicyViewSet,
    AssessmentResultViewSet, AssessmentReviewViewSet, AssessmentTypeViewSet, AssessmentViewSet,
    CompetencyAssessmentViewSet, CompetencyIndicatorViewSet, CompetencyLevelViewSet,
    CompetencyViewSet, CurriculumFrameworkViewSet, CurriculumLearningAreaViewSet,
    CurriculumTopicViewSet, CurriculumValueViewSet, LearnerSkillRatingViewSet,
    LearnerValueRatingViewSet, LearningOutcomeAssessmentViewSet, LearningOutcomeViewSet,
    LessonPlanViewSet, PortfolioItemViewSet, RubricCriterionViewSet, RubricLevelViewSet,
    RubricRatingViewSet, RubricViewSet, SchemeOfWorkViewSet, SchemeWeekViewSet,
    SkillViewSet, SubmissionViewSet, TeacherObservationViewSet,
)

router = DefaultRouter()
router.register("competencies", CompetencyViewSet, basename="competency")
router.register("competency-levels", CompetencyLevelViewSet, basename="competency-level")
router.register("competency-indicators", CompetencyIndicatorViewSet, basename="competency-indicator")
router.register("assessment-types", AssessmentTypeViewSet, basename="assessment-type")
router.register("assessments", AssessmentViewSet, basename="assessment")
router.register("results", AssessmentResultViewSet, basename="assessment-result")
router.register("competency-assessments", CompetencyAssessmentViewSet, basename="competency-assessment")
router.register("submissions", SubmissionViewSet, basename="submission")
router.register("curriculum-frameworks", CurriculumFrameworkViewSet, basename="curriculum-framework")
router.register("curriculum-values", CurriculumValueViewSet, basename="curriculum-value")
router.register("curriculum-learning-areas", CurriculumLearningAreaViewSet, basename="curriculum-learning-area")
router.register("curriculum-topics", CurriculumTopicViewSet, basename="curriculum-topic")
router.register("learning-outcomes", LearningOutcomeViewSet, basename="learning-outcome")
router.register("activities-of-integration", ActivityOfIntegrationViewSet, basename="activity-of-integration")
router.register("rubrics", RubricViewSet, basename="rubric")
router.register("rubric-criteria", RubricCriterionViewSet, basename="rubric-criterion")
router.register("rubric-levels", RubricLevelViewSet, basename="rubric-level")
router.register("rubric-ratings", RubricRatingViewSet, basename="rubric-rating")
router.register("assessment-policies", AssessmentPolicyViewSet, basename="assessment-policy")
router.register("evidence", AssessmentEvidenceViewSet, basename="assessment-evidence")
router.register("schemes-of-work", SchemeOfWorkViewSet, basename="scheme-of-work")
router.register("scheme-weeks", SchemeWeekViewSet, basename="scheme-week")
router.register("lesson-plans", LessonPlanViewSet, basename="lesson-plan")
router.register("skills", SkillViewSet, basename="skill")
router.register("learning-outcome-ratings", LearningOutcomeAssessmentViewSet, basename="learning-outcome-rating")
router.register("skill-ratings", LearnerSkillRatingViewSet, basename="skill-rating")
router.register("value-ratings", LearnerValueRatingViewSet, basename="value-rating")
router.register("portfolio-items", PortfolioItemViewSet, basename="portfolio-item")
router.register("teacher-observations", TeacherObservationViewSet, basename="teacher-observation")
router.register("reviews", AssessmentReviewViewSet, basename="assessment-review")
urlpatterns = router.urls
