from django import forms

from config.forms import DateRangeValidationMixin, StyledModelForm
from .models import (
    AcademicYear, CalendarEvent, ClassLevel, Department, SchoolProfile,
    Stream, Subject, SubjectAllocation, SubjectCombination, Term,
)


class SchoolProfileForm(StyledModelForm):
    class Meta:
        model = SchoolProfile
        exclude = ("created_at", "updated_at", "deleted_at", "is_deleted")


class AcademicYearForm(DateRangeValidationMixin, StyledModelForm):
    class Meta:
        model = AcademicYear
        fields = ("name", "start_date", "end_date", "is_current", "is_closed")


class TermForm(DateRangeValidationMixin, StyledModelForm):
    class Meta:
        model = Term
        fields = ("academic_year", "name", "number", "start_date", "end_date", "is_current", "is_closed")


class DepartmentForm(StyledModelForm):
    class Meta:
        model = Department
        fields = ("name", "code", "description", "head")


class ClassLevelForm(StyledModelForm):
    class Meta:
        model = ClassLevel
        fields = ("name", "curriculum", "level", "description")


class StreamForm(StyledModelForm):
    class Meta:
        model = Stream
        fields = ("name", "class_level", "academic_year", "class_teacher", "room_name", "capacity")


class SubjectForm(StyledModelForm):
    class Meta:
        model = Subject
        fields = ("name", "short_name", "code", "uneb_code", "department", "subject_type", "curriculum_level", "pass_mark", "description", "is_active")


class SubjectCombinationForm(StyledModelForm):
    class Meta:
        model = SubjectCombination
        fields = ("name", "code", "curriculum_level", "subjects", "description", "is_active")
        widgets = {"subjects": forms.SelectMultiple(attrs={"size": 8})}


class SubjectAllocationForm(StyledModelForm):
    class Meta:
        model = SubjectAllocation
        fields = ("teacher", "subject", "stream", "term", "lessons_per_week", "is_active")


class CalendarEventForm(DateRangeValidationMixin, StyledModelForm):
    class Meta:
        model = CalendarEvent
        fields = ("term", "title", "category", "start_date", "end_date", "description")
