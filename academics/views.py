from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, UpdateView

from config.crud import AuditedFormMixin, SoftDeleteView
from config.mixins import AcademicManagerRequiredMixin
from config.tables import ModelTableView
from students.models import Student
from .forms import SchoolProfileForm
from .models import AcademicYear, ClassLevel, Department, SchoolProfile, Stream, Subject, SubjectAllocation, SubjectCombination, Term


class AcademicsOverviewView(LoginRequiredMixin, TemplateView):
    template_name = "academics/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "years": AcademicYear.objects.filter(is_deleted=False),
            "terms": Term.objects.filter(is_deleted=False).select_related("academic_year")[:6],
            "classes": ClassLevel.objects.filter(is_deleted=False).annotate(stream_count=Count("streams")),
            "streams": Stream.objects.filter(is_deleted=False).select_related("class_level", "class_teacher", "academic_year").annotate(student_count=Count("students")),
            "department_count": Department.objects.filter(is_deleted=False).count(),
            "subject_count": Subject.objects.filter(is_deleted=False, is_active=True).count(),
            "allocation_count": SubjectAllocation.objects.filter(is_deleted=False, is_active=True).count(),
            "student_count": Student.objects.filter(is_deleted=False, is_active=True).count(),
        })
        return context


class ManagedTableView(AcademicManagerRequiredMixin, ModelTableView):
    pass


class ManagedCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"eyebrow": "Academic setup", "submit_label": "Save record"}


class ManagedUpdateView(AcademicManagerRequiredMixin, AuditedFormMixin, UpdateView):
    template_name = "shared/form.html"
    audit_action = "update"
    extra_context = {"eyebrow": "Academic setup", "submit_label": "Save changes"}


class ManagedDeleteView(AcademicManagerRequiredMixin, SoftDeleteView):
    pass


class SchoolProfileView(AcademicManagerRequiredMixin, AuditedFormMixin, UpdateView):
    model = SchoolProfile
    form_class = SchoolProfileForm
    template_name = "academics/school_profile.html"
    success_url = reverse_lazy("academics:school-profile")
    audit_action = "update"

    def get_object(self, queryset=None):
        profile = SchoolProfile.objects.filter(is_deleted=False).first()
        return profile or SchoolProfile.objects.create()
