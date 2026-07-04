from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from config.crud import AuditedFormMixin, SoftDeleteView
from config.mixins import ACADEMIC_MANAGERS, AcademicManagerRequiredMixin, AcademicStaffRequiredMixin
from accounts.models import User
from .access import conversation_scope
from .forms import AnnouncementForm, ConsentRecordForm, ConversationMessageForm, ConversationThreadForm, EmergencyBroadcastForm, LearningResourceForm
from .models import Announcement, ConsentRecord, ConversationMessage, ConversationThread, EmergencyBroadcast, LearningResource, Notification


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


def visible_threads(user):
    qs = ConversationThread.objects.filter(is_deleted=False).select_related("student", "created_by").prefetch_related("participants")
    if user.is_superuser:
        return qs
    return qs.filter(participants=user)


class ConversationListView(LoginRequiredMixin, ListView):
    template_name = "communications/conversation_list.html"
    context_object_name = "threads"
    paginate_by = 25

    def get_queryset(self):
        return visible_threads(self.request.user)


class ConversationCreateView(LoginRequiredMixin, CreateView):
    model = ConversationThread
    form_class = ConversationThreadForm
    template_name = "shared/form.html"
    extra_context = {"page_title": "Start a conversation", "eyebrow": "Family and school communication", "submit_label": "Create conversation"}

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        people, students = conversation_scope(self.request.user)
        form.fields["participants"].queryset = people
        form.fields["student"].queryset = students
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        self.object.participants.add(self.request.user)
        return response

    def get_success_url(self):
        return reverse("communications:conversation-detail", args=[self.object.pk])


class ConversationDetailView(LoginRequiredMixin, View):
    template_name = "communications/conversation_detail.html"

    def thread(self, request, pk):
        return get_object_or_404(visible_threads(request.user), pk=pk)

    def get(self, request, pk):
        thread = self.thread(request, pk)
        rows = []
        for message in thread.messages.filter(is_deleted=False).select_related("sender"):
            translated = message.translations.get(request.user.preferred_language, message.body)
            if isinstance(translated, dict):
                translated = translated.get("body", message.body)
            rows.append({"message": message, "display_body": translated})
            message.read_by.add(request.user)
        return render(request, self.template_name, {"thread": thread, "rows": rows, "form": ConversationMessageForm()})

    def post(self, request, pk):
        thread = self.thread(request, pk)
        if thread.status != "open":
            messages.error(request, "This conversation is closed.")
            return redirect("communications:conversation-detail", pk=pk)
        form = ConversationMessageForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.thread = thread
            item.sender = request.user
            item.save()
            item.read_by.add(request.user)
            for participant in thread.participants.exclude(pk=request.user.pk):
                Notification.objects.create(recipient=participant, title=thread.subject, message=item.body, status="sent", link=reverse("communications:conversation-detail", args=[thread.pk]))
            return redirect("communications:conversation-detail", pk=pk)
        rows = [{"message": item, "display_body": item.body} for item in thread.messages.filter(is_deleted=False).select_related("sender")]
        return render(request, self.template_name, {"thread": thread, "rows": rows, "form": form})


class ConsentListView(LoginRequiredMixin, ListView):
    template_name = "communications/consent_list.html"
    context_object_name = "consents"
    paginate_by = 30

    def get_queryset(self):
        qs = ConsentRecord.objects.filter(is_deleted=False).select_related("student", "guardian", "captured_by")
        if self.request.user.is_superuser or self.request.user.role in ACADEMIC_MANAGERS:
            return qs
        if self.request.user.role == "parent":
            return qs.filter(Q(guardian=self.request.user) | Q(student__parent=self.request.user) | Q(student__guardian_links__guardian__user=self.request.user)).distinct()
        if self.request.user.role == "student":
            return qs.filter(student__user=self.request.user)
        return qs.none()


class ConsentCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = ConsentRecord
    form_class = ConsentRecordForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("communications:consents")
    audit_action = "create"
    extra_context = {"page_title": "Record consent", "eyebrow": "Consent register", "submit_label": "Save consent"}

    def form_valid(self, form):
        form.instance.captured_by = self.request.user
        return super().form_valid(form)


class EmergencyBroadcastListView(AcademicManagerRequiredMixin, ListView):
    queryset = EmergencyBroadcast.objects.filter(is_deleted=False).select_related("stream", "created_by", "sent_by")
    template_name = "communications/emergency_list.html"
    context_object_name = "broadcasts"


class EmergencyBroadcastCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    model = EmergencyBroadcast
    form_class = EmergencyBroadcastForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("communications:emergency-list")
    audit_action = "create"
    extra_context = {"page_title": "Prepare emergency message", "eyebrow": "Emergency communication", "submit_label": "Save draft"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class EmergencyBroadcastSendView(AcademicManagerRequiredMixin, View):
    def post(self, request, pk):
        broadcast = get_object_or_404(EmergencyBroadcast, pk=pk, status="draft", is_deleted=False)
        recipients = User.objects.filter(is_active=True, is_deleted=False)
        role_map = {"staff": ["super_admin", "headteacher", "director_of_studies", "teacher", "bursar"], "teachers": ["teacher"], "students": ["student"], "parents": ["parent"]}
        if broadcast.audience in role_map:
            recipients = recipients.filter(role__in=role_map[broadcast.audience])
        elif broadcast.audience == "stream" and broadcast.stream_id:
            recipients = recipients.filter(Q(student_profile__stream=broadcast.stream) | Q(children__stream=broadcast.stream) | Q(guardian_profile__student_links__student__stream=broadcast.stream)).distinct()
        channels = [channel for channel in broadcast.channels if channel in {"in_app", "email", "sms", "whatsapp"}] or ["in_app"]
        queued = 0
        for recipient in recipients:
            translation = broadcast.translations.get(recipient.preferred_language, {})
            title = translation.get("title", broadcast.title) if isinstance(translation, dict) else broadcast.title
            body = translation.get("message", broadcast.message) if isinstance(translation, dict) else (translation or broadcast.message)
            for channel in channels:
                Notification.objects.create(recipient=recipient, title=title, message=body, channel=channel, status="sent" if channel == "in_app" else "pending")
                queued += 1
        broadcast.status = "sent"
        broadcast.sent_by = request.user
        broadcast.sent_at = timezone.now()
        broadcast.delivery_summary = {"recipients": recipients.count(), "deliveries": queued, "channels": channels}
        broadcast.save(update_fields=["status", "sent_by", "sent_at", "delivery_summary", "updated_at"])
        messages.success(request, f"Emergency message queued for {recipients.count()} recipient(s) across {len(channels)} channel(s).")
        return redirect("communications:emergency-list")
