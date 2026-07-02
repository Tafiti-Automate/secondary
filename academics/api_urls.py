from rest_framework.routers import DefaultRouter

from .api import (
    AcademicYearViewSet, CalendarEventViewSet, ClassLevelViewSet,
    DepartmentViewSet, SchoolProfileViewSet, StreamViewSet,
    SubjectAllocationViewSet, SubjectCombinationViewSet, SubjectViewSet,
    TermViewSet,
)

router = DefaultRouter()
router.register("school", SchoolProfileViewSet, basename="school")
router.register("academic-years", AcademicYearViewSet, basename="academic-year")
router.register("terms", TermViewSet, basename="term")
router.register("departments", DepartmentViewSet, basename="department")
router.register("class-levels", ClassLevelViewSet, basename="class-level")
router.register("streams", StreamViewSet, basename="stream")
router.register("subjects", SubjectViewSet, basename="subject")
router.register("subject-combinations", SubjectCombinationViewSet, basename="subject-combination")
router.register("subject-allocations", SubjectAllocationViewSet, basename="subject-allocation")
router.register("calendar", CalendarEventViewSet, basename="calendar-event")
urlpatterns = router.urls
