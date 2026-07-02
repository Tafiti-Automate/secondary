from django.contrib import admin
from .models import (
    ExamSession, Examination, ExaminationResult, GradeBoundary, GradeScale, UNEBCandidate,
    UNEBCandidateSubject, UNEBContinuousAssessment, UNEBExportBatch, UpperAssessmentComponent,
    UpperAssessmentPlan, UpperSubjectResult,
)

admin.site.register([
    GradeScale, GradeBoundary, ExamSession, Examination, ExaminationResult, UNEBCandidate,
    UNEBCandidateSubject, UNEBContinuousAssessment, UNEBExportBatch, UpperAssessmentPlan,
    UpperAssessmentComponent, UpperSubjectResult,
])
