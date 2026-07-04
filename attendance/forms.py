from config.forms import StyledModelForm
from .models import AttendanceAlert, AttendanceIdentity, AttendanceIntervention, AttendanceSession, TeacherAttendance


class AttendanceSessionForm(StyledModelForm):
    class Meta:
        model = AttendanceSession
        fields = ("term", "stream", "session_type", "subject", "date", "period_label", "notes", "status")


class TeacherAttendanceForm(StyledModelForm):
    class Meta:
        model = TeacherAttendance
        fields = ("teacher", "date", "check_in", "check_out", "status", "remarks")


class AttendanceIdentityForm(StyledModelForm):
    class Meta:
        model = AttendanceIdentity
        fields = ("student", "provider", "external_reference", "label", "valid_from", "valid_until", "is_active")


class AttendanceAlertForm(StyledModelForm):
    class Meta:
        model = AttendanceAlert
        fields = ("student", "session", "alert_type", "severity", "summary", "status", "assigned_to")


class AttendanceInterventionForm(StyledModelForm):
    class Meta:
        model = AttendanceIntervention
        fields = ("student", "alert", "intervention_type", "action_date", "details", "outcome", "follow_up_date", "status")
