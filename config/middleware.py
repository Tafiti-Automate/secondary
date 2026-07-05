from django.core.exceptions import PermissionDenied

from academics.models import SchoolProfile
from config.modules import module_is_enabled


MODULE_PATHS = {
    "academics": "academics",
    "students": "students",
    "assessments": "assessments",
    "examinations": "exams",
    "attendance": "attendance",
    "timetables": "timetables",
    "communications": "communications",
    "reports": "reports",
    "staff": "staff",
    "fees": "fees",
    "finance": "finance",
}


class ModuleAccessMiddleware:
    """Block direct URLs as well as hiding disabled modules from navigation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            parts = request.path_info.strip("/").split("/")
            if parts and parts[0] == "api" and len(parts) > 1:
                section = parts[1]
            else:
                section = parts[0] if parts else ""
            module_code = MODULE_PATHS.get(section)
            if module_code:
                school = SchoolProfile.objects.filter(is_deleted=False).first()
                if not module_is_enabled(module_code, school):
                    raise PermissionDenied("This module is not enabled for your school.")
        return self.get_response(request)
