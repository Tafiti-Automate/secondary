from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from academics.models import SchoolProfile
from config.modules import module_is_enabled


ACADEMIC_MANAGERS = {"super_admin", "headteacher", "director_of_studies"}
ACADEMIC_STAFF = ACADEMIC_MANAGERS | {"teacher"}


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = set()
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.role in self.allowed_roles

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("You do not have permission to access this page.")
        return super().handle_no_permission()


class AcademicManagerRequiredMixin(RoleRequiredMixin):
    allowed_roles = ACADEMIC_MANAGERS


class AcademicStaffRequiredMixin(RoleRequiredMixin):
    allowed_roles = ACADEMIC_STAFF


class FinanceStaffRequiredMixin(RoleRequiredMixin):
    allowed_roles = ACADEMIC_MANAGERS | {"bursar"}


class ModuleRequiredMixin:
    required_module = None

    def dispatch(self, request, *args, **kwargs):
        school = SchoolProfile.objects.filter(is_deleted=False).first()
        if self.required_module and not module_is_enabled(self.required_module, school):
            raise PermissionDenied("This module is not enabled for your school.")
        return super().dispatch(request, *args, **kwargs)
