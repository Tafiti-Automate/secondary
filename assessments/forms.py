from django import forms

from config.forms import StyledModelForm
from .models import (
    ActivityOfIntegration, Assessment, AssessmentEvidence, AssessmentPolicy,
    AssessmentSubmission, AssessmentType, Competency, CompetencyIndicator,
    CompetencyLevel, CurriculumFramework, CurriculumLearningArea, CurriculumTopic,
    CurriculumValue, LearningOutcome, LessonPlan, Rubric, RubricCriterion, RubricLevel,
    SchemeOfWork, SchemeWeek, Skill,
)


class CompetencyForm(StyledModelForm):
    class Meta:
        model = Competency
        fields = ("name", "code", "description", "display_order", "is_active")


class CompetencyLevelForm(StyledModelForm):
    class Meta:
        model = CompetencyLevel
        fields = ("name", "code", "numeric_value", "description", "colour", "display_order")


class CompetencyIndicatorForm(StyledModelForm):
    class Meta:
        model = CompetencyIndicator
        fields = ("competency", "subject", "class_level", "statement", "display_order")


class AssessmentTypeForm(StyledModelForm):
    class Meta:
        model = AssessmentType
        fields = ("name", "code", "category", "weight", "is_active")


class AssessmentForm(StyledModelForm):
    class Meta:
        model = Assessment
        fields = ("title", "assessment_type", "term", "subject", "stream", "topic", "activity_of_integration", "learning_outcomes", "rubric", "assessment_period", "evidence_method", "is_summative", "assigned_date", "due_date", "instructions", "attachment", "max_score", "status")


class SubmissionForm(StyledModelForm):
    class Meta:
        model = AssessmentSubmission
        fields = ("response_text", "attachment")


class CurriculumFrameworkForm(StyledModelForm):
    class Meta:
        model = CurriculumFramework
        fields = ("name", "stage", "version", "implementation_year", "authority", "description", "is_active")


class CurriculumValueForm(StyledModelForm):
    class Meta:
        model = CurriculumValue
        fields = ("name", "description", "display_order", "is_assessed")


class CurriculumLearningAreaForm(StyledModelForm):
    class Meta:
        model = CurriculumLearningArea
        fields = ("framework", "subject", "code", "name", "description", "sequence")


class SkillForm(StyledModelForm):
    class Meta:
        model = Skill
        fields = ("name", "code", "description", "display_order", "is_active")


class CurriculumTopicForm(StyledModelForm):
    class Meta:
        model = CurriculumTopic
        fields = ("framework", "subject", "class_level", "learning_area", "term_number", "code", "title", "description", "suggested_periods", "sequence")


class LearningOutcomeForm(StyledModelForm):
    class Meta:
        model = LearningOutcome
        fields = (
            "topic", "code", "statement", "assessment_criteria", "suggested_activities",
            "required_evidence", "generic_skills", "values", "display_order",
        )


class ActivityOfIntegrationForm(StyledModelForm):
    class Meta:
        model = ActivityOfIntegration
        fields = ("topic", "title", "scenario", "task", "expected_product", "teacher_guidance", "suggested_duration_minutes", "is_project", "is_published")


class RubricForm(StyledModelForm):
    class Meta:
        model = Rubric
        fields = ("name", "activity", "subject", "description", "total_marks")


class RubricCriterionForm(StyledModelForm):
    class Meta:
        model = RubricCriterion
        fields = ("rubric", "name", "description", "maximum_score", "display_order")


class RubricLevelForm(StyledModelForm):
    class Meta:
        model = RubricLevel
        fields = ("criterion", "name", "descriptor", "score", "display_order")


class AssessmentPolicyForm(StyledModelForm):
    class Meta:
        model = AssessmentPolicy
        fields = ("name", "academic_year", "class_level", "curriculum_stage", "purpose", "ongoing_weight", "summative_weight", "summative_frequency", "show_class_position", "requires_complete_marks", "notes", "is_active")


class AssessmentEvidenceForm(StyledModelForm):
    class Meta:
        model = AssessmentEvidence
        fields = ("assessment", "student", "method", "note", "attachment")


class SchemeOfWorkForm(StyledModelForm):
    class Meta:
        model = SchemeOfWork
        fields = ("allocation", "title", "status")


class SchemeWeekForm(StyledModelForm):
    class Meta:
        model = SchemeWeek
        fields = (
            "week_number", "sequence", "start_date", "end_date", "topic", "learning_outcomes",
            "competencies", "planned_periods", "teacher_activities", "learner_activities",
            "resources_required", "assessment_methods", "required_evidence", "completed",
            "completion_notes",
        )


class LessonPlanForm(StyledModelForm):
    class Meta:
        model = LessonPlan
        fields = (
            "allocation", "scheme_week", "title", "lesson_date", "start_time", "duration_minutes",
            "topic", "objectives", "learning_outcomes", "competencies", "teaching_activities",
            "learner_activities", "assessment_method", "teaching_resources", "differentiation",
            "reflection", "status",
        )


class CurriculumImportForm(forms.Form):
    framework = forms.ModelChoiceField(queryset=CurriculumFramework.objects.filter(is_deleted=False, is_active=True))
    csv_file = forms.FileField(help_text="UTF-8 CSV using the curriculum import template; maximum 5 MB.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_csv_file(self):
        upload = self.cleaned_data["csv_file"]
        if upload.size > 5 * 1024 * 1024 or not upload.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a CSV file no larger than 5 MB.")
        return upload
