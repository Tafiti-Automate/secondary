from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from config.models import BaseModel


class User(AbstractUser, BaseModel):
    ROLE_CHOICES = [
        ("super_admin", "Super Administrator"),
        ("headteacher", "Headteacher"),
        ("director_of_studies", "Director of Studies"),
        ("teacher", "Teacher"),
        ("bursar", "Bursar"),
        ("parent", "Parent"),
        ("student", "Student"),
    ]
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="teacher")
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)
    must_change_password = models.BooleanField(default=False)
    last_activity = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.get_full_name() or self.username


class AuditLog(models.Model):
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    action = models.CharField(max_length=32)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=255)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.actor or 'System'} · {self.action} · {self.entity_type}"
