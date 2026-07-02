from django.urls import path, reverse_lazy

from .forms import ActivityOfIntegrationForm, AssessmentPolicyForm, AssessmentTypeForm, CompetencyForm, CompetencyIndicatorForm, CompetencyLevelForm, CurriculumFrameworkForm, CurriculumLearningAreaForm, CurriculumTopicForm, CurriculumValueForm, LearningOutcomeForm, RubricCriterionForm, RubricForm, RubricLevelForm, SkillForm
from .models import ActivityOfIntegration, AssessmentPolicy, AssessmentType, Competency, CompetencyIndicator, CompetencyLevel, CurriculumFramework, CurriculumLearningArea, CurriculumTopic, CurriculumValue, LearningOutcome, Rubric, RubricCriterion, RubricLevel, Skill
from .views import ActivityDetailView, AssessmentCreateView, AssessmentDeleteView, AssessmentDetailView, AssessmentListView, AssessmentUpdateView, AssessmentWorkflowView, CBCEvidenceEntryView, CompetencyEntryView, CurriculumImportTemplateView, CurriculumImportView, CurriculumOverviewView, EvidenceCreateView, LessonPlanCreateView, MarkEntryView, PortfolioItemCreateView, PortfolioItemDetailView, PortfolioItemUpdateView, PortfolioListView, PortfolioWorkflowView, RubricEntryView, SchemeCreateView, SchemeDetailView, SchemeWeekCreateView, SchemeWorkflowView, SetupCreateView, SetupTableView, SetupUpdateView, SubmissionCreateView, TeacherObservationCreateView, TeachingPlanOverviewView

app_name = "assessments"

urlpatterns = [
    path("", AssessmentListView.as_view(), name="list"),
    path("add/", AssessmentCreateView.as_view(), name="add"),
    path("<int:pk>/", AssessmentDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", AssessmentUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", AssessmentDeleteView.as_view(), name="delete"),
    path("<int:pk>/workflow/", AssessmentWorkflowView.as_view(), name="workflow"),
    path("<int:pk>/marks/", MarkEntryView.as_view(), name="marks"),
    path("<int:pk>/competencies/", CompetencyEntryView.as_view(), name="competencies"),
    path("<int:pk>/cbc-evidence/", CBCEvidenceEntryView.as_view(), name="cbc-evidence"),
    path("<int:pk>/rubric/", RubricEntryView.as_view(), name="rubric-entry"),
    path("<int:pk>/submit/", SubmissionCreateView.as_view(), name="submit"),
    path("evidence/add/", EvidenceCreateView.as_view(), name="evidence-add"),
    path("observations/add/", TeacherObservationCreateView.as_view(), name="observation-add"),
    path("portfolio/", PortfolioListView.as_view(), name="portfolio-list"),
    path("portfolio/add/", PortfolioItemCreateView.as_view(), name="portfolio-add"),
    path("portfolio/<int:pk>/", PortfolioItemDetailView.as_view(), name="portfolio-detail"),
    path("portfolio/<int:pk>/edit/", PortfolioItemUpdateView.as_view(), name="portfolio-edit"),
    path("portfolio/<int:pk>/<str:operation>/", PortfolioWorkflowView.as_view(), name="portfolio-workflow"),
    path("planning/", TeachingPlanOverviewView.as_view(), name="teaching-plans"),
    path("planning/schemes/add/", SchemeCreateView.as_view(), name="scheme-add"),
    path("planning/schemes/<int:pk>/", SchemeDetailView.as_view(), name="scheme-detail"),
    path("planning/schemes/<int:pk>/weeks/add/", SchemeWeekCreateView.as_view(), name="scheme-week-add"),
    path("planning/schemes/<int:pk>/workflow/", SchemeWorkflowView.as_view(), name="scheme-workflow"),
    path("planning/lessons/add/", LessonPlanCreateView.as_view(), name="lesson-plan-add"),
    path("curriculum/", CurriculumOverviewView.as_view(), name="curriculum"),
    path("curriculum/import/", CurriculumImportView.as_view(), name="curriculum-import"),
    path("curriculum/import/template.csv", CurriculumImportTemplateView.as_view(), name="curriculum-import-template"),
    path("curriculum/activities/<int:pk>/", ActivityDetailView.as_view(), name="activity-detail"),
]

SETUP = {
    "types": (AssessmentType, AssessmentTypeForm, ("Name", "Category", "Weight", "Active"), ("name", "get_category_display", "weight", "is_active"), "Assessment types"),
    "competency-framework": (Competency, CompetencyForm, ("Competency", "Code", "Order", "Active"), ("name", "code", "display_order", "is_active"), "CBC competencies"),
    "competency-levels": (CompetencyLevel, CompetencyLevelForm, ("Level", "Code", "Value", "Order"), ("name", "code", "numeric_value", "display_order"), "Competency scale"),
    "competency-indicators": (CompetencyIndicator, CompetencyIndicatorForm, ("Indicator", "Competency", "Subject", "Class"), ("statement", "competency", "subject", "class_level"), "Competency indicators"),
    "frameworks": (CurriculumFramework, CurriculumFrameworkForm, ("Framework", "Stage", "Version", "Implementation", "Active"), ("name", "get_stage_display", "version", "implementation_year", "is_active"), "Curriculum frameworks"),
    "curriculum-values": (CurriculumValue, CurriculumValueForm, ("Value", "Order", "Separately assessed"), ("name", "display_order", "is_assessed"), "Curriculum values"),
    "learning-areas": (CurriculumLearningArea, CurriculumLearningAreaForm, ("Learning area", "Subject", "Framework", "Order"), ("name", "subject", "framework", "sequence"), "Curriculum learning areas"),
    "practical-skills": (Skill, SkillForm, ("Skill", "Code", "Order", "Active"), ("name", "code", "display_order", "is_active"), "Practical skills"),
    "topics": (CurriculumTopic, CurriculumTopicForm, ("Topic", "Subject", "Class", "Term", "Sequence"), ("title", "subject", "class_level", "get_term_number_display", "sequence"), "Curriculum topics"),
    "learning-outcomes": (LearningOutcome, LearningOutcomeForm, ("Learning outcome", "Topic", "Code", "Order"), ("statement", "topic", "code", "display_order"), "Learning outcomes"),
    "integration-activities": (ActivityOfIntegration, ActivityOfIntegrationForm, ("Activity", "Topic", "Project", "Published"), ("title", "topic", "is_project", "is_published"), "Activities of Integration"),
    "rubrics": (Rubric, RubricForm, ("Rubric", "Subject", "Activity", "Total marks"), ("name", "subject", "activity", "total_marks"), "Assessment rubrics"),
    "rubric-criteria": (RubricCriterion, RubricCriterionForm, ("Criterion", "Rubric", "Maximum", "Order"), ("name", "rubric", "maximum_score", "display_order"), "Rubric criteria"),
    "rubric-levels": (RubricLevel, RubricLevelForm, ("Level", "Criterion", "Score", "Order"), ("name", "criterion", "score", "display_order"), "Rubric achievement levels"),
    "assessment-policies": (AssessmentPolicy, AssessmentPolicyForm, ("Policy", "Year", "Class", "Ongoing", "Summative", "Frequency"), ("name", "academic_year", "class_level", "ongoing_weight", "summative_weight", "get_summative_frequency_display"), "Assessment policies"),
}
for slug, (model, form, columns, fields, title) in SETUP.items():
    list_name, add_name, edit_name = f"{slug}-list", f"{slug}-add", f"{slug}-edit"
    success = reverse_lazy(f"assessments:{list_name}")
    urlpatterns += [
        path(f"setup/{slug}/", SetupTableView.as_view(model=model, columns=columns, field_paths=fields, page_title=title, create_url_name=f"assessments:{add_name}", edit_url_name=f"assessments:{edit_name}"), name=list_name),
        path(f"setup/{slug}/add/", SetupCreateView.as_view(model=model, form_class=form, success_url=success, extra_context={"page_title": f"Add {model._meta.verbose_name}", "eyebrow": "Assessment setup", "submit_label": "Save record"}), name=add_name),
        path(f"setup/{slug}/<int:pk>/edit/", SetupUpdateView.as_view(model=model, form_class=form, success_url=success, extra_context={"page_title": f"Edit {model._meta.verbose_name}", "eyebrow": "Assessment setup", "submit_label": "Save changes"}), name=edit_name),
    ]
