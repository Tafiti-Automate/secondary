import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from academics.models import Stream, Subject, Term
from accounts.models import User
from config.models import BaseModel
from students.models import Student


class AttendanceSession(BaseModel):
    SESSION_TYPES = [("daily", "Daily roll call"), ("subject", "Subject attendance"), ("activity", "Academic activity")]
    term = models.ForeignKey(Term, related_name="attendance_sessions", on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, related_name="attendance_sessions", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="attendance_sessions", on_delete=models.SET_NULL, null=True, blank=True)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default="daily")
    date = models.DateField(default=timezone.localdate)
    period_label = models.CharField(max_length=40, blank=True)
    taken_by = models.ForeignKey(User, related_name="taken_attendance_sessions", on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("submitted", "Submitted"), ("verified", "Verified")], default="submitted")

    class Meta:
        ordering = ["-date", "stream"]
        constraints = [models.UniqueConstraint(fields=["stream", "date", "session_type", "subject", "period_label"], condition=Q(is_deleted=False), name="unique_active_attendance_session")]

    def clean(self):
        if self.session_type == "subject" and not self.subject_id:
            raise ValidationError({"subject": "A subject is required for subject attendance."})
        if self.stream_id and self.term_id and self.stream.academic_year_id != self.term.academic_year_id:
            raise ValidationError("The stream and term must be in the same academic year.")

    def __str__(self):
        return f"{self.stream} · {self.date} · {self.get_session_type_display()}"


class AttendanceRecord(BaseModel):
    STATUS_CHOICES = [("present", "Present"), ("absent", "Absent"), ("late", "Late"), ("excused", "Permission"), ("sick", "Sick")]
    session = models.ForeignKey(AttendanceSession, related_name="records", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, related_name="attendance_records", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="present")
    arrival_time = models.TimeField(null=True, blank=True)
    reason = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)
    capture_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source = models.CharField(max_length=20, choices=[("web", "Web register"), ("offline", "Offline device"), ("qr", "QR code"), ("biometric", "Biometric adapter"), ("import", "Imported")], default="web")
    device_id = models.CharField(max_length=100, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["student__first_name", "student__last_name"]
        constraints = [models.UniqueConstraint(fields=["session", "student"], condition=Q(is_deleted=False), name="unique_active_attendance_record")]

    def clean(self):
        if self.session_id and self.student_id and self.student.stream_id != self.session.stream_id:
            raise ValidationError({"student": "Student is not in this attendance session's stream."})

    def __str__(self):
        return f"{self.student} · {self.status}"


class AttendanceIdentity(BaseModel):
    """External attendance identity. Biometric templates stay with the provider, never here."""
    PROVIDERS = [("qr", "QR code"), ("biometric", "Biometric provider"), ("external", "External system")]
    student = models.ForeignKey(Student, related_name="attendance_identities", on_delete=models.CASCADE)
    provider = models.CharField(max_length=20, choices=PROVIDERS)
    external_reference = models.CharField(max_length=180)
    label = models.CharField(max_length=100, blank=True)
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    enrolled_by = models.ForeignKey(User, related_name="enrolled_attendance_identities", on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["student", "provider"]
        constraints = [models.UniqueConstraint(fields=["provider", "external_reference"], condition=Q(is_deleted=False), name="unique_attendance_external_identity")]

    def clean(self):
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError({"valid_until": "Expiry cannot precede activation."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.get_provider_display()}"


class AttendanceAlert(BaseModel):
    TYPES = [("absence", "Repeated absence"), ("late", "Repeated lateness"), ("safeguarding", "Safeguarding concern"), ("missing", "Unexplained missing learner")]
    student = models.ForeignKey(Student, related_name="attendance_alerts", on_delete=models.CASCADE)
    session = models.ForeignKey(AttendanceSession, related_name="alerts", on_delete=models.SET_NULL, null=True, blank=True)
    alert_type = models.CharField(max_length=20, choices=TYPES, default="absence")
    severity = models.CharField(max_length=16, choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")], default="medium")
    summary = models.CharField(max_length=220)
    status = models.CharField(max_length=20, choices=[("open", "Open"), ("reviewing", "Under review"), ("resolved", "Resolved")], default="open")
    assigned_to = models.ForeignKey(User, related_name="assigned_attendance_alerts", on_delete=models.SET_NULL, null=True, blank=True)
    resolved_by = models.ForeignKey(User, related_name="resolved_attendance_alerts", on_delete=models.SET_NULL, null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student} · {self.get_alert_type_display()}"


class AttendanceIntervention(BaseModel):
    student = models.ForeignKey(Student, related_name="attendance_interventions", on_delete=models.CASCADE)
    alert = models.ForeignKey(AttendanceAlert, related_name="interventions", on_delete=models.SET_NULL, null=True, blank=True)
    intervention_type = models.CharField(max_length=24, choices=[("call", "Parent/guardian call"), ("meeting", "Family meeting"), ("counselling", "Learner counselling"), ("home_visit", "Home visit"), ("referral", "Safeguarding referral"), ("support_plan", "Attendance support plan")])
    action_date = models.DateField(default=timezone.localdate)
    details = models.TextField()
    outcome = models.TextField(blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[("planned", "Planned"), ("completed", "Completed"), ("follow_up", "Follow-up required")], default="planned")
    recorded_by = models.ForeignKey(User, related_name="recorded_attendance_interventions", on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["-action_date", "-created_at"]

    def clean(self):
        if self.alert_id and self.student_id and self.alert.student_id != self.student_id:
            raise ValidationError({"alert": "The alert belongs to another learner."})
        if self.follow_up_date and self.follow_up_date < self.action_date:
            raise ValidationError({"follow_up_date": "Follow-up cannot precede the intervention."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.get_intervention_type_display()}"


class TeacherAttendance(BaseModel):
    teacher = models.ForeignKey(User, related_name="teacher_attendance", on_delete=models.CASCADE, limit_choices_to={"role": "teacher"})
    date = models.DateField(default=timezone.localdate)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[("present", "Present"), ("absent", "Absent"), ("late", "Late"), ("leave", "On leave")], default="present")
    remarks = models.CharField(max_length=180, blank=True)
    recorded_by = models.ForeignKey(User, related_name="recorded_teacher_attendance", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-date", "teacher"]
        constraints = [models.UniqueConstraint(fields=["teacher", "date"], condition=Q(is_deleted=False), name="unique_active_teacher_attendance")]

    def __str__(self):
        return f"{self.teacher} · {self.date}"
