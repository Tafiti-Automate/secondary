from django.urls import path, reverse_lazy

from .forms import AcademicYearForm, CalendarEventForm, ClassLevelForm, DepartmentForm, StreamForm, SubjectAllocationForm, SubjectCombinationForm, SubjectForm, TermForm
from .models import AcademicYear, CalendarEvent, ClassLevel, Department, Stream, Subject, SubjectAllocation, SubjectCombination, Term
from .views import AcademicsOverviewView, ManagedCreateView, ManagedDeleteView, ManagedTableView, ManagedUpdateView, SchoolProfileView

app_name = "academics"

ENTITY_CONFIG = {
    "years": (AcademicYear, AcademicYearForm, ("Academic year", "Starts", "Ends", "Current", "Closed"), ("name", "start_date", "end_date", "is_current", "is_closed"), "Academic years"),
    "terms": (Term, TermForm, ("Term", "Academic year", "Starts", "Ends", "Current"), ("name", "academic_year", "start_date", "end_date", "is_current"), "Terms"),
    "departments": (Department, DepartmentForm, ("Department", "Code", "Head", "Subjects"), ("name", "code", "head", "subjects__count"), "Departments"),
    "classes": (ClassLevel, ClassLevelForm, ("Class", "Level", "Curriculum", "Streams"), ("name", "level", "get_curriculum_display", "streams__count"), "Class levels"),
    "streams": (Stream, StreamForm, ("Stream", "Year", "Class teacher", "Room", "Capacity"), ("__str__", "academic_year", "class_teacher", "room_name", "capacity"), "Streams"),
    "subjects": (Subject, SubjectForm, ("Subject", "Code", "Department", "Type", "Curriculum"), ("name", "code", "department", "get_subject_type_display", "get_curriculum_level_display"), "Subjects"),
    "combinations": (SubjectCombination, SubjectCombinationForm, ("Combination", "Code", "Curriculum", "Subjects", "Active"), ("name", "code", "get_curriculum_level_display", "subjects__count", "is_active"), "Subject combinations"),
    "allocations": (SubjectAllocation, SubjectAllocationForm, ("Teacher", "Subject", "Stream", "Term", "Lessons/week"), ("teacher", "subject", "stream", "term", "lessons_per_week"), "Teacher allocations"),
    "calendar": (CalendarEvent, CalendarEventForm, ("Event", "Term", "Category", "Starts", "Ends"), ("title", "term", "get_category_display", "start_date", "end_date"), "Academic calendar"),
}

urlpatterns = [path("", AcademicsOverviewView.as_view(), name="overview"), path("school/", SchoolProfileView.as_view(), name="school-profile")]

for slug, (model, form_class, columns, fields, title) in ENTITY_CONFIG.items():
    list_name, add_name, edit_name, delete_name = f"{slug}-list", f"{slug}-add", f"{slug}-edit", f"{slug}-delete"
    success = reverse_lazy(f"academics:{list_name}")
    urlpatterns += [
        path(f"{slug}/", ManagedTableView.as_view(model=model, columns=columns, field_paths=fields, page_title=title, create_url_name=f"academics:{add_name}", edit_url_name=f"academics:{edit_name}", delete_url_name=f"academics:{delete_name}", search_fields=("name",) if hasattr(model, "name") else ()), name=list_name),
        path(f"{slug}/add/", ManagedCreateView.as_view(model=model, form_class=form_class, success_url=success, extra_context={"page_title": f"Add {model._meta.verbose_name}", "eyebrow": "Academic setup", "submit_label": "Save record"}), name=add_name),
        path(f"{slug}/<int:pk>/edit/", ManagedUpdateView.as_view(model=model, form_class=form_class, success_url=success, extra_context={"page_title": f"Edit {model._meta.verbose_name}", "eyebrow": "Academic setup", "submit_label": "Save changes"}), name=edit_name),
        path(f"{slug}/<int:pk>/delete/", ManagedDeleteView.as_view(model=model, success_url_name=f"academics:{list_name}"), name=delete_name),
    ]
