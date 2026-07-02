from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from config.crud import AuditedFormMixin, SoftDeleteView
from config.mixins import ACADEMIC_MANAGERS, AcademicManagerRequiredMixin, AcademicStaffRequiredMixin
from .forms import AnnouncementForm, LearningResourceForm
from .models import Announcement, LearningResource, Notification


def visible_announcements(user):
    now = timezone.now()
    qs = Announcement.objects.filter(is_deleted=False, published_at__lte=now).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
    if user.is_superuser or user.role in ACADEMIC_MANAGERS:
        return qs
    audiences = ["all"]
    if user.role == "teacher": audiences += ["staff", "teachers"]
    if user.role == "student": audiences += ["students", "stream"]
    if user.role == "parent": audiences += ["parents", "stream"]
    qs = qs.filter(audience__in=audiences)
    if user.role == "student" and hasattr(user, "student_profile"):
        qs = qs.filter(Q(stream__isnull=True) | Q(stream=user.student_profile.stream))
    elif user.role == "parent":
        qs = qs.filter(Q(stream__isnull=True) | Q(stream__students__parent=user) | Q(stream__students__guardian_links__guardian__user=user)).distinct()
    return qs


class AnnouncementListView(LoginRequiredMixin, ListView):
    template_name = "communications/announcement_list.html"
    context_object_name = "announcements"
    paginate_by = 15

    def get_queryset(self):
        return visible_announcements(self.request.user)


class AnnouncementCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("communications:announcements")
    audit_action = "create"
    extra_context = {"page_title": "Publish announcement", "eyebrow": "School communications", "submit_label": "Publish notice"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class AnnouncementUpdateView(AcademicManagerRequiredMixin, AuditedFormMixin, UpdateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("communications:announcements")
    audit_action = "update"
    extra_context = {"page_title": "Edit announcement", "eyebrow": "School communications", "submit_label": "Save changes"}


class ResourceListView(LoginRequiredMixin, ListView):
    template_name = "communications/resource_list.html"
    context_object_name = "resources"
    paginate_by = 18

    def get_queryset(self):
        qs = LearningResource.objects.filter(is_deleted=False, is_published=True).select_related("subject", "class_level", "stream", "uploaded_by")
        user = self.request.user
        if user.role == "student" and hasattr(user, "student_profile") and user.student_profile.stream:
            qs = qs.filter(class_level=user.student_profile.stream.class_level).filter(Q(stream__isnull=True) | Q(stream=user.student_profile.stream))
        if self.request.GET.get("q"):
            qs = qs.filter(Q(title__icontains=self.request.GET["q"]) | Q(description__icontains=self.request.GET["q"]) | Q(subject__name__icontains=self.request.GET["q"]))
        return qs


class ResourceCreateView(AcademicStaffRequiredMixin, AuditedFormMixin, CreateView):
    model = LearningResource
    form_class = LearningResourceForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("communications:resources")
    audit_action = "create"
    extra_context = {"page_title": "Upload learning resource", "eyebrow": "Learning resources", "submit_label": "Publish resource"}

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "communications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user, is_deleted=False)


class NotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.mark_read()
        messages.success(request, "Notification marked as read.")
        return redirect(notification.link or "communications:notifications")
