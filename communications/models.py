from django.db import models
from django.utils import timezone

from academics.models import ClassLevel, Stream, Subject
from accounts.models import User
from config.models import BaseModel


class Announcement(BaseModel):
    AUDIENCES = [("all", "Everyone"), ("staff", "All staff"), ("teachers", "Teachers"), ("students", "Students"), ("parents", "Parents"), ("stream", "Selected stream")]
    title = models.CharField(max_length=180)
    body = models.TextField()
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
