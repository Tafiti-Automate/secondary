from rest_framework.routers import DefaultRouter
from .api import (
    ExamSessionViewSet, ExaminationResultViewSet, ExaminationViewSet, GradeBoundaryViewSet,
    GradeScaleViewSet, UNEBCandidateSubjectViewSet, UNEBCandidateViewSet,
    UNEBContinuousAssessmentViewSet, UNEBExportBatchViewSet,
    UpperAssessmentComponentViewSet, UpperAssessmentPlanViewSet, UpperSubjectResultViewSet,
)

router = DefaultRouter()
router.register("grade-scales", GradeScaleViewSet, basename="grade-scale")
router.register("grade-boundaries", GradeBoundaryViewSet, basename="grade-boundary")
router.register("sessions", ExamSessionViewSet, basename="exam-session")
router.register("examinations", ExaminationViewSet, basename="examination")
router.register("results", ExaminationResultViewSet, basename="examination-result")
router.register("uneb-candidates", UNEBCandidateViewSet, basename="uneb-candidate")
router.register("uneb-candidate-subjects", UNEBCandidateSubjectViewSet, basename="uneb-candidate-subject")
router.register("uneb-continuous-assessment", UNEBContinuousAssessmentViewSet, basename="uneb-ca")
router.register("uneb-export-batches", UNEBExportBatchViewSet, basename="uneb-export-batch")
router.register("upper-assessment-plans", UpperAssessmentPlanViewSet, basename="upper-assessment-plan")
router.register("upper-assessment-components", UpperAssessmentComponentViewSet, basename="upper-assessment-component")
router.register("upper-subject-results", UpperSubjectResultViewSet, basename="upper-subject-result")
urlpatterns = router.urls
