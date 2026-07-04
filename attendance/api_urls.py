from rest_framework.routers import DefaultRouter
from .api import AttendanceAlertViewSet, AttendanceIdentityViewSet, AttendanceInterventionViewSet, AttendanceRecordViewSet, AttendanceSessionViewSet, TeacherAttendanceViewSet

router = DefaultRouter()
router.register("sessions", AttendanceSessionViewSet, basename="attendance-session")
router.register("records", AttendanceRecordViewSet, basename="attendance-record")
router.register("teachers", TeacherAttendanceViewSet, basename="teacher-attendance")
router.register("identities", AttendanceIdentityViewSet, basename="attendance-identity")
router.register("alerts", AttendanceAlertViewSet, basename="attendance-alert")
router.register("interventions", AttendanceInterventionViewSet, basename="attendance-intervention")
urlpatterns = router.urls
