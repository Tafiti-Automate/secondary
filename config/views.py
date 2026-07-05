from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, TemplateView

from academics.models import CalendarEvent, Stream, SubjectAllocation, Term
from assessments.models import Assessment, CompetencyAssessment, LearningOutcomeAssessment
from attendance.models import AttendanceRecord
from communications.models import Announcement, Notification
from exams.models import Examination
from reports.models import ReportCard, ReportSubjectResult
from students.models import Student
from timetables.models import TimetableEntry
from academics.models import SchoolProfile
from config.forms import SchoolModulesForm
from config.mixins import AcademicManagerRequiredMixin
from config.models import SchoolModule
from config.modules import MODULES, PRESETS, clear_module_cache, get_enabled_modules, get_plan_name


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        current_term = Term.objects.filter(is_current=True, is_deleted=False).select_related("academic_year").first()
        requested_term = self.request.GET.get("term")
        if requested_term:
            current_term = Term.objects.filter(pk=requested_term, is_deleted=False).select_related("academic_year").first() or current_term
        today = timezone.localdate()
        context.update({
            "role_label": user.get_role_display(),
            "current_term_obj": current_term,
            "dashboard_terms": Term.objects.filter(is_deleted=False).select_related("academic_year").order_by("-academic_year__start_date", "-number")[:12],
            "dashboard_updated_at": timezone.now(),
            "dashboard_charts": {},
            "announcements": self.visible_announcements(user)[:4],
            "calendar_events": CalendarEvent.objects.filter(is_deleted=False, start_date__gte=today).select_related("term")[:5],
        })
        if self.request.GET.get("refresh") and current_term:
            cache.delete(f"management-dashboard:{current_term.pk}")
        if user.role == "bursar":
            context.update(self.operations_context())
        elif user.is_superuser or user.role in {"super_admin", "headteacher", "director_of_studies"}:
            context.update(self.manager_context(current_term))
        elif user.role == "teacher":
            context.update(self.teacher_context(user, current_term, today))
        elif user.role == "student":
            context.update(self.student_context(user, current_term, today))
        elif user.role == "parent":
            context.update(self.parent_context(user, current_term))
        else:
            context.update(self.manager_context(current_term))
        return context

    def operations_context(self):
        from decimal import Decimal

        from fees.models import Payment, StudentInvoice
        from finance.models import Budget, Expenditure, Income

        school = SchoolProfile.objects.filter(is_deleted=False).first()
        enabled = get_enabled_modules(school)
        payments = Payment.objects.filter(is_deleted=False, is_reversed=False)
        collected = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00") if "fees" in enabled else Decimal("0.00")
        invoices = StudentInvoice.objects.filter(is_deleted=False).exclude(status="cancelled") if "fees" in enabled else StudentInvoice.objects.none()
        outstanding = sum((invoice.balance for invoice in invoices), Decimal("0.00"))
        other_income = Income.objects.filter(is_deleted=False).aggregate(total=Sum("amount"))["total"] or Decimal("0.00") if "finance" in enabled else Decimal("0.00")
        pending = Expenditure.objects.filter(is_deleted=False, status="pending") if "finance" in enabled else Expenditure.objects.none()
        return {
            "dashboard_kind": "operations",
            "operations_enabled": enabled,
            "recent_payments": payments.select_related("invoice__student")[:6] if "fees" in enabled else [],
            "pending_expenditures": pending.select_related("category", "vendor")[:6],
            "stats": [
                {"label": "Fees collected", "value": f"UGX {collected:,.0f}", "tone": "emerald", "icon": "report", "detail": "All unreversed payments"},
                {"label": "Fee balances", "value": f"UGX {outstanding:,.0f}", "tone": "amber", "icon": "alert", "detail": f"{invoices.exclude(status='paid').count()} open invoices"},
                {"label": "Other income", "value": f"UGX {other_income:,.0f}", "tone": "indigo", "icon": "report", "detail": "Non-fee institutional income"},
                {"label": "Pending approvals", "value": pending.count(), "tone": "rose", "icon": "clock", "detail": f"{Budget.objects.filter(is_deleted=False, status='open').count() if 'finance' in enabled else 0} open budgets"},
            ],
        }

    def visible_announcements(self, user):
        now = timezone.now()
        qs = Announcement.objects.filter(is_deleted=False, published_at__lte=now).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
        if user.is_superuser or user.role in {"super_admin", "headteacher", "director_of_studies"}:
            return qs
        audiences = ["all"]
        if user.role == "teacher":
            audiences += ["staff", "teachers"]
        elif user.role == "student":
            audiences += ["students", "stream"]
            if hasattr(user, "student_profile"):
                qs = qs.filter(Q(stream__isnull=True) | Q(stream=user.student_profile.stream))
        elif user.role == "parent":
            audiences += ["parents", "stream"]
            qs = qs.filter(Q(stream__isnull=True) | Q(stream__students__parent=user) | Q(stream__students__guardian_links__guardian__user=user)).distinct()
        return qs.filter(audience__in=audiences)

    def manager_context(self, term):
        reports = ReportCard.objects.filter(term=term, is_deleted=False) if term else ReportCard.objects.none()
        attendance = AttendanceRecord.objects.filter(session__term=term, is_deleted=False) if term else AttendanceRecord.objects.none()
        cache_key = f"management-dashboard:{term.pk if term else 'none'}"
        cached = cache.get(cache_key)
        if cached is None:
            attendance_total = attendance.count()
            present = attendance.filter(status="present").count()
            active_students = Student.objects.filter(is_deleted=False, is_active=True)
            cached = {
                "student_count": active_students.count(),
                "male_count": active_students.filter(gender="male").count(),
                "female_count": active_students.filter(gender="female").count(),
                "stream_count": Stream.objects.filter(is_deleted=False, academic_year__is_current=True).count(),
                "attendance_rate": f"{(present / attendance_total * 100):.1f}%" if attendance_total else "—",
                "report_count": reports.count(),
                "published_reports": reports.filter(status__in=("published", "locked")).count(),
                "missing_reports": reports.filter(has_missing_marks=True).count(),
                "pending_mark_entries": Examination.objects.filter(term=term, status__in=("draft", "entry"), is_deleted=False).count() if term else 0,
                "performance": list(ReportSubjectResult.objects.filter(report_card__term=term, is_deleted=False).values("subject__name").annotate(average=Avg("final_score")).order_by("-average")[:8]) if term else [],
                "class_breakdown": list(active_students.values("stream__class_level__name", "stream__name").annotate(total=Count("id")).order_by("stream__class_level__level", "stream__name")),
            }
            cache.set(cache_key, cached, 60)
        previous_term = Term.objects.filter(end_date__lt=term.start_date, is_deleted=False).order_by("-end_date").first() if term else None
        previous_scores = {
            item["student_id"]: item["average_score"]
            for item in ReportCard.objects.filter(term=previous_term, has_missing_marks=False, is_deleted=False).values("student_id", "average_score")
        } if previous_term else {}
        improvement = []
        for card in reports.filter(has_missing_marks=False).select_related("student", "stream"):
            previous = previous_scores.get(card.student_id)
            if previous is not None and card.average_score > previous:
                improvement.append({"student": card.student, "stream": card.stream, "change": card.average_score - previous})
        improvement.sort(key=lambda item: item["change"], reverse=True)

        history = list(
            ReportCard.objects.filter(is_deleted=False, has_missing_marks=False)
            .values("term__academic_year__name", "term__number")
            .annotate(average=Avg("average_score"), learners=Count("student", distinct=True))
            .order_by("term__academic_year__start_date", "term__number")
        )[-7:]
        daily_attendance = list(
            attendance.values("session__date")
            .annotate(total=Count("id"), present=Count("id", filter=Q(status="present")))
            .order_by("session__date")
        )[-14:]
        attendance_totals = {item["status"]: item["total"] for item in attendance.values("status").annotate(total=Count("id"))}
        attendance_states = [{"status": key, "total": attendance_totals[key]} for key in ("present", "absent", "late", "excused", "sick") if key in attendance_totals]
        class_performance = list(
            reports.filter(has_missing_marks=False)
            .values("stream__class_level__name", "stream__name")
            .annotate(average=Avg("average_score"), learners=Count("student", distinct=True))
            .order_by("stream__class_level__level", "stream__name")
        )
        outcome_rows = list(
            LearningOutcomeAssessment.objects.filter(term=term, is_deleted=False)
            .values("scale_level__name", "level").annotate(total=Count("id")).order_by("scale_level__numeric_value", "level")
        ) if term else []
        legacy_outcome_labels = dict(LearningOutcomeAssessment.LEVEL_CHOICES)
        outcome_achievement = [
            {"level": item["scale_level__name"] or legacy_outcome_labels.get(item["level"], item["level"]), "total": item["total"]}
            for item in outcome_rows
        ]
        competency_trends = list(
            CompetencyAssessment.objects.filter(assessment__term=term, scale_level__isnull=False, is_deleted=False)
            .values("competency__name")
            .annotate(average=Avg("scale_level__numeric_value"), ratings=Count("id"))
            .order_by("competency__display_order")[:8]
        ) if term else []
        teacher_workload = list(
            SubjectAllocation.objects.filter(term=term, is_deleted=False, is_active=True)
            .values("teacher__first_name", "teacher__last_name")
            .annotate(subjects=Count("subject", distinct=True), streams=Count("stream", distinct=True), lessons=Count("id"))
            .order_by("teacher__first_name")[:8]
        ) if term else []
        assessment_pipeline = list(
            Assessment.objects.filter(term=term, is_deleted=False)
            .values("workflow_status").annotate(total=Count("id")).order_by("workflow_status")
        ) if term else []
        current_average = reports.filter(has_missing_marks=False).aggregate(value=Avg("average_score"))["value"]
        previous_average = ReportCard.objects.filter(term=previous_term, has_missing_marks=False, is_deleted=False).aggregate(value=Avg("average_score"))["value"] if previous_term else None
        performance_change = float(current_average - previous_average) if current_average is not None and previous_average is not None else None
        previous_attendance = AttendanceRecord.objects.filter(session__term=previous_term, is_deleted=False) if previous_term else AttendanceRecord.objects.none()
        previous_attendance_total = previous_attendance.count()
        previous_attendance_rate = previous_attendance.filter(status="present").count() / previous_attendance_total * 100 if previous_attendance_total else None
        current_attendance_rate = float(cached["attendance_rate"].rstrip("%")) if cached["attendance_rate"] != "—" else None
        attendance_change = current_attendance_rate - previous_attendance_rate if current_attendance_rate is not None and previous_attendance_rate is not None else None
        subject_performance = cached["performance"]
        status_labels = dict(AttendanceRecord.STATUS_CHOICES)
        workflow_labels = dict(Assessment._meta.get_field("workflow_status").choices)
        dashboard_charts = {
            "performance_history": {
                "type": "line",
                "labels": [f"{item['term__academic_year__name']} T{item['term__number']}" for item in history],
                "datasets": [{"label": "School average", "data": [float(item["average"] or 0) for item in history], "color": "#10b981"}],
                "max": 100,
                "suffix": "%",
            },
            "attendance_daily": {
                "type": "line",
                "labels": [item["session__date"].strftime("%d %b") for item in daily_attendance],
                "datasets": [{"label": "Daily attendance", "data": [round(item["present"] / item["total"] * 100, 1) if item["total"] else 0 for item in daily_attendance], "color": "#6366f1"}],
                "max": 100,
                "suffix": "%",
            },
            "subject_performance": {
                "type": "bar",
                "horizontal": True,
                "labels": [item["subject__name"] for item in subject_performance],
                "datasets": [{"label": "Average", "data": [float(item["average"] or 0) for item in subject_performance], "color": "#0ea5e9"}],
                "max": 100,
                "suffix": "%",
            },
            "class_performance": {
                "type": "bar",
                "labels": [f"{item['stream__class_level__name']} {item['stream__name']}" for item in class_performance],
                "datasets": [{"label": "Class average", "data": [float(item["average"] or 0) for item in class_performance], "color": "#8b5cf6"}],
                "max": 100,
                "suffix": "%",
            },
            "attendance_mix": {
                "type": "doughnut",
                "labels": [status_labels.get(item["status"], item["status"].title()) for item in attendance_states],
                "datasets": [{"label": "Records", "data": [item["total"] for item in attendance_states], "colors": ["#10b981", "#f43f5e", "#f59e0b", "#6366f1", "#06b6d4"]}],
            },
            "outcome_distribution": {
                "type": "doughnut",
                "labels": [item["level"] for item in outcome_achievement],
                "datasets": [{"label": "Ratings", "data": [item["total"] for item in outcome_achievement], "colors": ["#8b5cf6", "#10b981", "#f59e0b", "#f43f5e"]}],
            },
            "competencies": {
                "type": "radar",
                "labels": [item["competency__name"] for item in competency_trends],
                "datasets": [{"label": "Achievement", "data": [round(float(item["average"] or 0), 2) for item in competency_trends], "color": "#14b8a6"}],
                "max": 4,
            },
            "population": {
                "type": "doughnut",
                "labels": ["Female", "Male"],
                "datasets": [{"label": "Learners", "data": [cached["female_count"], cached["male_count"]], "colors": ["#ec4899", "#3b82f6"]}],
            },
            "teacher_workload": {
                "type": "bar",
                "horizontal": True,
                "labels": [(f"{item['teacher__first_name']} {item['teacher__last_name']}").strip() or "Teacher" for item in teacher_workload],
                "datasets": [
                    {"label": "Subjects", "data": [item["subjects"] for item in teacher_workload], "color": "#10b981"},
                    {"label": "Streams", "data": [item["streams"] for item in teacher_workload], "color": "#6366f1"},
                ],
            },
            "assessment_pipeline": {
                "type": "bar",
                "labels": [workflow_labels.get(item["workflow_status"], item["workflow_status"].replace("_", " ").title()) for item in assessment_pipeline],
                "datasets": [{"label": "Assessments", "data": [item["total"] for item in assessment_pipeline], "color": "#f59e0b"}],
            },
        }
        return {
            "dashboard_kind": "management",
            "stats": [
                {"label": "Active students", "value": cached["student_count"], "tone": "emerald", "icon": "users", "detail": f"{cached['female_count']} female · {cached['male_count']} male"},
                {"label": "Teaching streams", "value": cached["stream_count"], "tone": "indigo", "icon": "school", "detail": "Current academic year"},
                {"label": "Attendance rate", "value": cached["attendance_rate"], "tone": "amber", "icon": "check", "detail": "Present records this term", "change": attendance_change},
                {"label": "School average", "value": f"{float(current_average):.1f}%" if current_average is not None else "—", "tone": "rose", "icon": "report", "detail": "Complete learner reports", "change": performance_change},
            ],
            "management_cards": [
                {"label": "Male learners", "value": cached["male_count"]},
                {"label": "Female learners", "value": cached["female_count"]},
                {"label": "Published reports", "value": cached["published_reports"]},
                {"label": "Reports with missing marks", "value": cached["missing_reports"]},
                {"label": "Pending exam entries", "value": cached["pending_mark_entries"]},
            ],
            "class_breakdown": cached["class_breakdown"],
            "performance_json": cached["performance"],
            "dashboard_charts": dashboard_charts,
            "recent_exams": Examination.objects.filter(term=term, is_deleted=False).select_related("subject", "stream")[:6] if term else [],
            "at_risk_students": Student.objects.filter(attendance_records__session__term=term, attendance_records__status="absent", attendance_records__is_deleted=False).annotate(absences=Count("attendance_records")).filter(absences__gte=3).order_by("-absences")[:6] if term else [],
            "most_improved": improvement[:6],
            "learners_needing_support": Student.objects.filter(
                Q(learning_outcome_assessments__scale_level__numeric_value=1)
                | Q(learning_outcome_assessments__scale_level__isnull=True, learning_outcome_assessments__level="needs_support"),
                learning_outcome_assessments__term=term,
                learning_outcome_assessments__is_deleted=False,
            ).annotate(support_count=Count("learning_outcome_assessments")).order_by("-support_count")[:6] if term else [],
            "outcome_achievement": outcome_achievement,
            "competency_trends": competency_trends,
            "teacher_workload": teacher_workload,
        }


    def teacher_context(self, user, term, today):
        allocations = SubjectAllocation.objects.filter(teacher=user, term=term, is_deleted=False).select_related("subject", "stream") if term else SubjectAllocation.objects.none()
        assessments = Assessment.objects.filter(created_by=user, term=term, is_deleted=False).select_related("subject", "stream") if term else Assessment.objects.none()
        exams = Examination.objects.filter(subject__allocations__teacher=user, term=term, is_deleted=False).select_related("subject", "stream").distinct() if term else Examination.objects.none()
        timetable = TimetableEntry.objects.filter(teacher=user, term=term, day_of_week=today.isoweekday(), is_deleted=False).select_related("time_slot", "stream", "subject", "room") if term else []
        subject_performance = list(
            ReportSubjectResult.objects.filter(
                report_card__term=term,
                subject__allocations__teacher=user,
                subject__allocations__term=term,
                final_score__isnull=False,
                is_deleted=False,
            ).values("subject__name").annotate(average=Avg("final_score")).order_by("subject__name").distinct()
        ) if term else []
        workflow = list(assessments.values("workflow_status").annotate(total=Count("id")).order_by("workflow_status"))
        weekly_schedule = list(
            TimetableEntry.objects.filter(teacher=user, term=term, is_deleted=False)
            .values("day_of_week").annotate(total=Count("id")).order_by("day_of_week")
        ) if term else []
        day_names = dict(TimetableEntry.DAYS)
        assessment_progress = []
        for item in assessments.order_by("-assigned_date")[:8]:
            class_size = Student.objects.filter(stream=item.stream, is_deleted=False, is_active=True).count()
            assessment_progress.append({"label": item.title, "value": round(item.marks_entered / class_size * 100, 1) if class_size else 0})
        workflow_labels = dict(Assessment._meta.get_field("workflow_status").choices)
        dashboard_charts = {
            "teacher_performance": {
                "type": "bar", "horizontal": True,
                "labels": [item["subject__name"] for item in subject_performance],
                "datasets": [{"label": "Learner average", "data": [float(item["average"] or 0) for item in subject_performance], "color": "#10b981"}],
                "max": 100, "suffix": "%",
            },
            "marking_progress": {
                "type": "bar",
                "labels": [item["label"] for item in assessment_progress],
                "datasets": [{"label": "Marks entered", "data": [item["value"] for item in assessment_progress], "color": "#6366f1"}],
                "max": 100, "suffix": "%",
            },
            "teacher_workflow": {
                "type": "doughnut",
                "labels": [workflow_labels.get(item["workflow_status"], item["workflow_status"].replace("_", " ").title()) for item in workflow],
                "datasets": [{"label": "Assessments", "data": [item["total"] for item in workflow], "colors": ["#94a3b8", "#3b82f6", "#f59e0b", "#10b981", "#8b5cf6", "#f43f5e"]}],
            },
            "weekly_schedule": {
                "type": "bar",
                "labels": [day_names.get(item["day_of_week"], str(item["day_of_week"])) for item in weekly_schedule],
                "datasets": [{"label": "Lessons", "data": [item["total"] for item in weekly_schedule], "color": "#06b6d4"}],
            },
        }
        return {
            "dashboard_kind": "teacher", "allocations": allocations, "teacher_assessments": assessments[:6], "teacher_exams": exams[:6], "today_timetable": timetable,
            "dashboard_charts": dashboard_charts,
            "stats": [
                {"label": "My allocations", "value": allocations.count(), "tone": "emerald", "icon": "book", "detail": "Subjects and streams"},
                {"label": "Assessments", "value": assessments.count(), "tone": "indigo", "icon": "edit", "detail": "Created this term"},
                {"label": "Pending exam entry", "value": exams.filter(status__in=("draft", "entry")).count(), "tone": "amber", "icon": "clock", "detail": "Requires mark entry"},
                {"label": "Today's lessons", "value": len(timetable), "tone": "rose", "icon": "calendar", "detail": today.strftime("%A, %d %b")},
            ],
        }

    def student_context(self, user, term, today):
        student = getattr(user, "student_profile", None)
        if not student:
            return {"dashboard_kind": "student", "student": None, "stats": []}
        reports = ReportCard.objects.filter(student=student, status__in=("published", "locked"), is_deleted=False)
        assessments = Assessment.objects.filter(stream=student.stream, status="published", is_deleted=False)
        timetable = TimetableEntry.objects.filter(stream=student.stream, term=term, day_of_week=today.isoweekday(), is_deleted=False).select_related("time_slot", "subject", "teacher", "room") if term else []
        attendance = AttendanceRecord.objects.filter(student=student, session__term=term, is_deleted=False) if term else AttendanceRecord.objects.none()
        total = attendance.count()
        present = attendance.filter(status="present").count()
        report_history = list(
            reports.filter(has_missing_marks=False)
            .values("term__academic_year__name", "term__number", "average_score")
            .order_by("term__academic_year__start_date", "term__number")
        )[-7:]
        latest_report = reports.filter(has_missing_marks=False).order_by("-term__academic_year__start_date", "-term__number").first()
        subject_results = list(latest_report.subject_results.filter(is_deleted=False, final_score__isnull=False).values("subject__name", "final_score").order_by("subject__name")) if latest_report else []
        attendance_totals = {item["status"]: item["total"] for item in attendance.values("status").annotate(total=Count("id"))}
        attendance_states = [{"status": key, "total": attendance_totals[key]} for key in ("present", "absent", "late", "excused", "sick") if key in attendance_totals]
        outcome_rows = list(
            LearningOutcomeAssessment.objects.filter(student=student, term=term, is_deleted=False)
            .values("scale_level__name", "level").annotate(total=Count("id")).order_by("scale_level__numeric_value", "level")
        ) if term else []
        legacy_outcome_labels = dict(LearningOutcomeAssessment.LEVEL_CHOICES)
        outcome_states = [
            {"level": item["scale_level__name"] or legacy_outcome_labels.get(item["level"], item["level"]), "total": item["total"]}
            for item in outcome_rows
        ]
        status_labels = dict(AttendanceRecord.STATUS_CHOICES)
        dashboard_charts = {
            "student_history": {
                "type": "line",
                "labels": [f"{item['term__academic_year__name']} T{item['term__number']}" for item in report_history],
                "datasets": [{"label": "Average", "data": [float(item["average_score"] or 0) for item in report_history], "color": "#10b981"}],
                "max": 100, "suffix": "%",
            },
            "student_subjects": {
                "type": "bar", "horizontal": True,
                "labels": [item["subject__name"] for item in subject_results],
                "datasets": [{"label": "Score", "data": [float(item["final_score"] or 0) for item in subject_results], "color": "#6366f1"}],
                "max": 100, "suffix": "%",
            },
            "student_attendance": {
                "type": "doughnut",
                "labels": [status_labels.get(item["status"], item["status"].title()) for item in attendance_states],
                "datasets": [{"label": "Days", "data": [item["total"] for item in attendance_states], "colors": ["#10b981", "#f43f5e", "#f59e0b", "#6366f1", "#06b6d4"]}],
            },
            "student_outcomes": {
                "type": "doughnut",
                "labels": [item["level"] for item in outcome_states],
                "datasets": [{"label": "Outcomes", "data": [item["total"] for item in outcome_states], "colors": ["#8b5cf6", "#10b981", "#f59e0b", "#f43f5e"]}],
            },
        }
        return {
            "dashboard_kind": "student", "student": student, "student_reports": reports[:3], "student_assessments": assessments[:6], "today_timetable": timetable,
            "dashboard_charts": dashboard_charts,
            "stats": [
                {"label": "Current class", "value": str(student.stream or "Not placed"), "tone": "emerald", "icon": "school", "detail": student.student_number or student.admission_number},
                {"label": "Attendance", "value": f"{present / total * 100:.1f}%" if total else "—", "tone": "indigo", "icon": "check", "detail": f"{present} of {total} records present" if total else "No attendance recorded"},
                {"label": "Open assignments", "value": assessments.count(), "tone": "amber", "icon": "edit", "detail": "Published class activities"},
                {"label": "Latest average", "value": f"{float(latest_report.average_score):.1f}%" if latest_report else "—", "tone": "rose", "icon": "report", "detail": str(latest_report.term) if latest_report else "No published report"},
            ],
        }

    def parent_context(self, user, term):
        children = Student.objects.filter(Q(parent=user) | Q(guardian_links__guardian__user=user), is_deleted=False).distinct().select_related("stream")
        reports = ReportCard.objects.filter(student__in=children, status__in=("published", "locked"), is_deleted=False).select_related("student", "term")
        absent = AttendanceRecord.objects.filter(student__in=children, session__term=term, status="absent", is_deleted=False).count() if term else 0
        child_performance = []
        for child in children:
            latest = reports.filter(student=child, has_missing_marks=False).order_by("-term__academic_year__start_date", "-term__number").first()
            child_performance.append({"name": child.full_name, "average": float(latest.average_score) if latest else 0})
        family_history = list(
            reports.filter(has_missing_marks=False)
            .values("term__academic_year__name", "term__number")
            .annotate(average=Avg("average_score"))
            .order_by("term__academic_year__start_date", "term__number")
        )[-7:]
        child_attendance = AttendanceRecord.objects.filter(student__in=children, session__term=term, is_deleted=False) if term else AttendanceRecord.objects.none()
        attendance_totals = {item["status"]: item["total"] for item in child_attendance.values("status").annotate(total=Count("id"))}
        attendance_states = [{"status": key, "total": attendance_totals[key]} for key in ("present", "absent", "late", "excused", "sick") if key in attendance_totals]
        status_labels = dict(AttendanceRecord.STATUS_CHOICES)
        dashboard_charts = {
            "family_history": {
                "type": "line",
                "labels": [f"{item['term__academic_year__name']} T{item['term__number']}" for item in family_history],
                "datasets": [{"label": "Family average", "data": [float(item["average"] or 0) for item in family_history], "color": "#10b981"}],
                "max": 100, "suffix": "%",
            },
            "child_performance": {
                "type": "bar",
                "labels": [item["name"] for item in child_performance],
                "datasets": [{"label": "Latest average", "data": [item["average"] for item in child_performance], "color": "#6366f1"}],
                "max": 100, "suffix": "%",
            },
            "family_attendance": {
                "type": "doughnut",
                "labels": [status_labels.get(item["status"], item["status"].title()) for item in attendance_states],
                "datasets": [{"label": "Attendance", "data": [item["total"] for item in attendance_states], "colors": ["#10b981", "#f43f5e", "#f59e0b", "#6366f1", "#06b6d4"]}],
            },
        }
        return {
            "dashboard_kind": "parent", "children": children, "parent_reports": reports[:6],
            "dashboard_charts": dashboard_charts,
            "stats": [
                {"label": "My learners", "value": children.count(), "tone": "emerald", "icon": "users", "detail": "Linked learner profiles"},
                {"label": "Published reports", "value": reports.count(), "tone": "indigo", "icon": "report", "detail": "Available to view"},
                {"label": "Term absences", "value": absent, "tone": "amber", "icon": "alert", "detail": str(term) if term else "No current term"},
                {"label": "Unread notices", "value": Notification.objects.filter(recipient=user, read_at__isnull=True, is_deleted=False).count(), "tone": "rose", "icon": "bell", "detail": "Messages requiring attention"},
            ],
        }


class SchoolModulesView(AcademicManagerRequiredMixin, FormView):
    template_name = "settings/modules.html"
    form_class = SchoolModulesForm
    success_url = "/settings/modules/"

    def get_school(self):
        return SchoolProfile.objects.filter(is_deleted=False).first()

    def get_initial(self):
        initial = super().get_initial()
        initial["enabled_modules"] = list(get_enabled_modules(self.get_school()))
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enabled = get_enabled_modules(self.get_school())
        context.update({
            "module_groups": self._module_groups(),
            "active_plan": get_plan_name(enabled),
            "enabled_count": len(enabled),
            "module_count": len(MODULES),
        })
        return context

    def form_valid(self, form):
        school = self.get_school()
        if not school:
            form.add_error(None, "Create the school profile before configuring modules.")
            return self.form_invalid(form)
        selected = set(form.cleaned_data["enabled_modules"])
        preset = self.request.POST.get("preset")
        if preset in PRESETS:
            selected = set(PRESETS[preset])
        with transaction.atomic():
            for code in MODULES:
                SchoolModule.objects.update_or_create(
                    school=school,
                    code=code,
                    defaults={"is_enabled": code in selected, "enabled_by": self.request.user, "is_deleted": False},
                )
        clear_module_cache(school.pk)
        messages.success(self.request, f"{get_plan_name(selected)} configuration saved. Changes are active immediately.")
        return super().form_valid(form)

    @staticmethod
    def _module_groups():
        groups = {}
        for code, item in MODULES.items():
            groups.setdefault(item["group"], []).append({"code": code, **item})
        return groups


class GlobalSearchView(LoginRequiredMixin, TemplateView):
    template_name = "search/results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        groups = []
        if len(query) < 2:
            context.update({"query": query, "result_groups": groups})
            return context
        school = SchoolProfile.objects.filter(is_deleted=False).first()
        enabled = get_enabled_modules(school)
        user = self.request.user

        if "students" in enabled:
            from students.views import scoped_students

            items = scoped_students(user).filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query)
                | Q(other_names__icontains=query) | Q(student_number__icontains=query)
                | Q(admission_number__icontains=query)
            )[:8]
            groups.append({"label": "Students", "items": [{"title": item.full_name, "meta": f"{item.student_number} · {item.stream or 'Not placed'}", "url": reverse("students:detail", args=[item.pk])} for item in items]})

        if "academics" in enabled and (user.is_superuser or user.role in {"super_admin", "headteacher", "director_of_studies"}):
            from academics.models import Subject

            items = Subject.objects.filter(Q(name__icontains=query) | Q(code__icontains=query), is_deleted=False)[:8]
            groups.append({"label": "Subjects", "items": [{"title": item.name, "meta": f"{item.code} · {item.get_curriculum_level_display()}", "url": reverse("academics:subjects-edit", args=[item.pk])} for item in items]})

        if "staff" in enabled and (user.is_superuser or user.role in {"super_admin", "headteacher", "director_of_studies"}):
            from staff.models import StaffMember

            items = StaffMember.objects.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(staff_number__icontains=query) | Q(job_title__icontains=query), is_deleted=False)[:8]
            groups.append({"label": "Staff", "items": [{"title": item.full_name, "meta": f"{item.staff_number} · {item.job_title}", "url": reverse("staff:detail", args=[item.pk])} for item in items]})

        if "fees" in enabled:
            from fees.views import scoped_invoices

            items = scoped_invoices(user).filter(Q(invoice_number__icontains=query) | Q(student__first_name__icontains=query) | Q(student__last_name__icontains=query) | Q(student__student_number__icontains=query))[:8]
            groups.append({"label": "Fee invoices", "items": [{"title": item.invoice_number, "meta": f"{item.student.full_name} · UGX {item.balance:,.0f} balance", "url": reverse("fees:invoice-detail", args=[item.pk])} for item in items]})

        if "finance" in enabled and (user.is_superuser or user.role in {"super_admin", "headteacher", "director_of_studies", "bursar"}):
            from finance.models import Expenditure

            items = Expenditure.objects.filter(Q(reference__icontains=query) | Q(description__icontains=query) | Q(vendor__name__icontains=query), is_deleted=False)[:8]
            groups.append({"label": "Expenditure", "items": [{"title": item.reference, "meta": f"{item.description[:70]} · UGX {item.gross_amount:,.0f}", "url": reverse("finance:expenditure-detail", args=[item.pk])} for item in items]})

        context.update({"query": query, "result_groups": [group for group in groups if group["items"]]})
        return context


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "time": timezone.now().isoformat()})
