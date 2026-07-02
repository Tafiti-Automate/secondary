from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


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
