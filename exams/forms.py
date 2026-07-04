from django import forms

from config.forms import DateRangeValidationMixin, StyledModelForm
from .models import (
    ExamSession, Examination, GradeBoundary, GradeScale, UNEBCandidate,
    UNEBCandidateSubject, UNEBContinuousAssessment, UNEBIntegrationAdapter, UpperAssessmentComponent,
    UpperAssessmentPlan,
)


class GradeScaleForm(StyledModelForm):
    class Meta:
        model = GradeScale
        fields = ("name", "curriculum_level", "description", "is_default")


class GradeBoundaryForm(StyledModelForm):
    class Meta:
        model = GradeBoundary
        fields = ("scale", "minimum_score", "maximum_score", "grade", "points", "description", "descriptor")


class ExamSessionForm(DateRangeValidationMixin, StyledModelForm):
    class Meta:
        model = ExamSession
        fields = ("term", "name", "exam_type", "start_date", "end_date", "weight", "status", "grade_scale")


class ExaminationForm(StyledModelForm):
    class Meta:
        model = Examination
        fields = ("title", "session", "term", "subject", "stream", "component", "is_school_summative", "exam_date", "start_time", "duration_minutes", "max_score", "status")


class UpperAssessmentPlanForm(StyledModelForm):
    class Meta:
        model = UpperAssessmentPlan
        fields = ("academic_year", "class_level", "subject", "name", "pass_mark", "grade_scale", "notes")


class UpperAssessmentComponentForm(StyledModelForm):
    class Meta:
        model = UpperAssessmentComponent
        fields = ("name", "component_type", "weight", "maximum_score", "sequence", "is_required", "is_active")


class UNEBCandidateForm(StyledModelForm):
    class Meta:
        model = UNEBCandidate
        fields = ("student", "examination_level", "examination_year", "index_number", "centre_number", "candidate_name", "gender", "status")


class UNEBCandidateSubjectForm(StyledModelForm):
    class Meta:
        model = UNEBCandidateSubject
        fields = ("candidate", "subject", "subject_code", "category", "is_registered")


class UNEBContinuousAssessmentForm(StyledModelForm):
    class Meta:
        model = UNEBContinuousAssessment
        fields = ("candidate_subject", "class_level", "term", "component", "raw_score", "maximum_score", "evidence_reference", "status", "notes")


class UNEBIntegrationAdapterForm(StyledModelForm):
    class Meta:
        model = UNEBIntegrationAdapter
        fields = ("name", "examination_level", "version", "effective_from", "effective_to", "status", "columns", "requirements", "notes")
        widgets = {
            "columns": forms.Textarea(attrs={"rows": 8}),
            "requirements": forms.Textarea(attrs={"rows": 5}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class UNEBCAImportForm(forms.Form):
    examination_level = forms.ChoiceField(choices=UNEBCandidate._meta.get_field("examination_level").choices)
    examination_year = forms.IntegerField(min_value=2024, max_value=2100)
    csv_file = forms.FileField(help_text="UTF-8 CSV using the current UNEB CA register template; maximum 5 MB.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_csv_file(self):
        upload = self.cleaned_data["csv_file"]
        if upload.size > 5 * 1024 * 1024 or not upload.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a CSV file no larger than 5 MB.")
        return upload
