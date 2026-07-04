from django.urls import path
from django.urls import reverse_lazy
from .forms import AttendanceAlertForm, AttendanceIdentityForm, AttendanceInterventionForm
from .models import AttendanceAlert, AttendanceIdentity, AttendanceIntervention
from .views import AttendanceAlertListView, AttendanceAnalyticsView, AttendanceCreateView, AttendanceDeleteView, AttendanceDetailView, AttendanceListView, AttendanceWorkflowCreateView, TakeAttendanceView, TeacherAttendanceCreateView, TeacherAttendanceListView

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
    path("alerts/", AttendanceAlertListView.as_view(), name="alerts"),
    path("alerts/add/", AttendanceWorkflowCreateView.as_view(model=AttendanceAlert, form_class=AttendanceAlertForm, success_url=reverse_lazy("attendance:alerts"), extra_context={"page_title": "Create attendance alert", "eyebrow": "Safeguarding", "submit_label": "Save alert"}), name="alert-add"),
    path("interventions/add/", AttendanceWorkflowCreateView.as_view(model=AttendanceIntervention, form_class=AttendanceInterventionForm, success_url=reverse_lazy("attendance:alerts"), extra_context={"page_title": "Record attendance intervention", "eyebrow": "Learner support", "submit_label": "Save intervention"}), name="intervention-add"),
    path("identities/add/", AttendanceWorkflowCreateView.as_view(model=AttendanceIdentity, form_class=AttendanceIdentityForm, success_url=reverse_lazy("attendance:list"), extra_context={"page_title": "Link attendance identity", "eyebrow": "QR / biometric adapter", "submit_label": "Save identity"}), name="identity-add"),
]
