from django.urls import path

from .views import BulkPromotionView, EnrollmentCreateView, GuardianCreateView, GuardianListView, GuardianUpdateView, PromotionCreateView, PromotionListView, StudentAcademicHistoryView, StudentCreateView, StudentDeleteView, StudentDetailView, StudentGuardianCreateView, StudentImportTemplateView, StudentImportView, StudentListView, StudentMovementCreateView, StudentMovementListView, StudentUpdateView, SubjectRegistrationCreateView

app_name = "students"

urlpatterns = [
    path("", StudentListView.as_view(), name="list"),
    path("add/", StudentCreateView.as_view(), name="add"),
    path("import/", StudentImportView.as_view(), name="import"),
    path("import/template.csv", StudentImportTemplateView.as_view(), name="import-template"),
    path("<int:pk>/", StudentDetailView.as_view(), name="detail"),
    path("<int:pk>/academic-history/", StudentAcademicHistoryView.as_view(), name="academic-history"),
    path("<int:pk>/edit/", StudentUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", StudentDeleteView.as_view(), name="delete"),
    path("guardians/", GuardianListView.as_view(), name="guardians"),
    path("guardians/add/", GuardianCreateView.as_view(), name="guardian-add"),
    path("guardians/<int:pk>/edit/", GuardianUpdateView.as_view(), name="guardian-edit"),
    path("guardian-links/add/", StudentGuardianCreateView.as_view(), name="guardian-link-add"),
    path("enrollments/add/", EnrollmentCreateView.as_view(), name="enrollment-add"),
    path("subject-registrations/add/", SubjectRegistrationCreateView.as_view(), name="subject-registration-add"),
    path("movements/", StudentMovementListView.as_view(), name="movements"),
    path("movements/add/", StudentMovementCreateView.as_view(), name="movement-add"),
    path("promotions/", PromotionListView.as_view(), name="promotions"),
    path("promotions/add/", PromotionCreateView.as_view(), name="promotion-add"),
    path("promotions/bulk/", BulkPromotionView.as_view(), name="bulk-promotion"),
]
