import csv
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from config.crud import AuditedFormMixin, SoftDeleteView
from config.audit import record_audit
from config.mixins import ACADEMIC_MANAGERS, AcademicManagerRequiredMixin, AcademicStaffRequiredMixin
from config.tables import ModelTableView
from students.models import Student
from academics.models import ClassLevel, Subject, SubjectAllocation, Term
from communications.services import queue_notification
from .forms import ActivityOfIntegrationForm, AssessmentEvidenceForm, AssessmentForm, AssessmentPolicyForm, AssessmentScaleForm, AssessmentTypeForm, CompetencyForm, CompetencyIndicatorForm, CompetencyLevelForm, CurriculumFrameworkForm, CurriculumImportForm, CurriculumTopicForm, CurriculumValueForm, EvidenceAssetForm, LearningOutcomeForm, LessonPlanForm, PortfolioItemForm, ProjectMilestoneForm, ProjectTeamForm, ProjectTeamMemberForm, RubricCriterionForm, RubricForm, RubricLevelForm, SchemeOfWorkForm, SchemeWeekForm, SubmissionForm, TeacherObservationForm
from .models import ActivityOfIntegration, Assessment, AssessmentEvidence, AssessmentPolicy, AssessmentResult, AssessmentScale, AssessmentSubmission, AssessmentType, Competency, CompetencyAssessment, CompetencyIndicator, CompetencyLevel, CurriculumFramework, CurriculumLearningArea, CurriculumTopic, CurriculumValue, EvidenceAsset, LearnerSkillRating, LearnerValueRating, LearningOutcome, LearningOutcomeAssessment, LessonPlan, PortfolioItem, ProjectMilestone, ProjectTeam, ProjectTeamMember, Rubric, RubricCriterion, RubricLevel, RubricRating, SchemeOfWork, SchemeWeek, Skill, TeacherObservation


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


def teacher_can_record_for(user, student, term=None, subject=None):
    if user.is_superuser or user.role in ACADEMIC_MANAGERS:
        return True
    if user.role != "teacher" or not student.stream_id:
        return False
    if student.stream.class_teacher_id == user.pk:
        return True
    allocations = SubjectAllocation.objects.filter(
        Q(teacher=user) | Q(subject__department__head=user),
        stream=student.stream, is_deleted=False, is_active=True,
    )
    if term:
        allocations = allocations.filter(term=term)
    if subject:
        allocations = allocations.filter(subject=subject)
    return allocations.exists()


def achievement_levels_for(assessment):
    policy = AssessmentPolicy.objects.filter(
        academic_year=assessment.term.academic_year,
        class_level=assessment.stream.class_level,
        purpose="internal",
        is_active=True,
        is_deleted=False,
    ).select_related("achievement_scale").first()
    scale = policy.achievement_scale if policy and policy.achievement_scale_id else AssessmentScale.objects.filter(
        is_default=True, is_active=True, is_deleted=False,
    ).first()
    levels = CompetencyLevel.objects.filter(is_deleted=False)
    return levels.filter(scale=scale) if scale else levels


def visible_portfolio_items(user):
    qs = PortfolioItem.objects.filter(is_deleted=False).select_related(
        "student__stream__class_level", "term", "subject", "assessment", "project_milestone", "learning_outcome",
        "uploaded_by", "verified_by",
    )
    if user.is_superuser or user.role in ACADEMIC_MANAGERS:
        return qs
    if user.role == "teacher":
        allocations = SubjectAllocation.objects.filter(
            Q(teacher=user) | Q(subject__department__head=user),
            stream_id=OuterRef("student__stream_id"), term_id=OuterRef("term_id"),
            is_deleted=False, is_active=True,
        )
        subject_allocation = allocations.filter(subject_id=OuterRef("subject_id"))
        return qs.annotate(
            has_allocation=Exists(allocations), has_subject_allocation=Exists(subject_allocation),
        ).filter(
            Q(student__stream__class_teacher=user)
            | Q(subject__isnull=True, has_allocation=True)
            | Q(has_subject_allocation=True)
        )
    if user.role == "student":
        return qs.filter(student__user=user)
    if user.role == "parent":
        return qs.filter(
            Q(student__parent=user) | Q(student__guardian_links__guardian__user=user),
            status="verified",
        ).distinct()
    return qs.none()


def visible_portfolio_students(user):
    qs = Student.objects.filter(is_deleted=False).select_related("stream__class_level")
    if user.is_superuser or user.role in ACADEMIC_MANAGERS:
        return qs
    if user.role == "teacher":
        return qs.filter(
            Q(stream__class_teacher=user)
            | Q(stream__subject_allocations__teacher=user, stream__subject_allocations__is_deleted=False, stream__subject_allocations__is_active=True)
            | Q(stream__subject_allocations__subject__department__head=user, stream__subject_allocations__is_deleted=False, stream__subject_allocations__is_active=True)
        ).distinct()
    if user.role == "student":
        return qs.filter(user=user)
    if user.role == "parent":
        return qs.filter(Q(parent=user) | Q(guardian_links__guardian__user=user)).distinct()
    return qs.none()


def scope_portfolio_form(form, user):
    active_students = visible_portfolio_students(user).filter(is_active=True)
    if user.role == "student" and not user.is_superuser:
        student = active_students.filter(user=user).first()
        form.fields["student"].queryset = active_students.filter(pk=getattr(student, "pk", None))
        form.fields["student"].initial = student
        form.fields["student"].widget = form.fields["student"].hidden_widget()
        if student and student.stream_id:
            form.fields["term"].queryset = Term.objects.filter(academic_year=student.stream.academic_year, is_deleted=False)
            form.fields["assessment"].queryset = Assessment.objects.filter(stream=student.stream, status="published", is_deleted=False)
            form.fields["project_milestone"].queryset = ProjectMilestone.objects.filter(
                assessment__stream=student.stream, assessment__status="published", is_deleted=False,
            )
            form.fields["subject"].queryset = Subject.objects.filter(
                Q(allocations__stream=student.stream) | Q(student_registrations__enrollment__student=student, student_registrations__status="active"),
                is_deleted=False,
            ).distinct()
            form.fields["learning_outcome"].queryset = LearningOutcome.objects.filter(topic__class_level=student.stream.class_level, is_deleted=False)
        return form

    if user.role == "teacher" and not user.is_superuser:
        allocations = planning_allocations(user)
        stream_ids = allocations.values_list("stream_id", flat=True)
        students = active_students.filter(Q(stream_id__in=stream_ids) | Q(stream__class_teacher=user)).distinct()
        form.fields["student"].queryset = students
        form.fields["term"].queryset = Term.objects.filter(Q(subject_allocations__in=allocations) | Q(academic_year__streams__class_teacher=user), is_deleted=False).distinct()
        form.fields["subject"].queryset = Subject.objects.filter(Q(allocations__in=allocations) | Q(department__head=user), is_deleted=False).distinct()
        form.fields["assessment"].queryset = teacher_assessments(user)
        form.fields["project_milestone"].queryset = ProjectMilestone.objects.filter(
            assessment__in=form.fields["assessment"].queryset, is_deleted=False,
        )
        form.fields["learning_outcome"].queryset = LearningOutcome.objects.filter(topic__subject__in=form.fields["subject"].queryset, is_deleted=False).distinct()
        return form

    form.fields["student"].queryset = active_students
    form.fields["term"].queryset = Term.objects.filter(is_deleted=False)
    form.fields["subject"].queryset = Subject.objects.filter(is_deleted=False, is_active=True)
    form.fields["assessment"].queryset = Assessment.objects.filter(is_deleted=False)
    form.fields["project_milestone"].queryset = ProjectMilestone.objects.filter(is_deleted=False)
    form.fields["learning_outcome"].queryset = LearningOutcome.objects.filter(is_deleted=False)
    return form


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
        return teacher_assessments(self.request.user).prefetch_related("results__student", "submissions__student", "learning_outcomes", "evidence_records__student", "evidence_records__assets", "reviews__reviewer", "project_teams__members__student")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object.subject.department
        context["is_hod"] = bool(
            self.request.user.is_superuser
            or self.request.user.role in ACADEMIC_MANAGERS
            or (department and department.head_id == self.request.user.pk)
        )
        context["project_milestones"] = self.object.project_milestones.filter(is_deleted=False).prefetch_related("portfolio_items")
        context["project_teams"] = self.object.project_teams.filter(is_deleted=False).prefetch_related("members__student")
        return context


class ProjectMilestoneCreateView(AcademicStaffRequiredMixin, CreateView):
    model = ProjectMilestone
    form_class = ProjectMilestoneForm
    template_name = "shared/form.html"
    extra_context = {
        "page_title": "Add project milestone",
        "eyebrow": "Project planning",
        "submit_label": "Save milestone",
    }

    def dispatch(self, request, *args, **kwargs):
        self.assessment = get_object_or_404(teacher_assessments(request.user), pk=kwargs["pk"])
        if not self.assessment.project_enabled:
            raise Http404
        if self.assessment.is_workflow_locked:
            raise PermissionDenied("DOS-approved project plans are read-only.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.assessment = self.assessment
        response = super().form_valid(form)
        record_audit(self.request, "project_milestone_create", self.object, f"Added milestone to {self.assessment.title}")
        messages.success(self.request, "Project milestone added.")
        return response

    def get_success_url(self):
        return reverse("assessments:detail", args=[self.assessment.pk])


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
        levels = achievement_levels_for(assessment)
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
        levels = {str(x.pk): x for x in achievement_levels_for(assessment)}
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


class CBCEvidenceEntryView(AcademicStaffRequiredMixin, View):
    template_name = "assessments/cbc_evidence_entry.html"
    sections = {"outcomes", "skills", "values"}

    def get_assessment(self, request, pk):
        return get_object_or_404(
            teacher_assessments(request.user).select_related("stream__class_level", "topic", "subject", "term"),
            pk=pk,
            stream__class_level__curriculum="lower",
        )

    @staticmethod
    def evidence_items(assessment):
        outcomes = assessment.learning_outcomes.filter(is_deleted=False).order_by("display_order", "pk")
        if not outcomes.exists() and assessment.topic_id:
            outcomes = assessment.topic.learning_outcomes.filter(is_deleted=False).order_by("display_order", "pk")
        skills = Skill.objects.filter(is_deleted=False, is_active=True).order_by("display_order", "name")
        linked_value_ids = outcomes.values_list("values__pk", flat=True)
        values = CurriculumValue.objects.filter(is_deleted=False)
        if any(linked_value_ids):
            values = values.filter(pk__in=linked_value_ids)
        return outcomes, skills, values.order_by("display_order", "name")

    @staticmethod
    def achievement_levels(assessment):
        return achievement_levels_for(assessment)

    def build_context(self, request, assessment, section):
        students = list(Student.objects.filter(stream=assessment.stream, is_deleted=False, is_active=True).order_by("first_name", "last_name"))
        outcomes, skills, values = self.evidence_items(assessment)
        levels = list(self.achievement_levels(assessment).order_by("display_order", "numeric_value"))
        context = {
            "assessment": assessment,
            "active_section": section,
            "levels": levels,
            "student_count": len(students),
            "locked": assessment.is_workflow_locked,
        }
        if section == "outcomes":
            items = list(outcomes)
            existing = {(item.student_id, item.outcome_id): item for item in LearningOutcomeAssessment.objects.filter(assessment=assessment, is_deleted=False)}
            context["rows"] = [{"student": student, "ratings": [{"item": item, "rating": existing.get((student.pk, item.pk))} for item in items]} for student in students]
            context["items"] = items
        elif section == "skills":
            items = list(skills)
            existing = {(item.student_id, item.skill_id): item for item in LearnerSkillRating.objects.filter(assessment=assessment, is_deleted=False).select_related("level")}
            context["rows"] = [{"student": student, "ratings": [{"item": item, "rating": existing.get((student.pk, item.pk))} for item in items]} for student in students]
            context["items"] = items
        else:
            items = list(values)
            existing = {(item.student_id, item.value_id): item for item in LearnerValueRating.objects.filter(assessment=assessment, is_deleted=False).select_related("level")}
            context["rows"] = [{"student": student, "ratings": [{"item": item, "rating": existing.get((student.pk, item.pk))} for item in items]} for student in students]
            context["items"] = items
        return context

    def get(self, request, pk):
        assessment = self.get_assessment(request, pk)
        section = request.GET.get("section", "outcomes")
        section = section if section in self.sections else "outcomes"
        return render(request, self.template_name, self.build_context(request, assessment, section))

    @transaction.atomic
    def post(self, request, pk):
        assessment = self.get_assessment(request, pk)
        section = request.POST.get("section", "outcomes")
        section = section if section in self.sections else "outcomes"
        if assessment.is_workflow_locked:
            messages.error(request, "DOS-approved CBC evidence is read-only.")
            return redirect(f"{reverse('assessments:cbc-evidence', args=[pk])}?section={section}")

        students = list(Student.objects.filter(stream=assessment.stream, is_deleted=False, is_active=True))
        outcomes, skills, values = self.evidence_items(assessment)
        saved = cleared = 0
        now = timezone.now()
        if section == "outcomes":
            level_map = {str(level.pk): level for level in self.achievement_levels(assessment)}
            for student in students:
                for outcome in outcomes:
                    level = level_map.get(request.POST.get(f"rating_{student.pk}_{outcome.pk}", ""))
                    existing = LearningOutcomeAssessment.objects.filter(assessment=assessment, student=student, outcome=outcome, is_deleted=False).first()
                    if level:
                        if existing:
                            existing.scale_level, existing.level = level, level.code
                            existing.assessed_by, existing.assessed_at = request.user, now
                            existing.save(update_fields=["scale_level", "level", "assessed_by", "assessed_at", "updated_at"])
                        else:
                            LearningOutcomeAssessment.objects.create(
                                assessment=assessment, student=student, outcome=outcome,
                                term=assessment.term, scale_level=level, assessed_by=request.user,
                            )
                        saved += 1
                    elif existing:
                        existing.soft_delete()
                        cleared += 1
        else:
            level_map = {str(level.pk): level for level in self.achievement_levels(assessment)}
            item_list = skills if section == "skills" else values
            model = LearnerSkillRating if section == "skills" else LearnerValueRating
            item_field = "skill" if section == "skills" else "value"
            for student in students:
                for item in item_list:
                    level = level_map.get(request.POST.get(f"rating_{student.pk}_{item.pk}", ""))
                    lookup = {"assessment": assessment, "student": student, item_field: item, "is_deleted": False}
                    existing = model.objects.filter(**lookup).first()
                    if level:
                        if existing:
                            existing.level, existing.assessed_by, existing.assessed_at = level, request.user, now
                            existing.save(update_fields=["level", "assessed_by", "assessed_at", "updated_at"])
                        else:
                            model.objects.create(
                                assessment=assessment, student=student, term=assessment.term,
                                subject=assessment.subject, level=level, assessed_by=request.user,
                                **{item_field: item},
                            )
                        saved += 1
                    elif existing:
                        existing.soft_delete()
                        cleared += 1

        record_audit(request, f"cbc_{section}_entry", assessment, f"Saved {saved} CBC {section} rating(s)", {"saved": saved, "cleared": cleared})
        messages.success(request, f"Saved {saved} {section} rating(s){f' and cleared {cleared}' if cleared else ''}.")
        return redirect(f"{reverse('assessments:cbc-evidence', args=[pk])}?section={section}")


class TeacherObservationCreateView(AcademicStaffRequiredMixin, CreateView):
    model = TeacherObservation
    form_class = TeacherObservationForm
    template_name = "shared/form.html"
    extra_context = {"page_title": "Record learner observation", "eyebrow": "CBC narrative evidence", "submit_label": "Save observation"}

    def get_initial(self):
        initial = super().get_initial()
        initial.update({
            "student": self.request.GET.get("student"),
            "assessment": self.request.GET.get("assessment"),
            "term": self.request.GET.get("term"),
            "subject": self.request.GET.get("subject"),
        })
        assessment = teacher_assessments(self.request.user).filter(pk=initial.get("assessment")).first()
        if assessment:
            initial.update({"term": assessment.term_id, "subject": assessment.subject_id})
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        allowed = teacher_assessments(self.request.user)
        if self.request.user.is_superuser or self.request.user.role in ACADEMIC_MANAGERS:
            form.fields["student"].queryset = Student.objects.filter(is_deleted=False, is_active=True)
            form.fields["term"].queryset = Term.objects.filter(is_deleted=False)
            form.fields["subject"].queryset = Subject.objects.filter(is_deleted=False, is_active=True)
            form.fields["assessment"].queryset = Assessment.objects.filter(is_deleted=False)
        else:
            stream_ids = allowed.values_list("stream_id", flat=True)
            form.fields["student"].queryset = Student.objects.filter(Q(stream_id__in=stream_ids) | Q(stream__class_teacher=self.request.user), is_deleted=False, is_active=True).distinct()
            form.fields["term"].queryset = Term.objects.filter(pk__in=allowed.values_list("term_id", flat=True), is_deleted=False)
            form.fields["subject"].queryset = Subject.objects.filter(pk__in=allowed.values_list("subject_id", flat=True), is_deleted=False)
            form.fields["assessment"].queryset = allowed
        form.fields["competencies"].queryset = Competency.objects.filter(is_deleted=False, is_active=True)
        form.fields["skills"].queryset = Skill.objects.filter(is_deleted=False, is_active=True)
        form.fields["values"].queryset = CurriculumValue.objects.filter(is_deleted=False)
        return form

    def form_valid(self, form):
        student, term, subject = form.cleaned_data["student"], form.cleaned_data["term"], form.cleaned_data.get("subject")
        if not teacher_can_record_for(self.request.user, student, term, subject):
            raise PermissionDenied("You may only record observations for learners assigned to your class or subject.")
        form.instance.observed_by = self.request.user
        response = super().form_valid(form)
        record_audit(self.request, "teacher_observation", self.object, f"Recorded {self.object.get_category_display()} observation for {student.full_name}")
        messages.success(self.request, "Learner observation saved.")
        return response

    def get_success_url(self):
        if self.object.assessment_id:
            return reverse("assessments:cbc-evidence", args=[self.object.assessment_id])
        return reverse("students:detail", args=[self.object.student_id])


class PortfolioListView(LoginRequiredMixin, ListView):
    template_name = "assessments/portfolio_list.html"
    context_object_name = "portfolio_items"
    paginate_by = 18

    def get_queryset(self):
        qs = visible_portfolio_items(self.request.user)
        if self.request.GET.get("student"):
            qs = qs.filter(student_id=self.request.GET["student"])
        if self.request.GET.get("term"):
            qs = qs.filter(term_id=self.request.GET["term"])
        if self.request.GET.get("status"):
            qs = qs.filter(status=self.request.GET["status"])
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(student__first_name__icontains=query) | Q(student__last_name__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "terms": Term.objects.filter(is_deleted=False),
            "statuses": PortfolioItem._meta.get_field("status").choices,
            "can_upload": self.request.user.is_superuser or self.request.user.role in ACADEMIC_MANAGERS | {"teacher", "student"},
            "selected_student": visible_portfolio_students(self.request.user).filter(pk=self.request.GET.get("student")).first(),
        })
        return context


class PortfolioFormScopeMixin:
    def get_form(self, form_class=None):
        return scope_portfolio_form(super().get_form(form_class), self.request.user)


class PortfolioItemCreateView(LoginRequiredMixin, PortfolioFormScopeMixin, CreateView):
    model = PortfolioItem
    form_class = PortfolioItemForm
    template_name = "assessments/portfolio_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.role in ACADEMIC_MANAGERS | {"teacher", "student"}):
            raise PermissionDenied("You do not have permission to upload portfolio evidence.")
        if request.user.role == "student" and not hasattr(request.user, "student_profile"):
            raise PermissionDenied("A linked learner profile is required.")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial.update({
            "student": self.request.GET.get("student"), "term": self.request.GET.get("term"),
            "subject": self.request.GET.get("subject"), "assessment": self.request.GET.get("assessment"),
            "project_milestone": self.request.GET.get("milestone"), "learning_outcome": self.request.GET.get("outcome"),
        })
        if self.request.user.role == "student" and hasattr(self.request.user, "student_profile"):
            initial["student"] = self.request.user.student_profile.pk
            current_term = Term.objects.filter(is_current=True, is_deleted=False).first()
            if current_term:
                initial["term"] = current_term.pk
        assessment = teacher_assessments(self.request.user).filter(pk=initial.get("assessment")).first() if self.request.user.role != "student" else None
        if assessment:
            initial.update({"term": assessment.term_id, "subject": assessment.subject_id})
        return initial

    def form_valid(self, form):
        if self.request.user.role == "student" and not self.request.user.is_superuser:
            if not hasattr(self.request.user, "student_profile"):
                raise PermissionDenied("A linked learner profile is required.")
            form.instance.student = self.request.user.student_profile
        elif not teacher_can_record_for(self.request.user, form.cleaned_data["student"], form.cleaned_data["term"], form.cleaned_data.get("subject")):
            raise PermissionDenied("You may only upload evidence for learners assigned to your class or subject.")
        if form.instance.assessment_id and not form.instance.subject_id:
            form.instance.subject = form.instance.assessment.subject
        form.instance.stream = form.instance.student.stream
        form.instance.uploaded_by = self.request.user
        form.instance.status = "submitted"
        response = super().form_valid(form)
        record_audit(self.request, "portfolio_upload", self.object, f"Uploaded portfolio evidence for {self.object.student.full_name}")
        messages.success(self.request, "Portfolio evidence submitted for verification.")
        return response

    def get_success_url(self):
        return reverse("assessments:portfolio-detail", args=[self.object.pk])


class PortfolioItemUpdateView(LoginRequiredMixin, PortfolioFormScopeMixin, UpdateView):
    model = PortfolioItem
    form_class = PortfolioItemForm
    template_name = "assessments/portfolio_form.html"

    def get_queryset(self):
        return visible_portfolio_items(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        item = self.get_object()
        if item.status == "verified":
            raise PermissionDenied("Verified portfolio evidence is read-only.")
        if request.user.role == "student" and item.student.user_id != request.user.pk:
            raise PermissionDenied("You may only edit your own portfolio evidence.")
        if request.user.role == "parent":
            raise PermissionDenied("Parents cannot edit learner portfolio evidence.")
        if request.user.role == "teacher" and not teacher_can_record_for(request.user, item.student, item.term, item.subject):
            raise PermissionDenied("You may only edit evidence for learners assigned to you.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if self.request.user.role == "student" and not self.request.user.is_superuser:
            form.instance.student = self.request.user.student_profile
        if form.instance.assessment_id and not form.instance.subject_id:
            form.instance.subject = form.instance.assessment.subject
        form.instance.stream = form.instance.student.stream
        form.instance.status = "submitted"
        form.instance.verified_by = None
        form.instance.verified_at = None
        response = super().form_valid(form)
        record_audit(self.request, "portfolio_update", self.object, "Updated portfolio evidence and resubmitted it")
        messages.success(self.request, "Portfolio evidence updated and resubmitted.")
        return response

    def get_success_url(self):
        return reverse("assessments:portfolio-detail", args=[self.object.pk])


class PortfolioItemDetailView(LoginRequiredMixin, DetailView):
    model = PortfolioItem
    template_name = "assessments/portfolio_detail.html"
    context_object_name = "item"

    def get_queryset(self):
        return visible_portfolio_items(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.object
        context["can_review"] = teacher_can_record_for(self.request.user, item.student, item.term, item.subject)
        context["can_edit"] = item.status != "verified" and (
            self.request.user.is_superuser or self.request.user.role in ACADEMIC_MANAGERS
            or (self.request.user.role == "teacher" and context["can_review"])
            or (self.request.user.role == "student" and item.student.user_id == self.request.user.pk)
        )
        return context


class PortfolioWorkflowView(AcademicStaffRequiredMixin, View):
    @transaction.atomic
    def post(self, request, pk, operation):
        item = get_object_or_404(visible_portfolio_items(request.user), pk=pk)
        if not teacher_can_record_for(request.user, item.student, item.term, item.subject):
            raise PermissionDenied("You may only review evidence for learners assigned to you.")
        feedback = request.POST.get("teacher_feedback", "").strip()
        if operation == "verify":
            item.status = "verified"
            item.verified_by = request.user
            item.verified_at = timezone.now()
            item.teacher_feedback = feedback
            action_message = "Portfolio evidence verified."
        elif operation == "request-changes":
            item.status = "draft"
            item.verified_by = None
            item.verified_at = None
            item.teacher_feedback = feedback
            action_message = "Portfolio evidence returned for changes."
        else:
            raise Http404
        item.save()
        record_audit(request, f"portfolio_{operation}", item, action_message)
        if item.student.user_id:
            queue_notification(
                item.student.user, "Portfolio evidence updated", action_message,
                link=reverse("assessments:portfolio-detail", args=[item.pk]),
            )
        messages.success(request, action_message)
        return redirect("assessments:portfolio-detail", pk=item.pk)


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


class CurriculumFrameworkWorkflowView(AcademicManagerRequiredMixin, View):
    def post(self, request, pk, operation):
        framework = get_object_or_404(CurriculumFramework, pk=pk, is_deleted=False)
        try:
            framework.transition(operation, request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            record_audit(request, f"curriculum_{operation}", framework, f"Curriculum version {operation}")
            messages.success(request, f"Curriculum version {operation} completed.")
        return redirect("assessments:curriculum")


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
        form.fields["learning_outcomes"].queryset = LearningOutcome.objects.filter(assessments__in=allowed, is_deleted=False).distinct()
        form.fields["competencies"].queryset = Competency.objects.filter(is_active=True, is_deleted=False)
        return form

    def get_success_url(self):
        return reverse("assessments:detail", args=[self.object.assessment_id])


class EvidenceAssetCreateView(AcademicStaffRequiredMixin, AuditedFormMixin, CreateView):
    model = EvidenceAsset
    form_class = EvidenceAssetForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Add multimedia evidence", "eyebrow": "Image · audio · video · document", "submit_label": "Save evidence asset"}

    def dispatch(self, request, *args, **kwargs):
        self.evidence = get_object_or_404(
            AssessmentEvidence.objects.filter(assessment__in=teacher_assessments(request.user), is_deleted=False),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.evidence = self.evidence
        form.instance.captured_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("assessments:detail", args=[self.evidence.assessment_id])


class ProjectTeamCreateView(AcademicStaffRequiredMixin, AuditedFormMixin, CreateView):
    model = ProjectTeam
    form_class = ProjectTeamForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Create project team", "eyebrow": "Collaborative project", "submit_label": "Create team"}

    def dispatch(self, request, *args, **kwargs):
        self.assessment = get_object_or_404(teacher_assessments(request.user), pk=kwargs["pk"])
        if not self.assessment.project_enabled:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.assessment = self.assessment
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("assessments:detail", args=[self.assessment.pk])


class ProjectTeamMemberCreateView(AcademicStaffRequiredMixin, AuditedFormMixin, CreateView):
    model = ProjectTeamMember
    form_class = ProjectTeamMemberForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Add project team member", "eyebrow": "Collaborative project", "submit_label": "Add learner"}

    def dispatch(self, request, *args, **kwargs):
        self.team = get_object_or_404(
            ProjectTeam.objects.filter(assessment__in=teacher_assessments(request.user), is_deleted=False),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["student"].queryset = Student.objects.filter(
            stream=self.team.assessment.stream, is_active=True, is_deleted=False,
        ).exclude(project_memberships__team=self.team, project_memberships__is_deleted=False)
        return form

    def form_valid(self, form):
        form.instance.team = self.team
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("assessments:detail", args=[self.team.assessment_id])


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
            topic_count = topic_update_count = outcome_count = outcome_update_count = 0
            framework = form.cleaned_data["framework"]
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
                    if term_number not in {1, 2, 3} or sequence < 1:
                        raise ValueError(f"Row {row_number}: term_number must be 1–3 and sequence must be positive.")
                    expected_stage = "lower" if class_level.curriculum == "lower" else "advanced"
                    if framework.stage != expected_stage:
                        raise ValueError(f"Row {row_number}: {class_level} does not belong to the selected {framework.get_stage_display()} framework.")
                    expected_subject_level = "lower" if class_level.curriculum == "lower" else "upper"
                    if subject.curriculum_level not in {expected_subject_level, "both"}:
                        raise ValueError(f"Row {row_number}: {subject} is not configured for {class_level}.")
                    learning_area = None
                    if row.get("learning_area", "").strip():
                        learning_area, _ = CurriculumLearningArea.objects.update_or_create(
                            framework=framework,
                            subject=subject,
                            name=row["learning_area"].strip(),
                            defaults={
                                "code": row.get("learning_area_code", "").strip(),
                                "sequence": int(row.get("learning_area_order", "1") or 1),
                                "is_deleted": False,
                            },
                        )
                    topic_code = row.get("topic_code", "").strip()
                    topic_lookup = {
                        "framework": framework,
                        "subject": subject,
                        "class_level": class_level,
                        "term_number": term_number,
                    }
                    topic_lookup["code" if topic_code else "sequence"] = topic_code or sequence
                    topic, created = CurriculumTopic.objects.update_or_create(
                        **topic_lookup,
                        defaults={
                            "learning_area": learning_area,
                            "code": topic_code,
                            "title": row["topic_title"].strip(),
                            "description": row.get("topic_description", "").strip(),
                            "suggested_periods": int(row.get("suggested_periods", "1") or 1),
                            "sequence": sequence,
                            "is_deleted": False,
                        },
                    )
                    topic_count += int(created)
                    topic_update_count += int(not created)
                    outcome_code = row.get("learning_outcome_code", "").strip()
                    outcome_statement = row["learning_outcome"].strip()
                    outcome_lookup = {"topic": topic}
                    outcome_lookup["code" if outcome_code else "statement"] = outcome_code or outcome_statement
                    outcome, created = LearningOutcome.objects.update_or_create(
                        **outcome_lookup,
                        defaults={
                            "code": outcome_code,
                            "statement": outcome_statement,
                            "assessment_criteria": row.get("assessment_criteria", "").strip(),
                            "suggested_activities": row.get("suggested_activities", "").strip(),
                            "required_evidence": row.get("required_evidence", "").strip(),
                            "display_order": int(row.get("outcome_order", "1") or 1),
                            "is_deleted": False,
                        },
                    )
                    outcome_count += int(created)
                    outcome_update_count += int(not created)
                    skill_names = [name.strip() for name in row.get("generic_skills", "").split("|") if name.strip()]
                    value_names = [name.strip() for name in row.get("values", "").split("|") if name.strip()]
                    skills = list(Competency.objects.filter(name__in=skill_names, is_active=True, is_deleted=False))
                    values = list(CurriculumValue.objects.filter(name__in=value_names, is_deleted=False))
                    missing_skills = sorted(set(skill_names) - {item.name for item in skills})
                    missing_values = sorted(set(value_names) - {item.name for item in values})
                    if missing_skills or missing_values:
                        missing = ", ".join(missing_skills + missing_values)
                        raise ValueError(f"Row {row_number}: unknown generic skill/value: {missing}.")
                    outcome.generic_skills.set(skills)
                    outcome.values.set(values)
            messages.success(
                request,
                f"Curriculum import complete: {topic_count} topic(s) created, {topic_update_count} updated; "
                f"{outcome_count} outcome(s) created, {outcome_update_count} updated.",
            )
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
