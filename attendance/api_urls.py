from rest_framework.routers import DefaultRouter
from .api import AttendanceRecordViewSet, AttendanceSessionViewSet, TeacherAttendanceViewSet

router = DefaultRouter()
router.register("sessions", AttendanceSessionViewSet, basename="attendance-session")
router.register("records", AttendanceRecordViewSet, basename="attendance-record")
router.register("teachers", TeacherAttendanceViewSet, basename="teacher-attendance")
urlpatterns = router.urls
