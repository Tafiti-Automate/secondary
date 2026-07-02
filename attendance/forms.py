from config.forms import StyledModelForm
from .models import AttendanceSession, TeacherAttendance


class AttendanceSessionForm(StyledModelForm):
    class Meta:
        model = AttendanceSession
        fields = ("term", "stream", "session_type", "subject", "date", "period_label", "notes", "status")


class TeacherAttendanceForm(StyledModelForm):
    class Meta:
        model = TeacherAttendance
        fields = ("teacher", "date", "check_in", "check_out", "status", "remarks")
