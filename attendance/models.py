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

    class Meta:
        ordering = ["student__first_name", "student__last_name"]
        constraints = [models.UniqueConstraint(fields=["session", "student"], condition=Q(is_deleted=False), name="unique_active_attendance_record")]

    def clean(self):
        if self.session_id and self.student_id and self.student.stream_id != self.session.stream_id:
            raise ValidationError({"student": "Student is not in this attendance session's stream."})

    def __str__(self):
        return f"{self.student} · {self.status}"


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
