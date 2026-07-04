from django import forms

from academics.models import AcademicYear, Stream, Term
from config.forms import StyledModelForm
from .models import (
    Enrollment, Guardian, Student, StudentAccommodation, StudentAchievement,
    StudentGuardian, StudentInterest, StudentMovement, StudentPromotion,
    StudentSubjectRegistration,
)


class StudentForm(StyledModelForm):
    class Meta:
        model = Student
        fields = (
            "student_number", "admission_number", "user", "first_name", "last_name", "other_names", "gender", "date_of_birth",
            "nationality", "national_id", "religion", "photo", "stream", "subject_combination", "parent",
            "date_admitted", "status", "is_boarding", "house", "address", "district", "previous_school",
            "previous_school_details", "blood_group", "allergies", "medical_information", "special_needs",
        )
        help_texts = {
            "student_number": "Leave blank to generate the learner's permanent school identifier.",
            "admission_number": "Leave blank to generate the admission-year number automatically.",
        }
        widgets = {
            "medical_information": forms.Textarea(attrs={"rows": 3}),
            "special_needs": forms.Textarea(attrs={"rows": 3}),
            "previous_school_details": forms.Textarea(attrs={"rows": 3}),
        }


class GuardianForm(StyledModelForm):
    class Meta:
        model = Guardian
        fields = ("user", "first_name", "last_name", "phone", "alternate_phone", "email", "occupation", "employer", "address", "national_id")


class StudentGuardianForm(StyledModelForm):
    class Meta:
        model = StudentGuardian
        fields = ("student", "guardian", "relationship", "is_primary", "receives_reports", "receives_alerts")


class EnrollmentForm(StyledModelForm):
    class Meta:
        model = Enrollment
        fields = ("student", "academic_year", "stream", "subject_combination", "roll_number", "status", "enrolled_on")


class PromotionForm(StyledModelForm):
    class Meta:
        model = StudentPromotion
        fields = ("student", "from_stream", "to_stream", "academic_year", "term", "decision", "remarks", "decision_date")


class SubjectRegistrationForm(StyledModelForm):
    class Meta:
        model = StudentSubjectRegistration
        fields = ("enrollment", "subject", "category", "status", "registered_on", "dropped_on", "reason")


class StudentMovementForm(StyledModelForm):
    class Meta:
        model = StudentMovement
        fields = ("student", "movement_type", "effective_date", "previous_school", "destination", "reason", "reference_number", "document")


class StudentAccommodationForm(StyledModelForm):
    class Meta:
        model = StudentAccommodation
        fields = ("category", "title", "need_description", "support_strategy", "start_date", "review_date", "end_date", "status", "confidential")
        widgets = {
            "need_description": forms.Textarea(attrs={"rows": 3}),
            "support_strategy": forms.Textarea(attrs={"rows": 4}),
        }


class StudentInterestForm(StyledModelForm):
    class Meta:
        model = StudentInterest
        fields = ("name", "category", "engagement_level", "notes", "first_observed", "is_active")
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class StudentAchievementForm(StyledModelForm):
    class Meta:
        model = StudentAchievement
        fields = ("title", "category", "achievement_date", "level", "issuer", "description", "evidence", "external_reference")
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class StudentImportForm(forms.Form):
    academic_year = forms.ModelChoiceField(queryset=AcademicYear.objects.filter(is_deleted=False))
    stream = forms.ModelChoiceField(queryset=Stream.objects.filter(is_deleted=False))
    csv_file = forms.FileField(help_text="UTF-8 CSV using the provided template; maximum 2 MB.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_csv_file(self):
        upload = self.cleaned_data["csv_file"]
        if upload.size > 2 * 1024 * 1024:
            raise forms.ValidationError("CSV file must be 2 MB or smaller.")
        if not upload.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a .csv file.")
        return upload

    def clean(self):
        cleaned = super().clean()
        year, stream = cleaned.get("academic_year"), cleaned.get("stream")
        if year and stream and stream.academic_year_id != year.pk:
            self.add_error("stream", "Stream does not belong to the selected academic year.")
        return cleaned


class BulkPromotionForm(forms.Form):
    term = forms.ModelChoiceField(queryset=Term.objects.filter(is_deleted=False), help_text="Term whose academic decision is being recorded.")
    from_stream = forms.ModelChoiceField(queryset=Stream.objects.filter(is_deleted=False), label="Current class / stream")
    to_stream = forms.ModelChoiceField(queryset=Stream.objects.filter(is_deleted=False), label="Next class / stream", required=False)
    decision = forms.ChoiceField(choices=[("promoted", "Promote selected learners"), ("repeated", "Repeat selected learners"), ("completed", "Mark selected learners completed"), ("deferred", "Defer decision")])
    apply_to = forms.ChoiceField(choices=[("eligible", "Only students without unresolved missing report marks"), ("all", "All active students in selected stream")], initial="eligible")
    remarks = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned = super().clean()
        term = cleaned.get("term")
        from_stream = cleaned.get("from_stream")
        to_stream = cleaned.get("to_stream")
        if term and from_stream and term.academic_year_id != from_stream.academic_year_id:
            self.add_error("from_stream", "The current stream must belong to the selected term academic year.")
        if cleaned.get("decision") in {"promoted", "repeated"}:
            if not to_stream:
                self.add_error("to_stream", "Choose the destination stream for promoted or repeated learners.")
            elif cleaned.get("decision") == "promoted" and from_stream and to_stream.class_level.level < from_stream.class_level.level:
                self.add_error("to_stream", "Promotion cannot move a learner to a lower class level.")
        return cleaned
