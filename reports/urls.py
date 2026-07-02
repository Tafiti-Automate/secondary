from django.urls import path
from .views import AcademicTranscriptDetailView, AcademicTranscriptListView, AcademicTranscriptPDFView, AnalyticsDashboardView, BulkReportPDFZipView, GenerateReportsView, GenerateTranscriptView, IssueTranscriptView, MissingMarksView, PerformanceExcelView, ReportBatchWorkflowView, ReportCardDetailView, ReportCardListView, ReportCardPDFView, ReportPublishView, ReportReviewView

app_name = "reports"
urlpatterns = [
    path("", ReportCardListView.as_view(), name="list"),
    path("generate/", GenerateReportsView.as_view(), name="generate"),
    path("analytics/", AnalyticsDashboardView.as_view(), name="analytics"),
    path("missing-marks/", MissingMarksView.as_view(), name="missing-marks"),
    path("batch/<str:operation>/", ReportBatchWorkflowView.as_view(), name="batch-workflow"),
    path("export/class-performance.xlsx", PerformanceExcelView.as_view(), name="excel"),
    path("export/report-cards.zip", BulkReportPDFZipView.as_view(), name="pdf-zip"),
    path("transcripts/", AcademicTranscriptListView.as_view(), name="transcript-list"),
    path("transcripts/generate/", GenerateTranscriptView.as_view(), name="transcript-generate"),
    path("transcripts/<int:pk>/", AcademicTranscriptDetailView.as_view(), name="transcript-detail"),
    path("transcripts/<int:pk>/issue/", IssueTranscriptView.as_view(), name="transcript-issue"),
    path("transcripts/<int:pk>/pdf/", AcademicTranscriptPDFView.as_view(), name="transcript-pdf"),
    path("<int:pk>/", ReportCardDetailView.as_view(), name="detail"),
    path("<int:pk>/review/", ReportReviewView.as_view(), name="review"),
    path("<int:pk>/publish/", ReportPublishView.as_view(), name="publish"),
    path("<int:pk>/pdf/", ReportCardPDFView.as_view(), name="pdf"),
]
