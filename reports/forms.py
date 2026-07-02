from django import forms

from academics.models import Stream, Term
from assessments.models import AssessmentPolicy
from config.forms import StyledModelForm
from students.models import Student
from .models import ReportCard


class ReportCardReviewForm(StyledModelForm):
    class Meta:
        model = ReportCard
        fields = ("teacher_remark", "dos_remark", "headteacher_comment", "promotion_decision")


class ReportGenerationForm(forms.Form):
    term = forms.ModelChoiceField(queryset=Term.objects.filter(is_deleted=False))
    stream = forms.ModelChoiceField(queryset=Stream.objects.filter(is_deleted=False))
    assessment_policy = forms.ModelChoiceField(queryset=AssessmentPolicy.objects.filter(is_deleted=False, is_active=True), help_text="The selected policy controls weights, annual/termly summative rules, and ranking.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned = super().clean()
        term, stream, policy = cleaned.get("term"), cleaned.get("stream"), cleaned.get("assessment_policy")
        if term and stream and term.academic_year_id != stream.academic_year_id:
            raise forms.ValidationError("The term and stream must belong to the same academic year.")
        if policy and term and policy.academic_year_id != term.academic_year_id:
            self.add_error("assessment_policy", "Policy belongs to a different academic year.")
        if policy and stream and policy.class_level_id and policy.class_level_id != stream.class_level_id:
            self.add_error("assessment_policy", "Policy does not apply to the selected class level.")
        return cleaned


class TranscriptGenerationForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.filter(is_deleted=False))
    purpose = forms.CharField(max_length=180, required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
