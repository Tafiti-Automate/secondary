from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from config.crud import AuditedFormMixin, SoftDeleteView
from config.mixins import AcademicManagerRequiredMixin, ModuleRequiredMixin
from .forms import StaffBankDetailForm, StaffDocumentForm, StaffMemberForm
from .models import StaffBankDetail, StaffDocument, StaffMember


class StaffAccessMixin(ModuleRequiredMixin, AcademicManagerRequiredMixin):
    required_module = "staff"


class StaffListView(StaffAccessMixin, ListView):
    model = StaffMember
    template_name = "staff/staff_list.html"
    context_object_name = "staff_members"
    paginate_by = 24

    def get_queryset(self):
        queryset = StaffMember.objects.filter(is_deleted=False).select_related("department", "user")
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "")
        if query:
            queryset = queryset.filter(Q(staff_number__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(job_title__icontains=query) | Q(phone__icontains=query))
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = StaffMember.STATUSES
        return context


class StaffDetailView(StaffAccessMixin, DetailView):
    model = StaffMember
    template_name = "staff/staff_detail.html"
    context_object_name = "staff_member"

    def get_queryset(self):
        return StaffMember.objects.filter(is_deleted=False).select_related("department", "user").prefetch_related("documents")


class StaffCreateView(StaffAccessMixin, AuditedFormMixin, CreateView):
    model = StaffMember
    form_class = StaffMemberForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Add staff member", "eyebrow": "Staff management", "submit_label": "Save staff member"}

    def get_success_url(self):
        return reverse("staff:detail", args=[self.object.pk])


class StaffUpdateView(StaffAccessMixin, AuditedFormMixin, UpdateView):
    model = StaffMember
    form_class = StaffMemberForm
    template_name = "shared/form.html"
    audit_action = "update"
    extra_context = {"page_title": "Edit staff member", "eyebrow": "Staff management", "submit_label": "Save changes"}

    def get_success_url(self):
        return reverse("staff:detail", args=[self.object.pk])


class StaffDeleteView(StaffAccessMixin, SoftDeleteView):
    model = StaffMember
    success_url_name = "staff:list"


class StaffBankDetailView(StaffAccessMixin, AuditedFormMixin, UpdateView):
    model = StaffBankDetail
    form_class = StaffBankDetailForm
    template_name = "shared/form.html"
    audit_action = "update"
    extra_context = {"page_title": "Staff payment details", "eyebrow": "Staff management", "submit_label": "Save payment details"}

    def dispatch(self, request, *args, **kwargs):
        self.staff_member = get_object_or_404(StaffMember.objects.filter(is_deleted=False), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return StaffBankDetail.objects.filter(staff=self.staff_member).first() or StaffBankDetail(staff=self.staff_member)

    def get_success_url(self):
        return reverse("staff:detail", args=[self.staff_member.pk])


class StaffDocumentCreateView(StaffAccessMixin, AuditedFormMixin, CreateView):
    model = StaffDocument
    form_class = StaffDocumentForm
    template_name = "shared/form.html"
    audit_action = "create"
    extra_context = {"page_title": "Upload staff document", "eyebrow": "Staff management", "submit_label": "Upload document"}

    def dispatch(self, request, *args, **kwargs):
        self.staff_member = get_object_or_404(StaffMember.objects.filter(is_deleted=False), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.staff = self.staff_member
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("staff:detail", args=[self.staff_member.pk])
