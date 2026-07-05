from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])


class SchoolModule(BaseModel):
    """A runtime feature switch for one school installation."""

    school = models.ForeignKey("academics.SchoolProfile", related_name="module_settings", on_delete=models.CASCADE)
    code = models.CharField(max_length=32)
    is_enabled = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    enabled_by = models.ForeignKey("accounts.User", related_name="module_changes", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["school", "code"], name="unique_school_module")]

    def __str__(self):
        from config.modules import MODULES

        return f"{self.school} · {MODULES.get(self.code, {}).get('name', self.code.title())}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from config.modules import clear_module_cache

        clear_module_cache(self.school_id)

    def delete(self, *args, **kwargs):
        school_id = self.school_id
        result = super().delete(*args, **kwargs)
        from config.modules import clear_module_cache

        clear_module_cache(school_id)
        return result
