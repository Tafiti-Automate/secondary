from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from .views import DashboardView, health

admin.site.site_header = "School Academic Administration"
admin.site.site_title = "Academic Management"
admin.site.index_title = "Academic records"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("academics/", include("academics.urls")),
    path("students/", include("students.urls")),
    path("assessments/", include("assessments.urls")),
    path("examinations/", include("exams.urls")),
    path("attendance/", include("attendance.urls")),
    path("timetables/", include("timetables.urls")),
    path("communications/", include("communications.urls")),
    path("reports/", include("reports.urls")),
    path("api/accounts/", include("accounts.api_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-redoc"),
    path("api/academics/", include("academics.api_urls")),
    path("api/students/", include("students.api_urls")),
    path("api/assessments/", include("assessments.api_urls")),
    path("api/exams/", include("exams.api_urls")),
    path("api/attendance/", include("attendance.api_urls")),
    path("api/timetables/", include("timetables.api_urls")),
    path("api/communications/", include("communications.api_urls")),
    path("api/reports/", include("reports.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
