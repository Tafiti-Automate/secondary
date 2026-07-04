from rest_framework.routers import DefaultRouter

from .api import EnrollmentViewSet, GuardianViewSet, PromotionViewSet, ScopedStudentViewSet, StudentAccommodationViewSet, StudentAchievementViewSet, StudentGuardianViewSet, StudentInterestViewSet, StudentMovementViewSet, SubjectRegistrationViewSet

router = DefaultRouter()
router.register("students", ScopedStudentViewSet, basename="student")
router.register("guardians", GuardianViewSet, basename="guardian")
router.register("student-guardians", StudentGuardianViewSet, basename="student-guardian")
router.register("enrollments", EnrollmentViewSet, basename="enrollment")
router.register("subject-registrations", SubjectRegistrationViewSet, basename="subject-registration")
router.register("movements", StudentMovementViewSet, basename="student-movement")
router.register("promotions", PromotionViewSet, basename="promotion")
router.register("accommodations", StudentAccommodationViewSet, basename="student-accommodation")
router.register("interests", StudentInterestViewSet, basename="student-interest")
router.register("achievements", StudentAchievementViewSet, basename="student-achievement")
urlpatterns = router.urls
