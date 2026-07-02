from rest_framework.permissions import BasePermission


class IsAcademicManager(BasePermission):
    roles = {"super_admin", "headteacher", "director_of_studies"}

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.role in self.roles))


class IsAcademicStaff(BasePermission):
    roles = IsAcademicManager.roles | {"teacher"}

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.role in self.roles))


class IsReadOnlyOrAcademicStaff(IsAcademicStaff):
    def has_permission(self, request, view):
        return request.method in {"GET", "HEAD", "OPTIONS"} and request.user.is_authenticated or super().has_permission(request, view)


class IsReadOnlyOrAcademicManager(IsAcademicManager):
    def has_permission(self, request, view):
        return request.method in {"GET", "HEAD", "OPTIONS"} and request.user.is_authenticated or super().has_permission(request, view)
