from django.urls import path, reverse_lazy

from .forms import ExamSessionForm, GradeBoundaryForm, GradeScaleForm
from .models import ExamSession, GradeBoundary, GradeScale
from .views import ExamMarkEntryView, ExamModerationView, ExaminationCreateView, ExaminationDeleteView, ExaminationDetailView, ExaminationListView, ExaminationTransitionView, ExaminationUpdateView, SetupCreateView, SetupTableView, SetupUpdateView, UNEBCACreateView, UNEBCAImportTemplateView, UNEBCAImportView, UNEBCAListView, UNEBCAWorkflowView, UNEBCandidateCreateView, UNEBCandidateDetailView, UNEBCandidateListView, UNEBCandidateSubjectCreateView, UNEBExportView, UNEBHubView

app_name = "exams"

urlpatterns = [
    path("", ExaminationListView.as_view(), name="list"),
    path("add/", ExaminationCreateView.as_view(), name="add"),
    path("<int:pk>/", ExaminationDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", ExaminationUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", ExaminationDeleteView.as_view(), name="delete"),
    path("<int:pk>/marks/", ExamMarkEntryView.as_view(), name="marks"),
    path("<int:pk>/moderate/", ExamModerationView.as_view(), name="moderate"),
    path("<int:pk>/transition/<str:operation>/", ExaminationTransitionView.as_view(), name="transition"),
    path("uneb/", UNEBHubView.as_view(), name="uneb-hub"),
    path("uneb/candidates/", UNEBCandidateListView.as_view(), name="uneb-candidates"),
    path("uneb/candidates/add/", UNEBCandidateCreateView.as_view(), name="uneb-candidate-add"),
    path("uneb/candidates/<int:pk>/", UNEBCandidateDetailView.as_view(), name="uneb-candidate-detail"),
    path("uneb/candidate-subjects/add/", UNEBCandidateSubjectCreateView.as_view(), name="uneb-subject-add"),
    path("uneb/continuous-assessment/", UNEBCAListView.as_view(), name="uneb-ca-list"),
    path("uneb/continuous-assessment/add/", UNEBCACreateView.as_view(), name="uneb-ca-add"),
    path("uneb/continuous-assessment/import/", UNEBCAImportView.as_view(), name="uneb-ca-import"),
    path("uneb/continuous-assessment/import/template.csv", UNEBCAImportTemplateView.as_view(), name="uneb-ca-import-template"),
    path("uneb/continuous-assessment/<str:operation>/", UNEBCAWorkflowView.as_view(), name="uneb-ca-workflow"),
    path("uneb/export/", UNEBExportView.as_view(), name="uneb-export"),
]

SETUP = {
    "sessions": (ExamSession, ExamSessionForm, ("Session", "Term", "Type", "Dates", "Status"), ("name", "term", "get_exam_type_display", "start_date", "get_status_display"), "Examination sessions"),
    "grade-scales": (GradeScale, GradeScaleForm, ("Scale", "Curriculum", "Default"), ("name", "get_curriculum_level_display", "is_default"), "Grading scales"),
    "grade-boundaries": (GradeBoundary, GradeBoundaryForm, ("Grade", "Minimum", "Maximum", "Points", "Descriptor"), ("grade", "minimum_score", "maximum_score", "points", "descriptor"), "Grade boundaries"),
}
for slug, (model, form, columns, fields, title) in SETUP.items():
    list_name, add_name, edit_name = f"{slug}-list", f"{slug}-add", f"{slug}-edit"
    success = reverse_lazy(f"exams:{list_name}")
    urlpatterns += [
        path(f"setup/{slug}/", SetupTableView.as_view(model=model, columns=columns, field_paths=fields, page_title=title, create_url_name=f"exams:{add_name}", edit_url_name=f"exams:{edit_name}"), name=list_name),
        path(f"setup/{slug}/add/", SetupCreateView.as_view(model=model, form_class=form, success_url=success, extra_context={"page_title": f"Add {model._meta.verbose_name}", "eyebrow": "Examination setup", "submit_label": "Save record"}), name=add_name),
        path(f"setup/{slug}/<int:pk>/edit/", SetupUpdateView.as_view(model=model, form_class=form, success_url=success, extra_context={"page_title": f"Edit {model._meta.verbose_name}", "eyebrow": "Examination setup", "submit_label": "Save changes"}), name=edit_name),
    ]
