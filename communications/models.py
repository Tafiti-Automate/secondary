from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from academics.models import ClassLevel, Stream, Subject
from accounts.models import User
from config.models import BaseModel
from students.models import Student


class Announcement(BaseModel):
    AUDIENCES = [("all", "Everyone"), ("staff", "All staff"), ("teachers", "Teachers"), ("students", "Students"), ("parents", "Parents"), ("stream", "Selected stream")]
    title = models.CharField(max_length=180)
    body = models.TextField()
    language = models.CharField(max_length=12, choices=User._meta.get_field("preferred_language").choices, default="en")
    translations = models.JSONField(default=dict, blank=True, help_text="Optional translated title/body objects keyed by language code.")
    audience = models.CharField(max_length=20, choices=AUDIENCES, default="all")
    stream = models.ForeignKey(Stream, related_name="announcements", on_delete=models.CASCADE, null=True, blank=True)
    attachment = models.FileField(upload_to="announcements/%Y/", blank=True, null=True)
    published_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, related_name="announcements", on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["-is_pinned", "-published_at"]

    @property
    def is_live(self):
        return self.published_at <= timezone.now() and (not self.expires_at or self.expires_at >= timezone.now())

    def __str__(self):
        return self.title


class LearningResource(BaseModel):
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(Subject, related_name="learning_resources", on_delete=models.PROTECT)
    class_level = models.ForeignKey(ClassLevel, related_name="learning_resources", on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, related_name="learning_resources", on_delete=models.SET_NULL, null=True, blank=True)
    resource_type = models.CharField(max_length=20, choices=[("notes", "Notes"), ("worksheet", "Worksheet"), ("video", "Video"), ("link", "Web link"), ("past_paper", "Past paper"), ("other", "Other")], default="notes")
    file = models.FileField(upload_to="learning-resources/%Y/", blank=True, null=True)
    external_url = models.URLField(blank=True)
    uploaded_by = models.ForeignKey(User, related_name="learning_resources", on_delete=models.SET_NULL, null=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Notification(BaseModel):
    recipient = models.ForeignKey(User, related_name="notifications", on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    message = models.TextField()
    channel = models.CharField(max_length=20, choices=[("in_app", "In-system"), ("email", "Email"), ("sms", "SMS"), ("whatsapp", "WhatsApp")], default="in_app")
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")], default="pending")
    link = models.CharField(max_length=255, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_read(self):
        return bool(self.read_at)

    def mark_read(self):
        if not self.read_at:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at", "updated_at"])

    def __str__(self):
        return self.title


class ConversationThread(BaseModel):
    subject = models.CharField(max_length=180)
    student = models.ForeignKey(Student, related_name="communication_threads", on_delete=models.SET_NULL, null=True, blank=True)
    participants = models.ManyToManyField(User, related_name="conversation_threads")
    created_by = models.ForeignKey(User, related_name="created_conversation_threads", on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=[("open", "Open"), ("resolved", "Resolved"), ("closed", "Closed")], default="open")
    last_message_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self):
        return self.subject


class ConversationMessage(BaseModel):
    thread = models.ForeignKey(ConversationThread, related_name="messages", on_delete=models.CASCADE)
    sender = models.ForeignKey(User, related_name="conversation_messages", on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    language = models.CharField(max_length=12, choices=User._meta.get_field("preferred_language").choices, default="en")
    translations = models.JSONField(default=dict, blank=True)
    attachment = models.FileField(upload_to="conversations/%Y/", null=True, blank=True)
    read_by = models.ManyToManyField(User, related_name="read_conversation_messages", blank=True)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        ConversationThread.objects.filter(pk=self.thread_id).update(last_message_at=self.created_at or timezone.now())

    def __str__(self):
        return f"{self.thread} · {self.sender or 'System'}"


class ConsentRecord(BaseModel):
    TYPES = [("media", "Photo/video use"), ("trip", "School trip"), ("medical", "Medical support"), ("data", "Data processing"), ("biometric", "Attendance identity use"), ("counselling", "Counselling support"), ("other", "Other")]
    student = models.ForeignKey(Student, related_name="consent_records", on_delete=models.CASCADE)
    consent_type = models.CharField(max_length=24, choices=TYPES)
    policy_version = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("granted", "Granted"), ("declined", "Declined"), ("withdrawn", "Withdrawn"), ("expired", "Expired")], default="pending")
    guardian = models.ForeignKey(User, related_name="learner_consents", on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={"role": "parent"})
    effective_date = models.DateField(default=timezone.localdate)
    expires_on = models.DateField(null=True, blank=True)
    evidence = models.FileField(upload_to="consents/%Y/", null=True, blank=True)
    notes = models.TextField(blank=True)
    captured_by = models.ForeignKey(User, related_name="captured_consents", on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["-effective_date", "student", "consent_type"]

    def clean(self):
        if self.expires_on and self.expires_on < self.effective_date:
            raise ValidationError({"expires_on": "Expiry cannot precede the effective date."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.get_consent_type_display()} · {self.get_status_display()}"


class EmergencyBroadcast(BaseModel):
    title = models.CharField(max_length=180)
    message = models.TextField()
    language = models.CharField(max_length=12, choices=User._meta.get_field("preferred_language").choices, default="en")
    translations = models.JSONField(default=dict, blank=True)
    severity = models.CharField(max_length=16, choices=[("advisory", "Advisory"), ("urgent", "Urgent"), ("critical", "Critical")], default="urgent")
    audience = models.CharField(max_length=20, choices=Announcement.AUDIENCES, default="all")
    stream = models.ForeignKey(Stream, related_name="emergency_broadcasts", on_delete=models.SET_NULL, null=True, blank=True)
    channels = models.JSONField(default=list, help_text="Delivery channels such as in_app, sms, email or whatsapp.")
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("sent", "Sent"), ("cancelled", "Cancelled")], default="draft")
    created_by = models.ForeignKey(User, related_name="created_emergency_broadcasts", on_delete=models.SET_NULL, null=True)
    sent_by = models.ForeignKey(User, related_name="sent_emergency_broadcasts", on_delete=models.SET_NULL, null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivery_summary = models.JSONField(default=dict, blank=True)
    acknowledged_by = models.ManyToManyField(User, related_name="acknowledged_emergency_broadcasts", blank=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.audience == "stream" and not self.stream_id:
            raise ValidationError({"stream": "Select a stream for a stream-specific broadcast."})
        if not isinstance(self.channels, list) or any(channel not in {"in_app", "email", "sms", "whatsapp"} for channel in self.channels):
            raise ValidationError({"channels": "Use a list containing only in_app, email, sms or whatsapp."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title
