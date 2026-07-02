from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from academics.models import AcademicYear, ClassLevel, Stream, Subject, Term
from accounts.models import User
from config.models import BaseModel
from students.models import Student


class GradeScale(BaseModel):
    name = models.CharField(max_length=100)
    curriculum_level = models.CharField(max_length=20, choices=[("lower", "Lower Secondary CBC"), ("upper", "Upper Secondary"), ("general", "General")], default="general")
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if self.is_default:
            GradeScale.objects.exclude(pk=self.pk).filter(curriculum_level=self.curriculum_level).update(is_default=False)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class GradeBoundary(BaseModel):
    scale = models.ForeignKey(GradeScale, related_name="boundaries", on_delete=models.CASCADE, null=True, blank=True)
    minimum_score = models.DecimalField(max_digits=5, decimal_places=2)
    maximum_score = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=5)
    points = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=100, blank=True)
    descriptor = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-minimum_score"]

    def clean(self):
        if self.minimum_score > self.maximum_score:
            raise ValidationError({"maximum_score": "Maximum score must be at least the minimum score."})
        overlapping = GradeBoundary.objects.filter(scale=self.scale, is_deleted=False, minimum_score__lte=self.maximum_score, maximum_score__gte=self.minimum_score).exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError("This range overlaps an existing grade boundary.")

    def __str__(self):
        return f"{self.grade} · {self.minimum_score}–{self.maximum_score}"


class ExamSession(BaseModel):
    term = models.ForeignKey(Term, related_name="exam_sessions", on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    exam_type = models.CharField(max_length=30, choices=[
        ("bot", "Beginning of term"), ("mid", "Mid term"), ("coursework", "Coursework"),
        ("practical", "Practical"), ("project", "Project"), ("holiday", "Holiday test"),
        ("end", "End of term"), ("annual", "Annual school summative"), ("mock", "Mock examination"),
        ("external", "External/end-of-cycle examination"),
    ], default="end")
    start_date = models.DateField()
    end_date = models.DateField()
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=100, validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_required = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("entry", "Mark entry"), ("moderation", "Moderation"), ("approved", "Approved"), ("published", "Published"), ("locked", "Locked")], default="draft")
    grade_scale = models.ForeignKey(GradeScale, related_name="exam_sessions", on_delete=models.PROTECT, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot precede start date."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} · {self.term}"


class UpperAssessmentPlan(BaseModel):
    academic_year = models.ForeignKey(AcademicYear, related_name="upper_assessment_plans", on_delete=models.PROTECT)
    class_level = models.ForeignKey(ClassLevel, related_name="upper_assessment_plans", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="upper_assessment_plans", on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    pass_mark = models.DecimalField(max_digits=5, decimal_places=2, default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    grade_scale = models.ForeignKey(GradeScale, related_name="upper_assessment_plans", on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("approved", "Approved"), ("locked", "Locked")], default="draft")
    approved_by = models.ForeignKey(User, related_name="approved_upper_assessment_plans", on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-academic_year__start_date", "class_level__level", "subject__name"]
        constraints = [
            models.UniqueConstraint(fields=["academic_year", "class_level", "subject"], condition=Q(is_deleted=False), name="unique_active_upper_assessment_plan")
        ]

    @property
    def configured_weight(self):
        return sum((component.weight for component in self.components.filter(is_deleted=False, is_active=True)), Decimal("0"))

    def clean(self):
        if self.class_level_id and self.class_level.curriculum != "upper":
            raise ValidationError({"class_level": "Upper-secondary assessment plans can only be assigned to S5 or S6."})
        if self.subject_id and self.subject.curriculum_level not in {"upper", "both"}:
            raise ValidationError({"subject": "The selected subject is not available for upper secondary."})
        if self.status in {"approved", "locked"}:
            if not self.pk:
                raise ValidationError("Create the assessment plan as a draft, add components, then approve it.")
            if self.configured_weight != Decimal("100"):
                raise ValidationError("Active upper-secondary assessment components must total exactly 100% before approval.")
            if not self.approved_by_id:
                raise ValidationError({"approved_by": "An approved assessment plan requires an approving officer."})

    def save(self, *args, **kwargs):
        if self.status in {"approved", "locked"} and self.approved_by_id and not self.approved_at:
            self.approved_at = timezone.now()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} · {self.class_level} · {self.subject.name}"


class UpperAssessmentComponent(BaseModel):
    COMPONENT_CHOICES = [
        ("bot", "Beginning of term test"), ("midterm", "Midterm"), ("coursework", "Coursework"),
        ("practical", "Practical"), ("project", "Project"), ("research", "Research"),
        ("laboratory", "Laboratory records"), ("fieldwork", "Field work"),
        ("exam", "End of term examination"), ("holiday", "Holiday test"),
    ]
    plan = models.ForeignKey(UpperAssessmentPlan, related_name="components", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    component_type = models.CharField(max_length=24, choices=COMPONENT_CHOICES)
    weight = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    maximum_score = models.DecimalField(max_digits=7, decimal_places=2, default=100, validators=[MinValueValidator(Decimal("0.01"))])
    sequence = models.PositiveSmallIntegerField(default=1)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plan", "sequence", "name"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "name"], condition=Q(is_deleted=False), name="unique_active_upper_plan_component_name")
        ]

    def clean(self):
        if self.plan_id and self.plan.status == "locked":
            raise ValidationError("Components of a locked assessment plan cannot be changed.")
        if self.plan_id and self.is_active:
            other_weight = sum(
                (component.weight for component in self.plan.components.filter(is_deleted=False, is_active=True).exclude(pk=self.pk)),
                Decimal("0"),
            )
            if other_weight + self.weight > Decimal("100"):
                raise ValidationError({"weight": "Active component weights cannot exceed 100%."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.plan} · {self.name} ({self.weight}%)"


class Examination(BaseModel):
    STATUS_CHOICES = [("draft", "Draft"), ("entry", "Mark entry"), ("submitted", "Submitted"), ("moderated", "Moderated"), ("approved", "Approved"), ("published", "Published"), ("locked", "Locked")]
    title = models.CharField(max_length=200)
    session = models.ForeignKey(ExamSession, related_name="examinations", on_delete=models.PROTECT, null=True, blank=True)
    term = models.ForeignKey(Term, related_name="examinations", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="examinations", on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, related_name="examinations", on_delete=models.PROTECT, null=True)
    exam_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=120)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(User, related_name="created_examinations", on_delete=models.SET_NULL, null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(User, related_name="moderated_examinations", on_delete=models.SET_NULL, null=True, blank=True)
    moderated_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, related_name="approved_examinations", on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    published = models.BooleanField(default=False)
    locked = models.BooleanField(default=False)
    is_school_summative = models.BooleanField(default=True)
    component = models.ForeignKey(UpperAssessmentComponent, related_name="examinations", on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        ordering = ["-exam_date", "subject__name"]

    def clean(self):
        if self.stream_id and self.term_id and self.stream.academic_year_id != self.term.academic_year_id:
            raise ValidationError("The stream and term must belong to the same academic year.")
        if self.session_id and self.term_id and self.session.term_id != self.term_id:
            raise ValidationError("The examination session and examination must belong to the same term.")
        if self.stream_id and self.stream.class_level.curriculum == "upper" and self.is_school_summative and self.session_id and self.session.exam_type != "annual" and not self.component_id:
            raise ValidationError({"session": "Advanced Secondary permits one school-based summative assessment annually; use an annual session."})
        if self.component_id:
            plan = self.component.plan
            if self.term_id and plan.academic_year_id != self.term.academic_year_id:
                raise ValidationError({"component": "Component plan belongs to a different academic year."})
            if self.stream_id and plan.class_level_id != self.stream.class_level_id:
                raise ValidationError({"component": "Component plan belongs to a different class level."})
            if self.subject_id and plan.subject_id != self.subject_id:
                raise ValidationError({"component": "Component plan belongs to a different subject."})

    def save(self, *args, **kwargs):
        if self.component_id:
            self.max_score = self.component.maximum_score
        self.full_clean()
        self.published = self.status in {"published", "locked"}
        self.locked = self.status == "locked"
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"published", "locked"}
        return super().save(*args, **kwargs)

    def transition(self, status, user):
        transitions = {
            "submit": "submitted", "moderate": "moderated", "approve": "approved",
            "publish": "published", "lock": "locked", "reopen": "entry",
        }
        target = transitions[status]
        now = timezone.now()
        if status == "submit":
            self.submitted_at = now
        elif status == "moderate":
            self.moderated_by, self.moderated_at = user, now
        elif status == "approve":
            self.approved_by, self.approved_at = user, now
        self.status = target
        self.save()

    def __str__(self):
        return self.title


class ExaminationResult(BaseModel):
    examination = models.ForeignKey(Examination, related_name="results", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, related_name="exam_results", on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
    grade = models.CharField(max_length=5, blank=True)
    points = models.PositiveSmallIntegerField(null=True, blank=True)
    descriptor = models.CharField(max_length=120, blank=True)
    teacher_remark = models.CharField(max_length=180, blank=True)
    marked_by = models.ForeignKey(User, related_name="marked_exam_results", on_delete=models.SET_NULL, null=True, blank=True)
    moderated_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    moderated_by = models.ForeignKey(User, related_name="moderated_exam_results", on_delete=models.SET_NULL, null=True, blank=True)
    approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["student__first_name", "student__last_name"]
        constraints = [models.UniqueConstraint(fields=["examination", "student"], condition=Q(is_deleted=False), name="unique_active_examination_result")]

    @property
    def effective_score(self):
        return self.moderated_score if self.moderated_score is not None else self.score

    @property
    def percentage(self):
        if not self.examination.max_score:
            return Decimal("0")
        return (self.effective_score / self.examination.max_score * 100).quantize(Decimal("0.01"))

    def clean(self):
        if self.examination_id and self.examination.status == "locked":
            raise ValidationError("Locked examination results are read-only.")
        score = self.effective_score
        if self.examination_id and score is not None and score > self.examination.max_score:
            raise ValidationError({"score": f"Score cannot exceed {self.examination.max_score}."})
        if self.examination_id and self.student_id and self.examination.stream_id and self.student.stream_id != self.examination.stream_id:
            raise ValidationError({"student": "Student is not enrolled in this examination's stream."})

    def assign_grade(self):
        scale = self.examination.session.grade_scale if self.examination.session_id else None
        boundaries = GradeBoundary.objects.filter(is_deleted=False, minimum_score__lte=self.percentage, maximum_score__gte=self.percentage)
        if scale:
            boundaries = boundaries.filter(scale=scale)
        else:
            boundaries = boundaries.filter(scale__isnull=True)
        boundary = boundaries.order_by("-minimum_score").first()
        if boundary:
            self.grade, self.points = boundary.grade, boundary.points
            self.descriptor = boundary.descriptor or boundary.description

    def save(self, *args, **kwargs):
        self.full_clean()
        self.assign_grade()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.effective_score}"


class UpperSubjectResult(BaseModel):
    plan = models.ForeignKey(UpperAssessmentPlan, related_name="processed_results", on_delete=models.PROTECT)
    student = models.ForeignKey(Student, related_name="upper_subject_results", on_delete=models.CASCADE)
    term = models.ForeignKey(Term, related_name="upper_subject_results", on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, related_name="upper_subject_results", on_delete=models.PROTECT)
    component_breakdown = models.JSONField(default=dict, blank=True)
    total_score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    average_score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    grade = models.CharField(max_length=5, blank=True)
    points = models.PositiveSmallIntegerField(null=True, blank=True)
    remark = models.CharField(max_length=120, blank=True)
    passed = models.BooleanField(default=False)
    class_position = models.PositiveIntegerField(null=True, blank=True)
    subject_position = models.PositiveIntegerField(null=True, blank=True)
    has_missing_components = models.BooleanField(default=False)
    missing_components = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("moderated", "Moderated"), ("approved", "Approved"), ("locked", "Locked")], default="draft")
    processed_by = models.ForeignKey(User, related_name="processed_upper_results", on_delete=models.SET_NULL, null=True, blank=True)
    moderated_by = models.ForeignKey(User, related_name="moderated_upper_results", on_delete=models.SET_NULL, null=True, blank=True)
    moderated_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, related_name="approved_upper_results", on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(User, related_name="locked_upper_results", on_delete=models.SET_NULL, null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["plan__subject__name", "student__first_name", "student__last_name"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "student", "term"], condition=Q(is_deleted=False), name="unique_active_upper_student_subject_result")
        ]

    def clean(self):
        if self.plan_id:
            if self.plan.academic_year_id != self.term.academic_year_id:
                raise ValidationError({"term": "Term belongs to a different academic year from the assessment plan."})
            if self.plan.class_level_id != self.stream.class_level_id:
                raise ValidationError({"stream": "Stream class level does not match the assessment plan."})
        if self.student_id and self.student.stream_id != self.stream_id:
            raise ValidationError({"student": "Student is not currently assigned to the result stream."})
        if self.status in {"approved", "locked"} and self.has_missing_components:
            raise ValidationError("Incomplete upper-secondary results cannot be approved or locked.")

    def save(self, *args, **kwargs):
        allow_locked_transition = kwargs.pop("allow_locked_transition", False)
        if self.pk:
            current = UpperSubjectResult.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if current == "locked" and not allow_locked_transition:
                raise ValidationError("Locked processed results are read-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    @transaction.atomic
    def transition(self, operation, user):
        transitions = {
            "moderate": ({"draft"}, "moderated"),
            "approve": ({"moderated"}, "approved"),
            "lock": ({"approved"}, "locked"),
            "reopen": ({"moderated", "approved", "locked"}, "draft"),
        }
        if operation not in transitions:
            raise ValidationError("Unknown upper-secondary result workflow operation.")
        allowed, target = transitions[operation]
        if self.status not in allowed:
            raise ValidationError(f"Cannot {operation} a result in {self.get_status_display()} state.")
        department_head_id = self.plan.subject.department.head_id if self.plan.subject.department_id else None
        if operation == "moderate" and not (user.is_superuser or user.role in {"super_admin", "headteacher", "director_of_studies"} or user.pk == department_head_id):
            raise ValidationError("Only the subject HOD or academic management may moderate this result.")
        if operation == "approve" and not (user.is_superuser or user.role in {"super_admin", "director_of_studies"}):
            raise ValidationError("DOS approval is required.")
        if operation == "lock" and not (user.is_superuser or user.role in {"super_admin", "headteacher"}):
            raise ValidationError("Headteacher confirmation is required to lock results.")
        if operation == "reopen" and not (user.is_superuser or user.role in {"super_admin", "headteacher", "director_of_studies"}):
            raise ValidationError("Academic management authorisation is required to reopen results.")
        now = timezone.now()
        if operation == "moderate":
            self.moderated_by, self.moderated_at = user, now
        elif operation == "approve":
            self.approved_by, self.approved_at = user, now
        elif operation == "lock":
            self.locked_by, self.locked_at = user, now
        elif operation == "reopen":
            self.moderated_by = self.moderated_at = self.approved_by = self.approved_at = self.locked_by = self.locked_at = None
        self.status = target
        self.save(allow_locked_transition=operation == "reopen")

    def __str__(self):
        return f"{self.student} · {self.plan.subject} · {self.total_score}"


class UNEBCandidate(BaseModel):
    student = models.ForeignKey(Student, related_name="uneb_candidates", on_delete=models.PROTECT)
    examination_level = models.CharField(max_length=10, choices=[("uce", "UCE"), ("uace", "UACE")])
    examination_year = models.PositiveIntegerField()
    index_number = models.CharField(max_length=40, blank=True)
    centre_number = models.CharField(max_length=30)
    candidate_name = models.CharField(max_length=200, blank=True)
    gender = models.CharField(max_length=10, choices=[("male", "Male"), ("female", "Female")])
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("verified", "Verified"), ("registered", "Registered"), ("withdrawn", "Withdrawn")], default="draft")
    verified_by = models.ForeignKey(User, related_name="verified_uneb_candidates", on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["examination_year", "examination_level", "student__first_name"]
        constraints = [models.UniqueConstraint(fields=["student", "examination_level", "examination_year"], condition=Q(is_deleted=False), name="unique_active_uneb_candidate")]

    def clean(self):
        if self.student_id and self.student.stream_id:
            level = self.student.stream.class_level.level
            if self.examination_level == "uce" and level not in {3, 4}:
                raise ValidationError({"student": "A UCE candidate record requires an S3 or S4 learner."})
            if self.examination_level == "uace" and level not in {5, 6}:
                raise ValidationError({"student": "A UACE candidate record requires an S5 or S6 learner."})

    def save(self, *args, **kwargs):
        if not self.candidate_name:
            self.candidate_name = self.student.full_name.upper()
        if not self.gender:
            self.gender = self.student.gender
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.candidate_name} · {self.examination_level.upper()} {self.examination_year}"


class UNEBCandidateSubject(BaseModel):
    candidate = models.ForeignKey(UNEBCandidate, related_name="registered_subjects", on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, related_name="uneb_candidate_subjects", on_delete=models.PROTECT)
    subject_code = models.CharField(max_length=20, blank=True)
    category = models.CharField(max_length=20, choices=[("core", "Core"), ("elective", "Elective"), ("principal", "Principal"), ("subsidiary", "Subsidiary")], default="core")
    is_registered = models.BooleanField(default=True)

    class Meta:
        ordering = ["subject__name"]
        constraints = [models.UniqueConstraint(fields=["candidate", "subject"], condition=Q(is_deleted=False), name="unique_active_uneb_candidate_subject")]

    def save(self, *args, **kwargs):
        if not self.subject_code:
            self.subject_code = self.subject.uneb_code or self.subject.code
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.candidate} · {self.subject}"


class UNEBContinuousAssessment(BaseModel):
    COMPONENTS = [("subject_achievement", "Subject achievement"), ("activity_integration", "Activity of Integration"), ("project", "Project"), ("coursework", "Coursework")]
    candidate_subject = models.ForeignKey(UNEBCandidateSubject, related_name="continuous_assessments", on_delete=models.CASCADE)
    class_level = models.ForeignKey("academics.ClassLevel", related_name="uneb_ca_records", on_delete=models.PROTECT)
    term = models.ForeignKey(Term, related_name="uneb_ca_records", on_delete=models.PROTECT, null=True, blank=True)
    component = models.CharField(max_length=30, choices=COMPONENTS)
    raw_score = models.DecimalField(max_digits=7, decimal_places=2, validators=[MinValueValidator(0)])
    maximum_score = models.DecimalField(max_digits=7, decimal_places=2, default=100, validators=[MinValueValidator(Decimal("0.01"))])
    percentage_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    evidence_reference = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("verified", "Verified"), ("approved", "Approved"), ("exported", "Exported")], default="draft")
    entered_by = models.ForeignKey(User, related_name="entered_uneb_ca", on_delete=models.SET_NULL, null=True)
    verified_by = models.ForeignKey(User, related_name="verified_uneb_ca", on_delete=models.SET_NULL, null=True, blank=True)
    approved_by = models.ForeignKey(User, related_name="approved_uneb_ca", on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["candidate_subject__candidate__candidate_name", "candidate_subject__subject__name", "class_level__level", "term__number"]
        constraints = [models.UniqueConstraint(fields=["candidate_subject", "class_level", "term", "component"], condition=Q(is_deleted=False), name="unique_active_uneb_ca_component")]

    def clean(self):
        if self.raw_score > self.maximum_score:
            raise ValidationError({"raw_score": "Raw score cannot exceed the maximum score."})
        level = self.class_level.level if self.class_level_id else None
        exam_level = self.candidate_subject.candidate.examination_level if self.candidate_subject_id else None
        if exam_level == "uce" and level not in {3, 4}:
            raise ValidationError({"class_level": "UCE continuous-assessment records must be from S3 or S4."})
        if exam_level == "uace" and level not in {5, 6}:
            raise ValidationError({"class_level": "UACE continuous-assessment records must be from S5 or S6."})
        if self.term_id and self.candidate_subject_id:
            exam_year = self.candidate_subject.candidate.examination_year
            academic_year = self.term.academic_year
            if exam_year not in {academic_year.start_date.year, academic_year.end_date.year}:
                raise ValidationError({"term": "Term does not belong to the candidate's examination year."})

    def save(self, *args, **kwargs):
        raw = Decimal(str(self.raw_score))
        maximum = Decimal(str(self.maximum_score))
        self.percentage_score = (raw / maximum * 100).quantize(Decimal("0.01"))
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.candidate_subject} · {self.get_component_display()}"


class UNEBExportBatch(BaseModel):
    examination_level = models.CharField(max_length=10, choices=[("uce", "UCE"), ("uace", "UACE")])
    examination_year = models.PositiveIntegerField()
    generated_by = models.ForeignKey(User, related_name="uneb_export_batches", on_delete=models.SET_NULL, null=True)
    generated_at = models.DateTimeField(default=timezone.now)
    record_count = models.PositiveIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=[("generated", "Generated"), ("submitted", "Submitted externally"), ("accepted", "Accepted"), ("rejected", "Rejected")], default="generated")
    notes = models.TextField(blank=True)
    records = models.ManyToManyField(UNEBContinuousAssessment, related_name="export_batches", blank=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"{self.examination_level.upper()} {self.examination_year} · {self.generated_at:%d %b %Y}"
