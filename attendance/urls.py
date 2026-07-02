from django.urls import path
from .views import AttendanceAnalyticsView, AttendanceCreateView, AttendanceDeleteView, AttendanceDetailView, AttendanceListView, TakeAttendanceView, TeacherAttendanceCreateView, TeacherAttendanceListView

app_name = "attendance"
urlpatterns = [
    path("", AttendanceListView.as_view(), name="list"),
    path("take/", AttendanceCreateView.as_view(), name="add"),
    path("<int:pk>/", AttendanceDetailView.as_view(), name="detail"),
    path("<int:pk>/register/", TakeAttendanceView.as_view(), name="take"),
    path("<int:pk>/delete/", AttendanceDeleteView.as_view(), name="delete"),
    path("analytics/overview/", AttendanceAnalyticsView.as_view(), name="analytics"),
    path("teachers/", TeacherAttendanceListView.as_view(), name="teachers"),
    path("teachers/add/", TeacherAttendanceCreateView.as_view(), name="teacher-add"),
]
