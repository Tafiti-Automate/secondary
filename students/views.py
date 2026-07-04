import csv
from datetime import date
from io import StringIO

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from academics.models import AcademicYear, Stream
from reports.models import ReportCard
from config.crud import AuditedFormMixin, SoftDeleteView
from config.mixins import ACADEMIC_STAFF, AcademicManagerRequiredMixin, AcademicStaffRequiredMixin
from .forms import BulkPromotionForm, EnrollmentForm, GuardianForm, PromotionForm, StudentAccommodationForm, StudentAchievementForm, StudentForm, StudentGuardianForm, StudentImportForm, StudentInterestForm, StudentMovementForm, SubjectRegistrationForm
from .models import Enrollment, Guardian, Student, StudentAccommodation, StudentAchievement, StudentGuardian, StudentInterest, StudentMovement, StudentPromotion, StudentSubjectRegistration
from .timeline import learner_timeline


def scoped_students(user):
    qs = Student.objects.filter(is_deleted=False).select_related("stream__class_level", "subject_combination", "user")
    if user.is_superuser or user.role in {"super_admin", "headteacher", "director_of_studies"}:
        return qs
    if user.role == "teacher":
        return qs.filter(Q(stream__class_teacher=user) | Q(stream__subject_allocations__teacher=user, stream__subject_allocations__is_deleted=False)).distinct()
    if user.role == "student":
        return qs.filter(user=user)
    if user.role == "parent":
        return qs.filter(Q(parent=user) | Q(guardian_links__guardian__user=user)).distinct()
    return qs.none()


class StudentListView(AcademicStaffRequiredMixin, ListView):
    model = Student
    template_name = "students/student_list.html"
    context_object_name = "students"
    paginate_by = 24

    def get_queryset(self):
        qs = scoped_students(self.request.user)
        query = self.request.GET.get("q", "").strip()
        stream = self.request.GET.get("stream", "")
        status = self.request.GET.get("status", "")
        if query:
            qs = qs.filter(Q(student_number__icontains=query) | Q(admission_number__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(other_names__icontains=query))
        if stream:
            qs = qs.filter(stream_id=stream)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"streams": Stream.objects.filter(is_deleted=False), "statuses": Student.STATUS_CHOICES})
        return context


class StudentDetailView(LoginRequiredMixin, DetailView):
    model = Student
    template_name = "students/student_detail.html"
    context_object_name = "student"

    def get_queryset(self):
        return scoped_students(self.request.user).prefetch_related(
            "guardian_links__guardian", "enrollments", "promotions", "assessment_results",
            "exam_results", "accommodations", "interests", "achievements",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["can_view_private_profile"] = bool(
            user.is_superuser
            or user.role in {"super_admin", "headteacher", "director_of_studies", "parent", "student"}
        )
        events = learner_timeline(self.object)
        if not context["can_view_private_profile"]:
            events = [event for event in events if not (
                event.category == "support" and getattr(event.source, "confidential", False)
            )]
        context["recent_timeline"] = events[:6]
        return context


class StudentTimelineView(LoginRequiredMixin, DetailView):
    model = Student
    template_name = "students/timeline.html"
    context_object_name = "student"

    def get_queryset(self):
        return scoped_students(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_view_private = bool(
            self.request.user.is_superuser
            or self.request.user.role in {"super_admin", "headteacher", "director_of_studies", "parent", "student"}
        )
        events = learner_timeline(self.object)
        if not can_view_private:
            events = [event for event in events if not (
                event.category == "support" and getattr(event.source, "confidential", False)
            )]
        context["timeline"] = events
        context["can_view_private_profile"] = can_view_private
        return context


class StudentRelatedCreateMixin:
    student = None

    def dispatch(self, request, *args, **kwargs):
        self.student = get_object_or_404(scoped_students(request.user), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.student = self.student
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("students:timeline", args=[self.student.pk])


class StudentAccommodationCreateView(AcademicManagerRequiredMixin, StudentRelatedCreateMixin, AuditedFormMixin, CreateView):
    model = StudentAccommodation
    form_class = StudentAccommodationForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Add learner accommodation", "eyebrow": "Learning support", "submit_label": "Save accommodation"}


class StudentInterestCreateView(AcademicStaffRequiredMixin, StudentRelatedCreateMixin, AuditedFormMixin, CreateView):
    model = StudentInterest
    form_class = StudentInterestForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Record learner interest", "eyebrow": "Whole learner profile", "submit_label": "Save interest"}


class StudentAchievementCreateView(AcademicStaffRequiredMixin, StudentRelatedCreateMixin, AuditedFormMixin, CreateView):
    model = StudentAchievement
    form_class = StudentAchievementForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Record learner achievement", "eyebrow": "Whole learner profile", "submit_label": "Save achievement"}

    def form_valid(self, form):
        form.instance.student = self.student
        if self.request.user.is_superuser or self.request.user.role in {"super_admin", "headteacher", "director_of_studies"}:
            form.instance.verified_by = self.request.user
        return super(StudentRelatedCreateMixin, self).form_valid(form)


class StudentAcademicHistoryView(LoginRequiredMixin, DetailView):
    model = Student
    template_name = "students/academic_history.html"
    context_object_name = "student"

    def get_queryset(self):
        return scoped_students(self.request.user).prefetch_related("enrollments__subject_registrations__subject", "promotions", "movements")


class StudentCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = Student
    form_class = StudentForm
    template_name = "students/student_form.html"
    audit_action = "create"

    def get_success_url(self):
        return reverse("students:detail", args=[self.object.pk])

    def form_valid(self, form):
        response = super().form_valid(form)
        year = AcademicYear.objects.filter(is_current=True, is_deleted=False).first()
        if year and self.object.stream and self.object.stream.academic_year_id == year.pk:
            Enrollment.objects.get_or_create(student=self.object, academic_year=year, defaults={"stream": self.object.stream, "subject_combination": self.object.subject_combination})
        return response


class StudentUpdateView(AcademicManagerRequiredMixin, AuditedFormMixin, UpdateView):
    model = Student
    form_class = StudentForm
    template_name = "students/student_form.html"
    audit_action = "update"

    def get_success_url(self):
        return reverse("students:detail", args=[self.object.pk])


class StudentDeleteView(AcademicManagerRequiredMixin, SoftDeleteView):
    model = Student
    success_url_name = "students:list"


class GuardianListView(AcademicManagerRequiredMixin, ListView):
    model = Guardian
    queryset = Guardian.objects.filter(is_deleted=False)
    template_name = "students/guardian_list.html"
    context_object_name = "guardians"
    paginate_by = 20


class GuardianCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = Guardian
    form_class = GuardianForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("students:guardians")
    audit_action = "create"
    extra_context = {"page_title": "Add parent or guardian", "eyebrow": "Student welfare", "submit_label": "Save guardian"}


class GuardianUpdateView(AcademicManagerRequiredMixin, AuditedFormMixin, UpdateView):
    model = Guardian
    form_class = GuardianForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("students:guardians")
    audit_action = "update"
    extra_context = {"page_title": "Edit guardian", "eyebrow": "Student welfare", "submit_label": "Save changes"}


class StudentGuardianCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = StudentGuardian
    form_class = StudentGuardianForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Link guardian to student", "eyebrow": "Student welfare", "submit_label": "Link guardian"}

    def get_initial(self):
        initial = super().get_initial()
        initial["student"] = self.request.GET.get("student")
        return initial

    def get_success_url(self):
        return reverse("students:detail", args=[self.object.student_id])


class EnrollmentCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = Enrollment
    form_class = EnrollmentForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Create enrolment", "eyebrow": "Academic placement", "submit_label": "Enrol student"}

    def get_success_url(self):
        return reverse("students:detail", args=[self.object.student_id])

    def get_initial(self):
        initial = super().get_initial()
        initial["student"] = self.request.GET.get("student")
        return initial


class PromotionListView(AcademicManagerRequiredMixin, ListView):
    queryset = StudentPromotion.objects.filter(is_deleted=False).select_related("student", "from_stream", "to_stream", "approved_by")
    template_name = "students/promotion_list.html"
    context_object_name = "promotions"
    paginate_by = 20


class PromotionCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = StudentPromotion
    form_class = PromotionForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("students:promotions")
    audit_action = "create"
    extra_context = {"page_title": "Record promotion decision", "eyebrow": "Academic progression", "submit_label": "Save decision"}

    def form_valid(self, form):
        form.instance.approved_by = self.request.user
        return super().form_valid(form)


class BulkPromotionView(AcademicManagerRequiredMixin, View):
    template_name = "students/bulk_promotion.html"

    def get(self, request):
        return render(request, self.template_name, {"form": BulkPromotionForm()})

    @transaction.atomic
    def post(self, request):
        form = BulkPromotionForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        term = form.cleaned_data["term"]
        from_stream = form.cleaned_data["from_stream"]
        to_stream = form.cleaned_data["to_stream"]
        decision = form.cleaned_data["decision"]
        students = Student.objects.filter(stream=from_stream, is_active=True, is_deleted=False)
        if form.cleaned_data["apply_to"] == "eligible":
            blocked_ids = ReportCard.objects.filter(term=term, stream=from_stream, has_missing_marks=True, is_deleted=False).values_list("student_id", flat=True)
            students = students.exclude(pk__in=blocked_ids)
        created = 0
        for student in students.select_related("stream", "subject_combination"):
            promotion, _ = StudentPromotion.objects.update_or_create(
                student=student, term=term, is_deleted=False,
                defaults={
                    "from_stream": from_stream, "to_stream": to_stream if decision in {"promoted", "repeated"} else None,
                    "academic_year": term.academic_year.name, "decision": decision,
                    "remarks": form.cleaned_data["remarks"], "approved_by": request.user,
                },
            )
            ReportCard.objects.filter(student=student, term=term, is_deleted=False).update(promotion_decision=decision)
            if decision in {"promoted", "repeated"}:
                Enrollment.objects.update_or_create(
                    student=student, academic_year=to_stream.academic_year,
                    defaults={"stream": to_stream, "subject_combination": student.subject_combination, "status": decision},
                )
            elif decision == "completed":
                Enrollment.objects.update_or_create(
                    student=student, academic_year=term.academic_year,
                    defaults={"stream": from_stream, "subject_combination": student.subject_combination, "status": "completed"},
                )
            created += 1
        messages.success(request, f"Processed {created} learner progression record(s). Current class placement was updated where applicable.")
        return redirect("students:promotions")


class SubjectRegistrationCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = StudentSubjectRegistration
    form_class = SubjectRegistrationForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Register learner subject", "eyebrow": "Subject registration history", "submit_label": "Register subject"}

    def get_initial(self):
        initial = super().get_initial()
        initial["enrollment"] = self.request.GET.get("enrollment")
        return initial

    def get_success_url(self):
        return reverse("students:detail", args=[self.object.enrollment.student_id])


class StudentMovementListView(AcademicManagerRequiredMixin, ListView):
    queryset = StudentMovement.objects.filter(is_deleted=False).select_related("student", "authorised_by")
    template_name = "students/movement_list.html"
    context_object_name = "movements"
    paginate_by = 25


class StudentMovementCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = StudentMovement
    form_class = StudentMovementForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("students:movements")
    audit_action = "create"
    extra_context = {"page_title": "Record student movement", "eyebrow": "Transfers, withdrawal and completion", "submit_label": "Save movement"}

    def form_valid(self, form):
        form.instance.authorised_by = self.request.user
        return super().form_valid(form)


class StudentImportView(AcademicManagerRequiredMixin, View):
    template_name = "students/import.html"
    required_headers = {"first_name", "last_name", "gender", "date_of_birth"}

    def get(self, request):
        return render(request, self.template_name, {"form": StudentImportForm()})

    def post(self, request):
        form = StudentImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        try:
            content = form.cleaned_data["csv_file"].read().decode("utf-8-sig")
            reader = csv.DictReader(StringIO(content))
            if not reader.fieldnames or not self.required_headers.issubset(set(reader.fieldnames)):
                raise ValueError("CSV must include first_name, last_name, gender and date_of_birth columns.")
            created = []
            with transaction.atomic():
                for row_number, row in enumerate(reader, 2):
                    gender = row["gender"].strip().lower()
                    if gender not in {"male", "female"}:
                        raise ValueError(f"Row {row_number}: gender must be male or female.")
                    try:
                        birth_date = date.fromisoformat(row["date_of_birth"].strip())
                    except ValueError:
                        raise ValueError(f"Row {row_number}: date_of_birth must use YYYY-MM-DD.")
                    student = Student.objects.create(
                        student_number=row.get("student_number", "").strip() or None,
                        admission_number=row.get("admission_number", "").strip(), first_name=row["first_name"].strip(),
                        last_name=row["last_name"].strip(), other_names=row.get("other_names", "").strip(), gender=gender,
                        date_of_birth=birth_date, stream=form.cleaned_data["stream"], date_admitted=date.today(),
                        previous_school=row.get("previous_school", "").strip(), district=row.get("district", "").strip(),
                    )
                    Enrollment.objects.create(student=student, academic_year=form.cleaned_data["academic_year"], stream=form.cleaned_data["stream"])
                    parent_phone = row.get("guardian_phone", "").strip()
                    if parent_phone:
                        guardian, _ = Guardian.objects.get_or_create(phone=parent_phone, defaults={"first_name": row.get("guardian_first_name", "Guardian").strip() or "Guardian", "last_name": row.get("guardian_last_name", student.last_name).strip() or student.last_name})
                        relationship = row.get("guardian_relationship", "guardian").strip().lower() or "guardian"
                        if relationship not in dict(StudentGuardian._meta.get_field("relationship").choices):
                            relationship = "guardian"
                        StudentGuardian.objects.create(student=student, guardian=guardian, relationship=relationship, is_primary=True)
                    created.append(student)
            messages.success(request, f"Imported {len(created)} learner record(s) successfully.")
            return redirect("students:list")
        except Exception as exc:
            form.add_error("csv_file", str(exc))
            return render(request, self.template_name, {"form": form})


class StudentImportTemplateView(AcademicManagerRequiredMixin, View):
    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="student-import-template.csv"'
        writer = csv.writer(response)
        writer.writerow(["student_number", "admission_number", "first_name", "last_name", "other_names", "gender", "date_of_birth", "previous_school", "district", "guardian_first_name", "guardian_last_name", "guardian_phone", "guardian_relationship"])
        writer.writerow(["", "", "Amina", "Nabirye", "", "female", "2012-05-04", "Previous Primary School", "Kampala", "Peter", "Kato", "+256700000000", "father"])
        return response
