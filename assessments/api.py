from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError as APIValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from academics.models import SubjectAllocation

from config.mixins import ACADEMIC_MANAGERS
from config.permissions import IsReadOnlyOrAcademicManager, IsReadOnlyOrAcademicStaff
from .models import (
    ActivityOfIntegration, Assessment, AssessmentEvidence, AssessmentPolicy, AssessmentResult,
    AssessmentReview, AssessmentSubmission, AssessmentType, Competency, CompetencyAssessment,
    CompetencyIndicator, CompetencyLevel, CurriculumFramework, CurriculumLearningArea,
    CurriculumTopic, CurriculumValue, LearnerSkillRating, LearnerValueRating, LearningOutcome,
    LearningOutcomeAssessment, LessonPlan, PortfolioItem, Rubric, RubricCriterion, RubricLevel,
    RubricRating, SchemeOfWork, SchemeWeek, Skill, TeacherObservation,
)
from .serializers import (
    ActivityOfIntegrationSerializer, AssessmentEvidenceSerializer, AssessmentPolicySerializer,
    AssessmentResultSerializer, AssessmentReviewSerializer, AssessmentSerializer,
    AssessmentSubmissionSerializer, AssessmentTypeSerializer, CompetencyAssessmentSerializer,
    CompetencyIndicatorSerializer, CompetencyLevelSerializer, CompetencySerializer,
    CurriculumFrameworkSerializer, CurriculumLearningAreaSerializer, CurriculumTopicSerializer,
    CurriculumValueSerializer, LearnerSkillRatingSerializer, LearnerValueRatingSerializer,
    LearningOutcomeAssessmentSerializer, LearningOutcomeSerializer, LessonPlanSerializer,
    PortfolioItemSerializer, RubricCriterionSerializer, RubricLevelSerializer,
    RubricRatingSerializer, RubricSerializer, SchemeOfWorkSerializer, SchemeWeekSerializer,
    SkillSerializer, TeacherObservationSerializer,
)


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsReadOnlyOrAcademicStaff]

    def get_queryset(self):
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.soft_delete()


def viewset_for(model, serializer):
    return type(f"{model.__name__}ViewSet", (BaseViewSet,), {"queryset": model.objects.all(), "serializer_class": serializer})


CompetencyViewSet = viewset_for(Competency, CompetencySerializer)
CompetencyLevelViewSet = viewset_for(CompetencyLevel, CompetencyLevelSerializer)
CompetencyIndicatorViewSet = viewset_for(CompetencyIndicator, CompetencyIndicatorSerializer)
AssessmentTypeViewSet = viewset_for(AssessmentType, AssessmentTypeSerializer)
for setup_viewset in (CompetencyViewSet, CompetencyLevelViewSet, CompetencyIndicatorViewSet, AssessmentTypeViewSet):
    setup_viewset.permission_classes = [IsReadOnlyOrAcademicManager]

CurriculumFrameworkViewSet = viewset_for(CurriculumFramework, CurriculumFrameworkSerializer)
CurriculumValueViewSet = viewset_for(CurriculumValue, CurriculumValueSerializer)
CurriculumLearningAreaViewSet = viewset_for(CurriculumLearningArea, CurriculumLearningAreaSerializer)
CurriculumTopicViewSet = viewset_for(CurriculumTopic, CurriculumTopicSerializer)
LearningOutcomeViewSet = viewset_for(LearningOutcome, LearningOutcomeSerializer)
ActivityOfIntegrationViewSet = viewset_for(ActivityOfIntegration, ActivityOfIntegrationSerializer)
RubricViewSet = viewset_for(Rubric, RubricSerializer)
RubricCriterionViewSet = viewset_for(RubricCriterion, RubricCriterionSerializer)
RubricLevelViewSet = viewset_for(RubricLevel, RubricLevelSerializer)
RubricRatingViewSet = viewset_for(RubricRating, RubricRatingSerializer)
AssessmentPolicyViewSet = viewset_for(AssessmentPolicy, AssessmentPolicySerializer)
SkillViewSet = viewset_for(Skill, SkillSerializer)
for curriculum_viewset in (CurriculumFrameworkViewSet, CurriculumValueViewSet, CurriculumLearningAreaViewSet, CurriculumTopicViewSet, LearningOutcomeViewSet, ActivityOfIntegrationViewSet, RubricViewSet, RubricCriterionViewSet, RubricLevelViewSet, AssessmentPolicyViewSet, SkillViewSet):
    curriculum_viewset.permission_classes = [IsReadOnlyOrAcademicManager]


class TeacherPlanningViewSet(BaseViewSet):
    allocation_path = "allocation"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role in ACADEMIC_MANAGERS:
            return qs
        if user.role == "teacher":
            return qs.filter(**{f"{self.allocation_path}__teacher": user})
        return qs.none()


class SchemeOfWorkViewSet(TeacherPlanningViewSet):
    queryset = SchemeOfWork.objects.all()
    serializer_class = SchemeOfWorkSerializer

    def perform_create(self, serializer):
        if self.request.user.role == "teacher" and serializer.validated_data["allocation"].teacher_id != self.request.user.pk:
            raise PermissionDenied("You may only prepare schemes for your own subject allocations.")
        serializer.save(prepared_by=self.request.user)

    def perform_update(self, serializer):
        requested_status = serializer.validated_data.get("status", serializer.instance.status)
        if requested_status in {"approved", "changes_requested"}:
            allocation = serializer.instance.allocation
            hod_id = allocation.subject.department.head_id if allocation.subject.department_id else None
            if not (self.request.user.is_superuser or self.request.user.role in ACADEMIC_MANAGERS or self.request.user.pk == hod_id):
                raise PermissionDenied("Only the subject HOD or academic management may review a scheme.")
            serializer.save(reviewed_by=self.request.user, reviewed_at=timezone.now())
            return
        serializer.save()


class SchemeWeekViewSet(TeacherPlanningViewSet):
    queryset = SchemeWeek.objects.all()
    serializer_class = SchemeWeekSerializer
    allocation_path = "scheme__allocation"

    def perform_create(self, serializer):
        if self.request.user.role == "teacher" and serializer.validated_data["scheme"].allocation.teacher_id != self.request.user.pk:
            raise PermissionDenied("You may only edit your own scheme of work.")
        serializer.save()


class LessonPlanViewSet(TeacherPlanningViewSet):
    queryset = LessonPlan.objects.all()
    serializer_class = LessonPlanSerializer

    def perform_create(self, serializer):
        if self.request.user.role == "teacher" and serializer.validated_data["allocation"].teacher_id != self.request.user.pk:
            raise PermissionDenied("You may only prepare lesson plans for your own subject allocations.")
        serializer.save(prepared_by=self.request.user)

    def perform_update(self, serializer):
        requested_status = serializer.validated_data.get("status", serializer.instance.status)
        if requested_status in {"approved", "changes_requested"}:
            if not (self.request.user.is_superuser or self.request.user.role in ACADEMIC_MANAGERS):
                raise PermissionDenied("Academic management review is required.")
            serializer.save(reviewed_by=self.request.user, reviewed_at=timezone.now())
            return
        serializer.save()


class LearnerEvidenceViewSet(BaseViewSet):
    owner_field = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role in ACADEMIC_MANAGERS:
            return qs
        if user.role == "teacher":
            return qs.filter(
                Q(student__stream__class_teacher=user)
                | Q(student__stream__subject_allocations__teacher=user, student__stream__subject_allocations__is_deleted=False)
            ).distinct()
        if user.role == "student":
            return qs.filter(student__user=user)
        if user.role == "parent":
            return qs.filter(Q(student__parent=user) | Q(student__guardian_links__guardian__user=user)).distinct()
        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        student = serializer.validated_data["student"]
        if user.role == "teacher":
            term = serializer.validated_data.get("term")
            subject = serializer.validated_data.get("subject")
            assessment = serializer.validated_data.get("assessment")
            term = term or (assessment.term if assessment else None)
            subject = subject or (assessment.subject if assessment else None)
            allocation = SubjectAllocation.objects.filter(
                teacher=user,
                stream=student.stream,
                term=term,
                is_deleted=False,
                is_active=True,
            )
            if subject:
                allocation = allocation.filter(subject=subject)
            if not (student.stream and (student.stream.class_teacher_id == user.pk or allocation.exists())):
                raise PermissionDenied("You may only assess learners assigned to your class or subject.")
        values = {self.owner_field: self.request.user} if self.owner_field else {}
        serializer.save(**values)


class LearningOutcomeAssessmentViewSet(LearnerEvidenceViewSet):
    queryset = LearningOutcomeAssessment.objects.all()
    serializer_class = LearningOutcomeAssessmentSerializer
    owner_field = "assessed_by"


class LearnerSkillRatingViewSet(LearnerEvidenceViewSet):
    queryset = LearnerSkillRating.objects.all()
    serializer_class = LearnerSkillRatingSerializer
    owner_field = "assessed_by"


class LearnerValueRatingViewSet(LearnerEvidenceViewSet):
    queryset = LearnerValueRating.objects.all()
    serializer_class = LearnerValueRatingSerializer
    owner_field = "assessed_by"


class TeacherObservationViewSet(LearnerEvidenceViewSet):
    queryset = TeacherObservation.objects.all()
    serializer_class = TeacherObservationSerializer
    owner_field = "observed_by"


class PortfolioItemViewSet(LearnerEvidenceViewSet):
    queryset = PortfolioItem.objects.all()
    serializer_class = PortfolioItemSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == "student":
            if not hasattr(user, "student_profile"):
                raise PermissionDenied("A linked student profile is required.")
            serializer.save(student=user.student_profile, uploaded_by=user, status="submitted")
        elif user.role == "teacher":
            student = serializer.validated_data["student"]
            term = serializer.validated_data["term"]
            subject = serializer.validated_data.get("subject")
            allocation = SubjectAllocation.objects.filter(
                teacher=user, stream=student.stream, term=term, is_deleted=False, is_active=True,
            )
            if subject:
                allocation = allocation.filter(subject=subject)
            if not (student.stream and (student.stream.class_teacher_id == user.pk or allocation.exists())):
                raise PermissionDenied("You may only add portfolio evidence for an assigned learner.")
            serializer.save(uploaded_by=user)
        elif user.is_superuser or user.role in ACADEMIC_MANAGERS:
            serializer.save(uploaded_by=user)
        else:
            raise PermissionDenied("Only learners and academic staff may add portfolio evidence.")


class AssessmentReviewViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AssessmentReview.objects.filter(is_deleted=False)
    serializer_class = AssessmentReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_superuser or user.role in ACADEMIC_MANAGERS:
            return qs
        if user.role == "teacher":
            return qs.filter(Q(assessment__created_by=user) | Q(assessment__subject__department__head=user)).distinct()
        return qs.none()


class AssessmentEvidenceViewSet(BaseViewSet):
    queryset = AssessmentEvidence.objects.all()
    serializer_class = AssessmentEvidenceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role in ACADEMIC_MANAGERS:
            return qs
        if user.role == "teacher":
            allocation = SubjectAllocation.objects.filter(
                teacher=user,
                subject_id=OuterRef("assessment__subject_id"),
                stream_id=OuterRef("assessment__stream_id"),
                term_id=OuterRef("assessment__term_id"),
                is_deleted=False,
                is_active=True,
            )
            return qs.annotate(is_allocated=Exists(allocation)).filter(is_allocated=True)
        if user.role == "student":
            return qs.filter(student__user=user)
        if user.role == "parent":
            return qs.filter(Q(student__parent=user) | Q(student__guardian_links__guardian__user=user)).distinct()
        return qs.none()

    def perform_create(self, serializer):
        assessment = serializer.validated_data["assessment"]
        if assessment.is_workflow_locked:
            raise APIValidationError("DOS-approved assessment evidence is read-only.")
        if self.request.user.role == "teacher" and not SubjectAllocation.objects.filter(
            teacher=self.request.user,
            subject=assessment.subject,
            stream=assessment.stream,
            term=assessment.term,
            is_deleted=False,
            is_active=True,
        ).exists():
            raise PermissionDenied("You may only capture evidence for your assigned subject and stream.")
        serializer.save(captured_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.assessment.is_workflow_locked:
            raise APIValidationError("DOS-approved assessment evidence is read-only.")
        serializer.save(captured_by=self.request.user)


class AssessmentViewSet(BaseViewSet):
    queryset = Assessment.objects.all()
    serializer_class = AssessmentSerializer
    search_fields = ["title", "subject__name", "stream__name"]

    def get_queryset(self):
        qs = super().get_queryset().select_related("term", "subject", "stream", "assessment_type")
        user = self.request.user
        if user.role == "teacher" and not user.is_superuser:
            allocation = SubjectAllocation.objects.filter(teacher=user, subject_id=OuterRef("subject_id"), stream_id=OuterRef("stream_id"), term_id=OuterRef("term_id"), is_deleted=False, is_active=True)
            return qs.annotate(is_allocated=Exists(allocation)).filter(is_allocated=True)
        if user.role == "student":
            return qs.filter(stream__students__user=user, status="published")
        if user.role == "parent":
            return qs.filter(stream__students__guardian_links__guardian__user=user, status="published").distinct()
        return qs

    def perform_create(self, serializer):
        status_value = serializer.validated_data.get("status", "draft")
        if self.request.user.role == "teacher":
            is_allocated = SubjectAllocation.objects.filter(
                teacher=self.request.user,
                subject=serializer.validated_data["subject"],
                stream=serializer.validated_data["stream"],
                term=serializer.validated_data["term"],
                is_deleted=False,
                is_active=True,
            ).exists()
            if not is_allocated:
                raise PermissionDenied("You may only create assessments for your assigned subject and stream.")
        if self.request.user.role == "teacher" and status_value not in {"draft", "published", "closed"}:
            status_value = "draft"
        serializer.save(created_by=self.request.user, status=status_value)

    def perform_update(self, serializer):
        if serializer.instance.is_workflow_locked:
            raise APIValidationError("DOS-approved assessments are read-only. Reopen the workflow before editing.")
        status_value = serializer.validated_data.get("status", serializer.instance.status)
        if self.request.user.role == "teacher" and status_value == "moderated":
            status_value = serializer.instance.status
        serializer.save(status=status_value)

    @action(detail=True, methods=["post"], url_path="workflow")
    def workflow(self, request, pk=None):
        assessment = self.get_object()
        operation = request.data.get("operation", "")
        try:
            assessment.transition(operation, request.user, request.data.get("comment", ""))
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(assessment).data)


class AssessmentResultViewSet(BaseViewSet):
    queryset = AssessmentResult.objects.all()
    serializer_class = AssessmentResultSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == "teacher":
            allocation = SubjectAllocation.objects.filter(teacher=self.request.user, subject_id=OuterRef("assessment__subject_id"), stream_id=OuterRef("assessment__stream_id"), term_id=OuterRef("assessment__term_id"), is_deleted=False, is_active=True)
            return qs.annotate(is_allocated=Exists(allocation)).filter(is_allocated=True)
        if self.request.user.role == "student":
            return qs.filter(student__user=self.request.user, assessment__status__in=("published", "closed", "moderated"))
        if self.request.user.role == "parent":
            return qs.filter(student__guardian_links__guardian__user=self.request.user, assessment__status__in=("published", "closed", "moderated")).distinct()
        return qs

    def perform_create(self, serializer):
        assessment = serializer.validated_data["assessment"]
        if assessment.is_workflow_locked:
            raise APIValidationError("DOS-approved assessment results are read-only.")
        if assessment.status in {"closed", "moderated"} and self.request.user.role not in {"super_admin", "headteacher", "director_of_studies"} and not self.request.user.is_superuser:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("This assessment is closed for mark entry.")
        serializer.save(marked_by=self.request.user)

    def perform_update(self, serializer):
        assessment = serializer.instance.assessment
        if assessment.is_workflow_locked:
            raise APIValidationError("DOS-approved assessment results are read-only.")
        if assessment.status in {"closed", "moderated"} and self.request.user.role not in {"super_admin", "headteacher", "director_of_studies"} and not self.request.user.is_superuser:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("This assessment is closed for mark entry.")
        serializer.save(marked_by=self.request.user)


class CompetencyAssessmentViewSet(BaseViewSet):
    queryset = CompetencyAssessment.objects.all()
    serializer_class = CompetencyAssessmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "teacher":
            allocation = SubjectAllocation.objects.filter(teacher=user, subject_id=OuterRef("assessment__subject_id"), stream_id=OuterRef("assessment__stream_id"), term_id=OuterRef("assessment__term_id"), is_deleted=False, is_active=True)
            return qs.annotate(is_allocated=Exists(allocation)).filter(is_allocated=True)
        if user.role == "student":
            return qs.filter(student__user=user, assessment__status__in=("published", "closed", "moderated"))
        if user.role == "parent":
            return qs.filter(student__guardian_links__guardian__user=user, assessment__status__in=("published", "closed", "moderated")).distinct()
        return qs

    def perform_create(self, serializer):
        if serializer.validated_data["assessment"].is_workflow_locked:
            raise APIValidationError("DOS-approved competency ratings are read-only.")
        serializer.save(assessed_by=self.request.user)


class SubmissionViewSet(BaseViewSet):
    queryset = AssessmentSubmission.objects.all()
    serializer_class = AssessmentSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == "student":
            return qs.filter(student__user=self.request.user)
        if self.request.user.role == "teacher":
            return qs.filter(assessment__created_by=self.request.user)
        if self.request.user.role in {"super_admin", "headteacher", "director_of_studies"} or self.request.user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        if self.request.user.role != "student" or not hasattr(self.request.user, "student_profile"):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only linked student accounts can submit work.")
        serializer.save(student=self.request.user.student_profile)
