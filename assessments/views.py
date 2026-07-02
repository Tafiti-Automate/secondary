import csv
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from config.crud import AuditedFormMixin, SoftDeleteView
from config.audit import record_audit
from config.mixins import ACADEMIC_MANAGERS, AcademicManagerRequiredMixin, AcademicStaffRequiredMixin
from config.tables import ModelTableView
from students.models import Student
from academics.models import ClassLevel, Subject, SubjectAllocation
from .forms import ActivityOfIntegrationForm, AssessmentEvidenceForm, AssessmentForm, AssessmentPolicyForm, AssessmentTypeForm, CompetencyForm, CompetencyIndicatorForm, CompetencyLevelForm, CurriculumFrameworkForm, CurriculumImportForm, CurriculumTopicForm, CurriculumValueForm, LearningOutcomeForm, LessonPlanForm, RubricCriterionForm, RubricForm, RubricLevelForm, SchemeOfWorkForm, SchemeWeekForm, SubmissionForm
from .models import ActivityOfIntegration, Assessment, AssessmentEvidence, AssessmentPolicy, AssessmentResult, AssessmentSubmission, AssessmentType, Competency, CompetencyAssessment, CompetencyIndicator, CompetencyLevel, CurriculumFramework, CurriculumLearningArea, CurriculumTopic, CurriculumValue, LearningOutcome, LessonPlan, Rubric, RubricCriterion, RubricLevel, RubricRating, SchemeOfWork, SchemeWeek, Skill


def teacher_assessments(user):
    qs = Assessment.objects.filter(is_deleted=False).select_related("assessment_type", "subject", "stream", "term")
    if user.is_superuser or user.role in ACADEMIC_MANAGERS:
        return qs
    if user.role == "teacher":
        allocation = SubjectAllocation.objects.filter(teacher=user, subject_id=OuterRef("subject_id"), stream_id=OuterRef("stream_id"), term_id=OuterRef("term_id"), is_deleted=False, is_active=True)
        return qs.annotate(is_allocated=Exists(allocation)).filter(is_allocated=True)
    return qs.none()


def planning_allocations(user):
    qs = SubjectAllocation.objects.filter(is_deleted=False, is_active=True).select_related("teacher", "subject", "stream", "term")
    if user.is_superuser or user.role in ACADEMIC_MANAGERS:
        return qs
    return qs.filter(Q(teacher=user) | Q(subject__department__head=user)).distinct() if user.role == "teacher" else qs.none()


class AssessmentListView(AcademicStaffRequiredMixin, ListView):
    template_name = "assessments/assessment_list.html"
    context_object_name = "assessments"
    paginate_by = 20

    def get_queryset(self):
        qs = teacher_assessments(self.request.user)
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs


class AssessmentCreateView(AcademicStaffRequiredMixin, AuditedFormMixin, CreateView):
    model = Assessment
    form_class = AssessmentForm
    template_name = "assessments/assessment_form.html"
    audit_action = "create"
    success_url = reverse_lazy("assessments:list")
    extra_context = {"page_title": "Create assessment", "eyebrow": "Continuous assessment", "submit_label": "Create assessment"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.role == "teacher" and not self.request.user.is_superuser:
            allocations = SubjectAllocation.objects.filter(teacher=self.request.user, is_deleted=False, is_active=True)
            form.fields["subject"].queryset = form.fields["subject"].queryset.filter(allocations__in=allocations).distinct()
            form.fields["stream"].queryset = form.fields["stream"].queryset.filter(subject_allocations__in=allocations).distinct()
            form.fields["term"].queryset = form.fields["term"].queryset.filter(subject_allocations__in=allocations).distinct()
            form.fields["status"].choices = [("draft", "Draft"), ("published", "Published"), ("closed", "Closed")]
        return form


class AssessmentUpdateView(AcademicStaffRequiredMixin, AuditedFormMixin, UpdateView):
    model = Assessment
    form_class = AssessmentForm
    template_name = "assessments/assessment_form.html"
    audit_action = "update"
    success_url = reverse_lazy("assessments:list")
    extra_context = {"page_title": "Edit assessment", "eyebrow": "Continuous assessment", "submit_label": "Save changes"}

    def get_queryset(self):
        return teacher_assessments(self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.role == "teacher" and not self.request.user.is_superuser:
            form.fields["status"].choices = [("draft", "Draft"), ("published", "Published"), ("closed", "Closed")]
        return form

    def form_valid(self, form):
        if form.instance.is_workflow_locked:
            form.add_error(None, "DOS-approved assessments are read-only. Reopen the workflow before editing.")
            return self.form_invalid(form)
        return super().form_valid(form)


class AssessmentDetailView(AcademicStaffRequiredMixin, DetailView):
    template_name = "assessments/assessment_detail.html"
    context_object_name = "assessment"

    def get_queryset(self):
        return teacher_assessments(self.request.user).prefetch_related("results__student", "submissions__student", "learning_outcomes", "evidence_records__student", "reviews__reviewer")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object.subject.department
        context["is_hod"] = bool(
            self.request.user.is_superuser
            or self.request.user.role in ACADEMIC_MANAGERS
            or (department and department.head_id == self.request.user.pk)
        )
        return context


class AssessmentWorkflowView(AcademicStaffRequiredMixin, View):
    def post(self, request, pk):
        assessment = get_object_or_404(teacher_assessments(request.user), pk=pk)
        operation = request.POST.get("operation", "")
        try:
            assessment.transition(operation, request.user, request.POST.get("comment", "").strip())
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            record_audit(request, "assessment_workflow", assessment, f"Assessment workflow: {operation}", {"operation": operation})
            messages.success(request, f"Assessment workflow updated to {assessment.get_workflow_status_display()}.")
        return redirect("assessments:detail", pk=pk)


class AssessmentDeleteView(AcademicManagerRequiredMixin, SoftDeleteView):
    model = Assessment
    success_url_name = "assessments:list"


class MarkEntryView(AcademicStaffRequiredMixin, View):
    template_name = "assessments/mark_entry.html"

    def get_assessment(self, request, pk):
        return get_object_or_404(teacher_assessments(request.user), pk=pk)

    def get(self, request, pk):
        assessment = self.get_assessment(request, pk)
        students = Student.objects.filter(stream=assessment.stream, is_deleted=False, is_active=True).order_by("first_name", "last_name")
        results = {item.student_id: item for item in AssessmentResult.objects.filter(assessment=assessment, is_deleted=False)}
        rows = [{"student": student, "result": results.get(student.pk)} for student in students]
        from django.shortcuts import render
        return render(request, self.template_name, {"assessment": assessment, "rows": rows})

    @transaction.atomic
    def post(self, request, pk):
        assessment = self.get_assessment(request, pk)
        if assessment.is_workflow_locked:
            messages.error(request, "DOS-approved assessment results are read-only.")
            return redirect("assessments:detail", pk=pk)
        if assessment.status in {"closed", "moderated"} and request.user.role not in ACADEMIC_MANAGERS:
            messages.error(request, "This assessment is closed for mark entry.")
            return redirect("assessments:detail", pk=pk)
        students = Student.objects.filter(stream=assessment.stream, is_deleted=False, is_active=True)
        saved, errors = 0, []
        for student in students:
            raw = request.POST.get(f"score_{student.pk}", "").strip()
            if not raw:
                continue
            try:
                score = Decimal(raw)
                result, _ = AssessmentResult.objects.get_or_create(assessment=assessment, student=student, defaults={"score": score, "marked_by": request.user})
                result.score = score
                result.feedback = request.POST.get(f"feedback_{student.pk}", "").strip()
                result.marked_by = request.user
                result.save()
                saved += 1
            except (InvalidOperation, ValidationError) as exc:
                errors.append(f"{student.full_name}: {exc}")
        if errors:
            messages.error(request, "Some marks were not saved: " + "; ".join(errors[:3]))
        if saved:
            record_audit(request, "mark_entry", assessment, f"Entered {saved} continuous-assessment mark(s)", {"saved": saved})
            messages.success(request, f"Saved {saved} student mark(s).")
        return redirect("assessments:marks", pk=pk)


class CompetencyEntryView(AcademicStaffRequiredMixin, View):
    template_name = "assessments/competency_entry.html"

    def get_assessment(self, request, pk):
        return get_object_or_404(teacher_assessments(request.user), pk=pk)

    def get(self, request, pk):
        from django.shortcuts import render
        assessment = self.get_assessment(request, pk)
        students = Student.objects.filter(stream=assessment.stream, is_deleted=False, is_active=True)
        competencies = Competency.objects.filter(is_deleted=False, is_active=True)
        levels = CompetencyLevel.objects.filter(is_deleted=False)
        existing = {(x.student_id, x.competency_id): x for x in CompetencyAssessment.objects.filter(assessment=assessment, is_deleted=False)}
        rows = [{"student": student, "ratings": [{"competency": competency, "rating": existing.get((student.pk, competency.pk))} for competency in competencies]} for student in students]
        return render(request, self.template_name, {"assessment": assessment, "rows": rows, "levels": levels})

    @transaction.atomic
    def post(self, request, pk):
        assessment = self.get_assessment(request, pk)
        if assessment.is_workflow_locked:
            messages.error(request, "DOS-approved competency ratings are read-only.")
            return redirect("assessments:detail", pk=pk)
        students = Student.objects.filter(stream=assessment.stream, is_deleted=False, is_active=True)
        competencies = Competency.objects.filter(is_deleted=False, is_active=True)
        levels = {str(x.pk): x for x in CompetencyLevel.objects.filter(is_deleted=False)}
        saved = 0
        for student in students:
            for competency in competencies:
                level = levels.get(request.POST.get(f"level_{student.pk}_{competency.pk}"))
                if level:
                    CompetencyAssessment.objects.update_or_create(assessment=assessment, student=student, competency=competency, defaults={"scale_level": level, "assessed_by": request.user, "is_deleted": False})
                    saved += 1
        messages.success(request, f"Saved {saved} competency rating(s).")
        record_audit(request, "competency_entry", assessment, f"Entered {saved} competency rating(s)", {"saved": saved})
        return redirect("assessments:competencies", pk=pk)


class CurriculumOverviewView(AcademicStaffRequiredMixin, TemplateView):
    template_name = "assessments/curriculum_overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "frameworks": CurriculumFramework.objects.filter(is_deleted=False, is_active=True),
            "learning_area_count": CurriculumLearningArea.objects.filter(is_deleted=False).count(),
            "topic_count": CurriculumTopic.objects.filter(is_deleted=False).count(),
            "outcome_count": LearningOutcome.objects.filter(is_deleted=False).count(),
            "activity_count": ActivityOfIntegration.objects.filter(is_deleted=False).count(),
            "rubric_count": Rubric.objects.filter(is_deleted=False).count(),
            "policies": AssessmentPolicy.objects.filter(is_deleted=False, is_active=True).select_related("academic_year", "class_level"),
            "skills": Competency.objects.filter(is_deleted=False, is_active=True, assessment_mode="integrated"),
            "practical_skills": Skill.objects.filter(is_deleted=False, is_active=True),
            "values": CurriculumValue.objects.filter(is_deleted=False),
        })
        return context


class ActivityDetailView(AcademicStaffRequiredMixin, DetailView):
    model = ActivityOfIntegration
    template_name = "assessments/activity_detail.html"
    context_object_name = "activity"

    def get_queryset(self):
        return ActivityOfIntegration.objects.filter(is_deleted=False).select_related("topic__subject", "topic__class_level").prefetch_related("topic__learning_outcomes__generic_skills")


class RubricEntryView(AcademicStaffRequiredMixin, View):
    template_name = "assessments/rubric_entry.html"

    def assessment(self, request, pk):
        return get_object_or_404(teacher_assessments(request.user).select_related("rubric"), pk=pk, rubric__isnull=False)

    def get(self, request, pk):
        assessment = self.assessment(request, pk)
        students = Student.objects.filter(stream=assessment.stream, is_deleted=False, is_active=True)
        criteria = list(assessment.rubric.criteria.filter(is_deleted=False).prefetch_related("levels"))
        results = {item.student_id: item for item in AssessmentResult.objects.filter(assessment=assessment, is_deleted=False)}
        ratings = {(item.result.student_id, item.criterion_id): item for item in RubricRating.objects.filter(result__assessment=assessment, is_deleted=False).select_related("level")}
        rows = [{"student": student, "result": results.get(student.pk), "criteria": [{"criterion": criterion, "rating": ratings.get((student.pk, criterion.pk))} for criterion in criteria]} for student in students]
        return render(request, self.template_name, {"assessment": assessment, "rows": rows, "criteria": criteria})

    @transaction.atomic
    def post(self, request, pk):
        assessment = self.assessment(request, pk)
        if assessment.is_workflow_locked:
            messages.error(request, "DOS-approved rubric evidence is read-only.")
            return redirect("assessments:detail", pk=pk)
        criteria = list(assessment.rubric.criteria.filter(is_deleted=False).prefetch_related("levels"))
        saved = 0
        for student in Student.objects.filter(stream=assessment.stream, is_deleted=False, is_active=True):
            selected = []
            total = Decimal("0")
            for criterion in criteria:
                level_id = request.POST.get(f"level_{student.pk}_{criterion.pk}")
                level = criterion.levels.filter(pk=level_id, is_deleted=False).first() if level_id else None
                if level:
                    selected.append((criterion, level))
                    total += level.score
            existing_result = AssessmentResult.objects.filter(assessment=assessment, student=student, is_deleted=False).first()
            if selected:
                result = existing_result or AssessmentResult(assessment=assessment, student=student, score=total, marked_by=request.user)
                result.score, result.marked_by = total, request.user
                result.is_deleted = False
                result.deleted_at = None
                result.save()
                RubricRating.objects.filter(result=result, is_deleted=False).update(is_deleted=True)
                for criterion, level in selected:
                    RubricRating.objects.update_or_create(result=result, criterion=criterion, defaults={"level": level, "is_deleted": False})
                saved += 1
            elif existing_result:
                existing_result.soft_delete()
        record_audit(request, "rubric_entry", assessment, f"Saved rubric evidence for {saved} learner(s)", {"saved": saved})
        messages.success(request, f"Saved rubric ratings for {saved} learner(s).")
        return redirect("assessments:rubric-entry", pk=pk)


class EvidenceCreateView(AcademicStaffRequiredMixin, AuditedFormMixin, CreateView):
    model = AssessmentEvidence
    form_class = AssessmentEvidenceForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Capture assessment evidence", "eyebrow": "Observation · conversation · product", "submit_label": "Save evidence"}

    def get_initial(self):
        initial = super().get_initial()
        initial.update({"assessment": self.request.GET.get("assessment"), "student": self.request.GET.get("student")})
        return initial

    def form_valid(self, form):
        if form.instance.assessment.is_workflow_locked:
            form.add_error(None, "DOS-approved assessment evidence is read-only.")
            return self.form_invalid(form)
        form.instance.captured_by = self.request.user
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        allowed = teacher_assessments(self.request.user)
        form.fields["assessment"].queryset = allowed
        form.fields["student"].queryset = Student.objects.filter(stream_id__in=allowed.values_list("stream_id", flat=True), is_deleted=False, is_active=True).distinct()
        return form

    def get_success_url(self):
        return reverse("assessments:detail", args=[self.object.assessment_id])


class CurriculumImportView(AcademicManagerRequiredMixin, View):
    template_name = "assessments/curriculum_import.html"
    required = {"subject_code", "class_level", "term_number", "topic_title", "sequence", "learning_outcome"}

    def get(self, request):
        return render(request, self.template_name, {"form": CurriculumImportForm()})

    def post(self, request):
        form = CurriculumImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        try:
            reader = csv.DictReader(StringIO(form.cleaned_data["csv_file"].read().decode("utf-8-sig")))
            if not reader.fieldnames or not self.required.issubset(reader.fieldnames):
                raise ValueError("Template columns are missing. Download and use the current curriculum template.")
            topic_count, outcome_count = 0, 0
            with transaction.atomic():
                for row_number, row in enumerate(reader, 2):
                    subject = Subject.objects.filter(code__iexact=row["subject_code"].strip(), is_deleted=False).first()
                    class_level = ClassLevel.objects.filter(name__iexact=row["class_level"].strip(), is_deleted=False).first()
                    if not subject or not class_level:
                        raise ValueError(f"Row {row_number}: subject code or class level is not configured.")
                    try:
                        term_number, sequence = int(row["term_number"]), int(row["sequence"])
                    except ValueError:
                        raise ValueError(f"Row {row_number}: term_number and sequence must be numbers.")
                    learning_area = None
                    if row.get("learning_area", "").strip():
                        learning_area, _ = CurriculumLearningArea.objects.get_or_create(
                            framework=form.cleaned_data["framework"],
                            subject=subject,
                            name=row["learning_area"].strip(),
                            defaults={
                                "code": row.get("learning_area_code", "").strip(),
                                "sequence": int(row.get("learning_area_order", "1") or 1),
                            },
                        )
                    topic, created = CurriculumTopic.objects.get_or_create(framework=form.cleaned_data["framework"], subject=subject, class_level=class_level, term_number=term_number, sequence=sequence, defaults={"learning_area": learning_area, "code": row.get("topic_code", "").strip(), "title": row["topic_title"].strip(), "description": row.get("topic_description", "").strip(), "suggested_periods": int(row.get("suggested_periods", "1") or 1)})
                    topic_count += int(created)
                    outcome, created = LearningOutcome.objects.get_or_create(topic=topic, code=row.get("learning_outcome_code", "").strip(), statement=row["learning_outcome"].strip(), defaults={"assessment_criteria": row.get("assessment_criteria", "").strip(), "suggested_activities": row.get("suggested_activities", "").strip(), "required_evidence": row.get("required_evidence", "").strip(), "display_order": int(row.get("outcome_order", "1") or 1)})
                    outcome_count += int(created)
                    skill_names = [name.strip() for name in row.get("generic_skills", "").split("|") if name.strip()]
                    value_names = [name.strip() for name in row.get("values", "").split("|") if name.strip()]
                    if skill_names:
                        outcome.generic_skills.set(Competency.objects.filter(name__in=skill_names, is_active=True, is_deleted=False))
                    if value_names:
                        outcome.values.set(CurriculumValue.objects.filter(name__in=value_names, is_deleted=False))
            messages.success(request, f"Curriculum import complete: {topic_count} new topic(s), {outcome_count} new learning outcome(s).")
            return redirect("assessments:curriculum")
        except Exception as exc:
            form.add_error("csv_file", str(exc))
            return render(request, self.template_name, {"form": form})


class CurriculumImportTemplateView(AcademicManagerRequiredMixin, View):
    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="curriculum-import-template.csv"'
        writer = csv.writer(response)
        writer.writerow(["subject_code", "class_level", "term_number", "learning_area_code", "learning_area", "learning_area_order", "topic_code", "topic_title", "topic_description", "sequence", "suggested_periods", "learning_outcome_code", "learning_outcome", "assessment_criteria", "suggested_activities", "required_evidence", "outcome_order", "generic_skills", "values"])
        writer.writerow(["ENG", "S1", "1", "S1-ENG-LA1", "Communication", "1", "S1-ENG-T1-01", "Communication in context", "", "1", "10", "S1.ENG.1.1", "The learner communicates clearly for a defined audience.", "Uses audience-appropriate language", "Role play and guided discussion", "Oral presentation and observation notes", "1", "Communication|Critical Thinking and Problem Solving", "Respect for Humanity and Environment|Integrity"])
        return response


class TeachingPlanOverviewView(AcademicStaffRequiredMixin, TemplateView):
    template_name = "assessments/teaching_plans.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        allocations = planning_allocations(self.request.user)
        context.update({
            "schemes": SchemeOfWork.objects.filter(allocation__in=allocations, is_deleted=False).select_related("allocation__subject", "allocation__stream", "allocation__term", "prepared_by", "reviewed_by"),
            "lessons": LessonPlan.objects.filter(allocation__in=allocations, is_deleted=False).select_related("allocation__subject", "allocation__stream", "topic", "prepared_by")[:20],
            "allocation_count": allocations.count(),
        })
        return context


class SchemeCreateView(AcademicStaffRequiredMixin, CreateView):
    model = SchemeOfWork
    form_class = SchemeOfWorkForm
    template_name = "shared/form.html"
    extra_context = {"page_title": "Create term scheme of work", "eyebrow": "Teacher planning", "submit_label": "Save scheme"}

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        allocations = planning_allocations(self.request.user)
        if self.request.user.role == "teacher" and not self.request.user.is_superuser:
            allocations = allocations.filter(teacher=self.request.user)
        form.fields["allocation"].queryset = allocations
        if self.request.user.role == "teacher" and not self.request.user.is_superuser:
            form.fields["status"].choices = [("draft", "Draft"), ("submitted", "Submit to HOD")]
        return form

    def form_valid(self, form):
        form.instance.prepared_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("assessments:scheme-detail", args=[self.object.pk])


class SchemeDetailView(AcademicStaffRequiredMixin, DetailView):
    model = SchemeOfWork
    template_name = "assessments/scheme_detail.html"
    context_object_name = "scheme"

    def get_queryset(self):
        return SchemeOfWork.objects.filter(allocation__in=planning_allocations(self.request.user), is_deleted=False).select_related("allocation__subject", "allocation__stream", "allocation__term", "allocation__subject__department", "reviewed_by").prefetch_related("weekly_plans__topic", "weekly_plans__learning_outcomes", "weekly_plans__competencies", "weekly_plans__lesson_plans")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object.allocation.subject.department
        context["can_review"] = bool(self.request.user.is_superuser or self.request.user.role in ACADEMIC_MANAGERS or (department and department.head_id == self.request.user.pk))
        context["can_submit"] = self.request.user.pk == self.object.allocation.teacher_id
        return context


class SchemeWeekCreateView(AcademicStaffRequiredMixin, CreateView):
    model = SchemeWeek
    form_class = SchemeWeekForm
    template_name = "shared/form.html"
    extra_context = {"page_title": "Add weekly scheme row", "eyebrow": "Scheme of work", "submit_label": "Save weekly plan"}

    def dispatch(self, request, *args, **kwargs):
        self.scheme = get_object_or_404(SchemeOfWork.objects.filter(allocation__in=planning_allocations(request.user), is_deleted=False), pk=kwargs["pk"])
        if request.user.role == "teacher" and self.scheme.allocation.teacher_id != request.user.pk:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        allocation = self.scheme.allocation
        form.fields["topic"].queryset = CurriculumTopic.objects.filter(subject=allocation.subject, class_level=allocation.stream.class_level, term_number=allocation.term.number, is_deleted=False)
        form.fields["learning_outcomes"].queryset = LearningOutcome.objects.filter(topic__in=form.fields["topic"].queryset, is_deleted=False)
        form.fields["competencies"].queryset = Competency.objects.filter(is_active=True, is_deleted=False)
        return form

    def form_valid(self, form):
        form.instance.scheme = self.scheme
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("assessments:scheme-detail", args=[self.scheme.pk])


class LessonPlanCreateView(AcademicStaffRequiredMixin, CreateView):
    model = LessonPlan
    form_class = LessonPlanForm
    template_name = "shared/form.html"
    extra_context = {"page_title": "Create lesson plan", "eyebrow": "Teacher planning", "submit_label": "Save lesson plan"}

    def get_initial(self):
        initial = super().get_initial()
        initial.update({"allocation": self.request.GET.get("allocation"), "scheme_week": self.request.GET.get("scheme_week")})
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        allocations = planning_allocations(self.request.user)
        if self.request.user.role == "teacher" and not self.request.user.is_superuser:
            allocations = allocations.filter(teacher=self.request.user)
        form.fields["allocation"].queryset = allocations
        form.fields["scheme_week"].queryset = SchemeWeek.objects.filter(scheme__allocation__in=allocations, is_deleted=False)
        form.fields["topic"].queryset = CurriculumTopic.objects.filter(subject__allocations__in=allocations, is_deleted=False).distinct()
        form.fields["learning_outcomes"].queryset = LearningOutcome.objects.filter(topic__subject__allocations__in=allocations, is_deleted=False).distinct()
        form.fields["competencies"].queryset = Competency.objects.filter(is_active=True, is_deleted=False)
        if self.request.user.role == "teacher" and not self.request.user.is_superuser:
            form.fields["status"].choices = [("draft", "Draft"), ("submitted", "Submit for review")]
        return form

    def form_valid(self, form):
        form.instance.prepared_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("assessments:teaching-plans")


class SchemeWorkflowView(AcademicStaffRequiredMixin, View):
    def post(self, request, pk):
        scheme = get_object_or_404(SchemeOfWork.objects.filter(allocation__in=planning_allocations(request.user), is_deleted=False), pk=pk)
        operation = request.POST.get("operation")
        if operation == "submit" and request.user.pk == scheme.allocation.teacher_id:
            scheme.status = "submitted"
        elif operation in {"approve", "changes"}:
            department = scheme.allocation.subject.department
            can_review = request.user.is_superuser or request.user.role in ACADEMIC_MANAGERS or (department and department.head_id == request.user.pk)
            if not can_review:
                messages.error(request, "Only the subject HOD or academic management may review this scheme.")
                return redirect("assessments:scheme-detail", pk=pk)
            scheme.status = "approved" if operation == "approve" else "changes_requested"
            scheme.reviewed_by = request.user
            scheme.reviewed_at = timezone.now()
            scheme.review_comments = request.POST.get("comment", "").strip()
        else:
            messages.error(request, "Invalid scheme workflow operation.")
            return redirect("assessments:scheme-detail", pk=pk)
        try:
            scheme.save()
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"Scheme updated to {scheme.get_status_display()}.")
        return redirect("assessments:scheme-detail", pk=pk)


class SubmissionCreateView(LoginRequiredMixin, CreateView):
    model = AssessmentSubmission
    form_class = SubmissionForm
    template_name = "shared/form.html"
    extra_context = {"page_title": "Submit assignment", "eyebrow": "Student portal", "submit_label": "Submit work"}

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "student" or not hasattr(request.user, "student_profile"):
            raise Http404
        self.assessment = get_object_or_404(Assessment, pk=kwargs["pk"], status="published", stream=request.user.student_profile.stream, is_deleted=False)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.assessment = self.assessment
        form.instance.student = self.request.user.student_profile
        messages.success(self.request, "Your work has been submitted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("dashboard")


class SetupTableView(AcademicManagerRequiredMixin, ModelTableView):
    pass


class SetupCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    template_name = "shared/form.html"
    audit_action = "create"


class SetupUpdateView(AcademicManagerRequiredMixin, AuditedFormMixin, UpdateView):
    template_name = "shared/form.html"
    audit_action = "update"
