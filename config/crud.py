from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import DeleteView

from accounts.models import AuditLog


class AuditedFormMixin:
    audit_action = "save"

    def form_valid(self, form):
        response = super().form_valid(form)
        AuditLog.objects.create(
            actor=self.request.user,
            action=self.audit_action,
            entity_type=self.object._meta.verbose_name.title(),
            entity_id=str(self.object.pk),
            description=f"{self.audit_action.title()}d {self.object}",
            ip_address=self.request.META.get("REMOTE_ADDR"),
        )
        messages.success(self.request, f"{self.object._meta.verbose_name.title()} saved successfully.")
        return response


class SoftDeleteView(DeleteView):
    template_name = "shared/confirm_delete.html"
    success_url_name = "dashboard"

    def form_valid(self, form):
        obj = self.get_object()
        obj.soft_delete()
        AuditLog.objects.create(
            actor=self.request.user,
            action="delete",
            entity_type=obj._meta.verbose_name.title(),
            entity_id=str(obj.pk),
            description=f"Archived {obj}",
            ip_address=self.request.META.get("REMOTE_ADDR"),
        )
        messages.success(self.request, f"{obj._meta.verbose_name.title()} archived.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.success_url_name)
