from django.contrib import admin
from .models import (
    AcademicTranscript, ReportCard, ReportCompetencyRating, ReportLearningOutcomeRating,
    ReportSkillRating, ReportSubjectResult, ReportValueRating, TranscriptEntry,
)

admin.site.register([
    ReportCard, ReportSubjectResult, ReportCompetencyRating, ReportLearningOutcomeRating,
    ReportSkillRating, ReportValueRating, AcademicTranscript, TranscriptEntry,
])
