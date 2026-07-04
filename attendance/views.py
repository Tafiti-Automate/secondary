from collections import Counter

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from config.crud import AuditedFormMixin, SoftDeleteView
from config.audit import record_audit
from config.mixins import ACADEMIC_MANAGERS, AcademicManagerRequiredMixin, AcademicStaffRequiredMixin
from students.models import Student
from .forms import AttendanceAlertForm, AttendanceIdentityForm, AttendanceInterventionForm, AttendanceSessionForm, TeacherAttendanceForm
from .models import AttendanceAlert, AttendanceIdentity, AttendanceIntervention, AttendanceRecord, AttendanceSession, TeacherAttendance


def attendance_sessions(user):
    qs = AttendanceSession.objects.filter(is_deleted=False).select_related("term", "stream", "subject", "taken_by").annotate(
        total_records=Count("records", filter=Q(records__is_deleted=False)),
        absent_records=Count("records", filter=Q(records__is_deleted=False, records__status="absent")),
        present_records=Count("records", filter=Q(records__is_deleted=False, records__status="present")),
    )
    if user.role == "teacher" and not user.is_superuser:
        qs = qs.filter(Q(taken_by=user) | Q(stream__class_teacher=user) | Q(stream__subject_allocations__teacher=user)).distinct()
    return qs.order_by("-date", "stream__class_level__level", "stream__name")


class AttendanceListView(AcademicStaffRequiredMixin, ListView):
    template_name = "attendance/session_list.html"
    context_object_name = "sessions"
    paginate_by = 20

    def get_queryset(self):
        return attendance_sessions(self.request.user)


class AttendanceCreateView(AcademicStaffRequiredMixin, AuditedFormMixin, CreateView):
    model = AttendanceSession
    form_class = AttendanceSessionForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Take attendance", "eyebrow": "Attendance", "submit_label": "Start register"}

    def form_valid(self, form):
        form.instance.taken_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("attendance:take", args=[self.object.pk])


class TakeAttendanceView(AcademicStaffRequiredMixin, View):
    template_name = "attendance/take_attendance.html"

    def session(self, request, pk):
        return get_object_or_404(attendance_sessions(request.user), pk=pk)

    def get(self, request, pk):
        session = self.session(request, pk)
        students = Student.objects.filter(stream=session.stream, is_deleted=False, is_active=True)
        records = {record.student_id: record for record in AttendanceRecord.objects.filter(session=session, is_deleted=False)}
        return render(request, self.template_name, {"session": session, "rows": [{"student": student, "record": records.get(student.pk)} for student in students], "statuses": AttendanceRecord.STATUS_CHOICES})

    @transaction.atomic
    def post(self, request, pk):
        session = self.session(request, pk)
        saved = 0
        for student in Student.objects.filter(stream=session.stream, is_deleted=False, is_active=True):
            status = request.POST.get(f"status_{student.pk}", "present")
            if status not in dict(AttendanceRecord.STATUS_CHOICES):
                status = "present"
            AttendanceRecord.objects.update_or_create(session=session, student=student, defaults={"status": status, "reason": request.POST.get(f"reason_{student.pk}", "").strip(), "is_deleted": False})
            if status == "absent":
                from communications.models import Notification
                recipients = []
                if student.parent_id:
                    recipients.append(student.parent)
                recipients += [link.guardian.user for link in student.guardian_links.filter(receives_alerts=True, guardian__user__isnull=False, is_deleted=False).select_related("guardian__user")]
                for recipient in set(recipients):
                    Notification.objects.get_or_create(recipient=recipient, title=f"Absence alert · {student.full_name} · {session.date:%d %b}", channel="in_app", defaults={"message": f"{student.full_name} was marked absent from {session.get_session_type_display().lower()} on {session.date:%d %B %Y}.", "status": "sent", "link": reverse("students:detail", args=[student.pk])})
                absences = AttendanceRecord.objects.filter(student=student, status="absent", is_deleted=False).count()
                if absences >= 3:
                    AttendanceAlert.objects.get_or_create(
                        student=student, session=session, alert_type="absence", is_deleted=False,
                        defaults={"severity": "high" if absences >= 6 else "medium", "summary": f"{absences} recorded absences require follow-up."},
                    )
            saved += 1
        messages.success(request, f"Attendance saved for {saved} student(s).")
        record_audit(request, "attendance", session, f"Saved attendance for {saved} student(s)", {"saved": saved})
        return redirect("attendance:take", pk=pk)


class AttendanceDetailView(AcademicStaffRequiredMixin, DetailView):
    template_name = "attendance/session_detail.html"
    context_object_name = "session"

    def get_queryset(self):
        return attendance_sessions(self.request.user).prefetch_related("records__student")


class AttendanceDeleteView(AcademicManagerRequiredMixin, SoftDeleteView):
    model = AttendanceSession
    success_url_name = "attendance:list"


class TeacherAttendanceListView(AcademicManagerRequiredMixin, ListView):
    queryset = TeacherAttendance.objects.filter(is_deleted=False).select_related("teacher", "recorded_by")
    template_name = "attendance/teacher_list.html"
    context_object_name = "records"
    paginate_by = 25


class TeacherAttendanceCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = TeacherAttendance
    form_class = TeacherAttendanceForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("attendance:teachers")
    audit_action = "create"
    extra_context = {"page_title": "Record teacher attendance", "eyebrow": "Staff attendance", "submit_label": "Save attendance"}

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)


class AttendanceAnalyticsView(AcademicStaffRequiredMixin, View):
    def get(self, request):
        sessions = attendance_sessions(request.user)
        records = AttendanceRecord.objects.filter(session__in=sessions, is_deleted=False)
        totals = records.values("status").annotate(total=Count("id"))
        summary = {item["status"]: item["total"] for item in totals}
        at_risk = Student.objects.filter(attendance_records__session__in=sessions, attendance_records__status="absent", attendance_records__is_deleted=False).annotate(absences=Count("attendance_records")).filter(absences__gte=3).order_by("-absences")[:20]
        return render(request, "attendance/analytics.html", {"summary": summary, "at_risk": at_risk, "total": sum(summary.values()), "open_alerts": AttendanceAlert.objects.filter(status__in=("open", "reviewing"), is_deleted=False)[:10]})


class AttendanceAlertListView(AcademicStaffRequiredMixin, ListView):
    template_name = "attendance/alert_list.html"
    context_object_name = "alerts"
    paginate_by = 30

    def get_queryset(self):
        qs = AttendanceAlert.objects.filter(is_deleted=False).select_related("student", "session", "assigned_to")
        if self.request.user.role == "teacher" and not self.request.user.is_superuser:
            qs = qs.filter(Q(assigned_to=self.request.user) | Q(student__stream__class_teacher=self.request.user)).distinct()
        return qs


class AttendanceWorkflowCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    template_name = "shared/form.html"
    audit_action = "create"

    def form_valid(self, form):
        if isinstance(form.instance, AttendanceIdentity):
            form.instance.enrolled_by = self.request.user
        if isinstance(form.instance, AttendanceIntervention):
            form.instance.recorded_by = self.request.user
        return super().form_valid(form)
