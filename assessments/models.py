from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from academics.models import AcademicYear, ClassLevel, Stream, Subject, SubjectAllocation, Term
from accounts.models import User
from config.models import BaseModel
from students.models import Student


class Competency(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    scale = models.JSONField(default=list, blank=True)
    display_order = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    curriculum_stage = models.CharField(max_length=20, choices=[("lower", "Lower Secondary"), ("advanced", "Advanced Secondary"), ("both", "Both")], default="both")
    assessment_mode = models.CharField(max_length=20, choices=[("integrated", "Integrated into learning outcomes"), ("standalone", "Standalone")], default="integrated")

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class AssessmentScale(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        if self.is_default and not self.is_active:
            raise ValidationError({"is_active": "The default achievement scale must be active."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_default:
            AssessmentScale.objects.exclude(pk=self.pk).update(is_default=False)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CompetencyLevel(BaseModel):
    scale = models.ForeignKey(AssessmentScale, related_name="levels", on_delete=models.PROTECT, null=True, blank=True)
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=12, unique=True)
    numeric_value = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=180, blank=True)
    colour = models.CharField(max_length=20, default="#10b981")
    display_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["display_order", "numeric_value"]

    def __str__(self):
        return self.name


class CompetencyIndicator(BaseModel):
    competency = models.ForeignKey(Competency, related_name="indicators", on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, related_name="competency_indicators", on_delete=models.CASCADE, null=True, blank=True)
    class_level = models.ForeignKey("academics.ClassLevel", related_name="competency_indicators", on_delete=models.CASCADE, null=True, blank=True)
    statement = models.TextField()
    display_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["competency", "display_order"]

    def __str__(self):
        return self.statement[:80]


class CurriculumFramework(BaseModel):
    name = models.CharField(max_length=160)
    stage = models.CharField(max_length=20, choices=[("lower", "Lower Secondary"), ("advanced", "Advanced Secondary")])
    version = models.CharField(max_length=40, blank=True)
    implementation_year = models.PositiveIntegerField(default=2026)
    authority = models.CharField(max_length=120, default="National Curriculum Development Centre")
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("published", "Published"), ("retired", "Retired")], default="draft")
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    source_reference = models.URLField(blank=True)
    supersedes = models.ForeignKey("self", related_name="successor_versions", on_delete=models.PROTECT, null=True, blank=True)
    published_by = models.ForeignKey(User, related_name="published_curriculum_frameworks", on_delete=models.SET_NULL, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["stage", "-implementation_year"]

    def clean(self):
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The version end date cannot precede its start date."})
        if self.supersedes_id:
            if self.supersedes_id == self.pk:
                raise ValidationError({"supersedes": "A curriculum version cannot supersede itself."})
            if self.supersedes.stage != self.stage:
                raise ValidationError({"supersedes": "Curriculum versions must belong to the same stage."})
        if self.status == "published" and not self.published_by_id:
            raise ValidationError({"published_by": "A published curriculum version requires an approving officer."})

    def save(self, *args, **kwargs):
        self.is_active = self.status in {"draft", "published"}
        if self.status == "published" and self.published_by_id and not self.published_at:
            self.published_at = timezone.now()
        self.full_clean()
        return super().save(*args, **kwargs)

    @transaction.atomic
    def transition(self, operation, user):
        if operation == "publish" and self.status == "draft":
            if not self.topics.filter(is_deleted=False, learning_outcomes__is_deleted=False).exists():
                raise ValidationError("Import at least one topic and learning outcome before publication.")
            self.status, self.published_by, self.published_at = "published", user, timezone.now()
            if self.supersedes_id:
                CurriculumFramework.objects.filter(pk=self.supersedes_id).update(
                    status="retired", is_active=False, effective_to=self.effective_from,
                )
        elif operation == "retire" and self.status == "published":
            self.status, self.is_active = "retired", False
            if not self.effective_to:
                self.effective_to = timezone.localdate()
        elif operation == "reopen" and self.status == "draft":
            return
        else:
            raise ValidationError("That curriculum-version transition is not allowed.")
        self.save()

    def __str__(self):
        return f"{self.name} ({self.version or self.implementation_year})"


class CurriculumValue(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=1)
    is_assessed = models.BooleanField(default=False, help_text="NCDC values inform learning but are not scored like knowledge and skills.")

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class CurriculumLearningArea(BaseModel):
    framework = models.ForeignKey(CurriculumFramework, related_name="learning_areas", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="curriculum_learning_areas", on_delete=models.PROTECT)
    code = models.CharField(max_length=30, blank=True)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    sequence = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["subject__name", "sequence", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["framework", "subject", "sequence"],
                condition=Q(is_deleted=False),
                name="unique_active_learning_area_sequence",
            )
        ]

    def __str__(self):
        return f"{self.subject.name} · {self.name}"


class CurriculumTopic(BaseModel):
    framework = models.ForeignKey(CurriculumFramework, related_name="topics", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="curriculum_topics", on_delete=models.PROTECT)
    class_level = models.ForeignKey(ClassLevel, related_name="curriculum_topics", on_delete=models.PROTECT)
    learning_area = models.ForeignKey(CurriculumLearningArea, related_name="topics", on_delete=models.PROTECT, null=True, blank=True)
    term_number = models.PositiveSmallIntegerField(choices=[(1, "Term I"), (2, "Term II"), (3, "Term III")], default=1)
    code = models.CharField(max_length=30, blank=True)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    suggested_periods = models.PositiveSmallIntegerField(default=1)
    sequence = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["class_level__level", "subject__name", "term_number", "sequence"]
        constraints = [models.UniqueConstraint(fields=["framework", "subject", "class_level", "term_number", "sequence"], condition=Q(is_deleted=False), name="unique_active_curriculum_topic_sequence")]

    def clean(self):
        if self.learning_area_id:
            if self.learning_area.framework_id != self.framework_id:
                raise ValidationError({"learning_area": "Learning area and topic must use the same curriculum framework."})
            if self.learning_area.subject_id != self.subject_id:
                raise ValidationError({"learning_area": "Learning area and topic must belong to the same subject."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.class_level} · {self.subject.name} · {self.title}"


class LearningOutcome(BaseModel):
    topic = models.ForeignKey(CurriculumTopic, related_name="learning_outcomes", on_delete=models.CASCADE)
    code = models.CharField(max_length=40, blank=True)
    statement = models.TextField()
    assessment_criteria = models.TextField(blank=True)
    suggested_activities = models.TextField(blank=True)
    required_evidence = models.TextField(blank=True)
    generic_skills = models.ManyToManyField(Competency, related_name="learning_outcomes", blank=True)
    values = models.ManyToManyField(CurriculumValue, related_name="learning_outcomes", blank=True)
    display_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["topic", "display_order"]

    def __str__(self):
        return self.statement[:100]


class ActivityOfIntegration(BaseModel):
    topic = models.ForeignKey(CurriculumTopic, related_name="integration_activities", on_delete=models.CASCADE)
    title = models.CharField(max_length=180)
    scenario = models.TextField()
    task = models.TextField()
    expected_product = models.TextField(blank=True)
    teacher_guidance = models.TextField(blank=True)
    suggested_duration_minutes = models.PositiveIntegerField(default=80)
    is_project = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["topic", "title"]

    def __str__(self):
        return self.title


class Rubric(BaseModel):
    name = models.CharField(max_length=160)
    activity = models.OneToOneField(ActivityOfIntegration, related_name="rubric", on_delete=models.CASCADE, null=True, blank=True)
    subject = models.ForeignKey(Subject, related_name="rubrics", on_delete=models.PROTECT, null=True, blank=True)
    description = models.TextField(blank=True)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RubricCriterion(BaseModel):
    rubric = models.ForeignKey(Rubric, related_name="criteria", on_delete=models.CASCADE)
    name = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    maximum_score = models.DecimalField(max_digits=6, decimal_places=2, default=10)
    display_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["rubric", "display_order"]

    def __str__(self):
        return self.name


class RubricLevel(BaseModel):
    criterion = models.ForeignKey(RubricCriterion, related_name="levels", on_delete=models.CASCADE)
    name = models.CharField(max_length=60)
    descriptor = models.TextField()
    score = models.DecimalField(max_digits=6, decimal_places=2)
    display_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["criterion", "display_order"]

    def __str__(self):
        return f"{self.criterion.name} · {self.name}"


class AssessmentPolicy(BaseModel):
    name = models.CharField(max_length=160)
    academic_year = models.ForeignKey(AcademicYear, related_name="assessment_policies", on_delete=models.PROTECT)
    class_level = models.ForeignKey(ClassLevel, related_name="assessment_policies", on_delete=models.PROTECT, null=True, blank=True)
    curriculum_stage = models.CharField(max_length=20, choices=[("lower", "Lower Secondary"), ("advanced", "Advanced Secondary")])
    purpose = models.CharField(max_length=20, choices=[("internal", "Internal reporting"), ("uneb", "UNEB preparation")], default="internal")
    achievement_scale = models.ForeignKey(AssessmentScale, related_name="policies", on_delete=models.PROTECT, null=True, blank=True)
    ongoing_weight = models.DecimalField(max_digits=5, decimal_places=2, default=40, validators=[MinValueValidator(0), MaxValueValidator(100)])
    summative_weight = models.DecimalField(max_digits=5, decimal_places=2, default=60, validators=[MinValueValidator(0), MaxValueValidator(100)])
    summative_frequency = models.CharField(max_length=20, choices=[("termly", "Termly"), ("annual", "Once per year"), ("none", "No separate summative exam")], default="termly")
    show_class_position = models.BooleanField(default=False)
    requires_complete_marks = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["academic_year", "class_level__level", "name"]

    def clean(self):
        if self.ongoing_weight + self.summative_weight != 100:
            raise ValidationError("Ongoing and summative weights must add up to 100%.")
        if self.curriculum_stage == "advanced" and self.summative_frequency == "termly":
            raise ValidationError({"summative_frequency": "The aligned Advanced Secondary Curriculum uses one school-based summative assessment annually."})
        if self.class_level_id:
            expected = "lower" if self.class_level.curriculum == "lower" else "advanced"
            if self.curriculum_stage != expected:
                raise ValidationError({"curriculum_stage": "Policy stage does not match the selected class level."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class AssessmentType(BaseModel):
    CATEGORY_CHOICES = [
        ("exercise", "Class exercise"), ("homework", "Homework"), ("test", "Test"),
        ("assignment", "Assignment"), ("project", "Project"), ("practical", "Practical work"),
        ("oral", "Oral presentation"), ("debate", "Debate"), ("presentation", "Presentation"),
        ("group", "Group work"), ("observation", "Observation"), ("fieldwork", "Field work"),
        ("experiment", "Experiment"), ("research", "Research task"), ("portfolio", "Portfolio assignment"),
        ("coursework", "Coursework"),
    ]
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="test")
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=10, validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.weight}%)"


class Assessment(BaseModel):
    STATUS_CHOICES = [("draft", "Draft"), ("published", "Published"), ("closed", "Closed"), ("moderated", "Moderated")]
    PROJECT_TYPE_CHOICES = [
        ("individual", "Individual project"), ("group", "Group project"),
        ("class", "Class project"), ("interdisciplinary", "Interdisciplinary project"),
        ("long_term", "Long-term project"), ("community", "Community project"),
    ]
    title = models.CharField(max_length=200)
    assessment_type = models.ForeignKey(AssessmentType, related_name="assessments", on_delete=models.PROTECT)
    term = models.ForeignKey(Term, related_name="assessments", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="assessments", on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, related_name="assessments", on_delete=models.PROTECT, null=True)
    created_by = models.ForeignKey(User, related_name="created_assessments", on_delete=models.SET_NULL, null=True, blank=True)
    assigned_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(blank=True, null=True)
    instructions = models.TextField(blank=True)
    attachment = models.FileField(upload_to="assessments/%Y/", null=True, blank=True)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100, validators=[MinValueValidator(Decimal("0.01"))])
    weight = models.DecimalField(
        "reporting weight", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Optional weight for this task. When blank, the assessment type's default weight is used.",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    topic = models.ForeignKey(CurriculumTopic, related_name="assessments", on_delete=models.SET_NULL, null=True, blank=True)
    activity_of_integration = models.ForeignKey(ActivityOfIntegration, related_name="assessments", on_delete=models.SET_NULL, null=True, blank=True)
    learning_outcomes = models.ManyToManyField(LearningOutcome, related_name="assessments", blank=True)
    rubric = models.ForeignKey(Rubric, related_name="assessments", on_delete=models.SET_NULL, null=True, blank=True)
    assessment_period = models.CharField(max_length=20, choices=[("ongoing", "Ongoing formative"), ("end_topic", "End-of-topic integration"), ("annual", "Annual school summative"), ("end_cycle", "End-of-cycle certification")], default="ongoing")
    evidence_method = models.CharField(max_length=20, choices=[("observation", "Observation"), ("conversation", "Conversation"), ("product", "Product"), ("triangulated", "Triangulated evidence")], default="product")
    is_summative = models.BooleanField(default=False)
    project_type = models.CharField(max_length=24, choices=PROJECT_TYPE_CHOICES, blank=True)
    project_supervisor = models.ForeignKey(User, related_name="supervised_projects", on_delete=models.SET_NULL, null=True, blank=True)
    project_subjects = models.ManyToManyField(Subject, related_name="interdisciplinary_projects", blank=True)
    workflow_status = models.CharField(
        max_length=24,
        choices=[
            ("draft", "Draft"), ("submitted", "Submitted for HOD review"),
            ("hod_changes", "HOD changes requested"), ("hod_approved", "HOD approved"),
            ("dos_changes", "DOS changes requested"), ("approved", "DOS approved"),
            ("locked", "Locked"),
        ],
        default="draft",
    )
    submitted_by = models.ForeignKey(User, related_name="submitted_assessments", on_delete=models.SET_NULL, null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    workflow_locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-assigned_date", "title"]

    def clean(self):
        if self.due_date and self.assigned_date and self.due_date < self.assigned_date:
            raise ValidationError({"due_date": "Due date cannot be before the assigned date."})
        if self.stream_id and self.term_id and self.stream.academic_year_id != self.term.academic_year_id:
            raise ValidationError("The stream and term must be in the same academic year.")
        if self.stream_id and self.stream.class_level.curriculum == "upper" and self.is_summative and self.assessment_period != "annual":
            raise ValidationError({"assessment_period": "Advanced Secondary school-based summative assessment must be annual."})
        if self.activity_of_integration_id and self.topic_id and self.activity_of_integration.topic_id != self.topic_id:
            raise ValidationError("The Activity of Integration must belong to the selected topic.")
        if self.rubric_id and self.max_score != self.rubric.total_marks:
            raise ValidationError({"max_score": "Maximum score must equal the selected rubric total."})
        if self.project_supervisor_id and self.project_supervisor.role not in {"teacher", "director_of_studies", "headteacher", "super_admin"}:
            raise ValidationError({"project_supervisor": "Project supervisors must be academic staff."})
        if (self.project_type or self.project_supervisor_id) and not self.project_enabled:
            raise ValidationError("Project details can only be added to a project assessment or project Activity of Integration.")

    @property
    def marks_entered(self):
        return self.results.filter(is_deleted=False).count()

    @property
    def effective_weight(self):
        return self.weight if self.weight is not None else self.assessment_type.weight

    @property
    def project_enabled(self):
        return bool(
            (self.assessment_type_id and self.assessment_type.category == "project")
            or (self.activity_of_integration_id and self.activity_of_integration.is_project)
        )

    @property
    def is_workflow_locked(self):
        return self.workflow_status in {"approved", "locked"}

    @transaction.atomic
    def transition(self, operation, user, comment=""):
        transitions = {
            "submit": ({"draft", "hod_changes", "dos_changes"}, "submitted"),
            "hod_approve": ({"submitted"}, "hod_approved"),
            "hod_request_changes": ({"submitted"}, "hod_changes"),
            "dos_approve": ({"hod_approved"}, "approved"),
            "dos_request_changes": ({"hod_approved"}, "dos_changes"),
            "lock": ({"approved"}, "locked"),
            "reopen": ({"approved", "locked"}, "draft"),
        }
        if operation not in transitions:
            raise ValidationError("Unknown assessment workflow operation.")
        allowed, target = transitions[operation]
        if self.workflow_status not in allowed:
            raise ValidationError(f"Cannot {operation.replace('_', ' ')} from {self.get_workflow_status_display()}.")

        manager_roles = {"super_admin", "headteacher", "director_of_studies"}
        if operation.startswith("hod_"):
            department_head_id = self.subject.department.head_id if self.subject_id and self.subject.department_id else None
            if not (user.is_superuser or user.role in manager_roles or user.pk == department_head_id):
                raise ValidationError("Only the subject Head of Department or academic management may perform HOD review.")
        elif operation.startswith("dos_") or operation in {"lock", "reopen"}:
            if not (user.is_superuser or user.role in manager_roles):
                raise ValidationError("Academic management approval is required.")

        now = timezone.now()
        if operation == "submit":
            self.submitted_by, self.submitted_at = user, now
            self.status = "closed"
        elif operation.startswith("hod_"):
            AssessmentReview.objects.create(
                assessment=self,
                stage="hod",
                decision="approved" if operation == "hod_approve" else "changes_requested",
                reviewer=user,
                comment=comment,
            )
            if operation == "hod_approve":
                self.status = "moderated"
        elif operation.startswith("dos_"):
            AssessmentReview.objects.create(
                assessment=self,
                stage="dos",
                decision="approved" if operation == "dos_approve" else "changes_requested",
                reviewer=user,
                comment=comment,
            )
            if operation == "dos_approve":
                self.workflow_locked_at = now
                self.status = "moderated"
        elif operation == "lock":
            self.workflow_locked_at = now
        elif operation == "reopen":
            self.workflow_locked_at = None
            self.status = "draft"
        self.workflow_status = target
        self.save()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ProjectMilestone(BaseModel):
    assessment = models.ForeignKey(Assessment, related_name="project_milestones", on_delete=models.CASCADE)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    expected_evidence = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    sequence = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=16,
        choices=[("planned", "Planned"), ("open", "Open"), ("closed", "Closed")],
        default="planned",
    )

    class Meta:
        ordering = ["assessment", "sequence", "due_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "sequence"],
                condition=Q(is_deleted=False),
                name="unique_active_project_milestone_sequence",
            )
        ]

    def clean(self):
        if self.assessment_id:
            if not self.assessment.project_enabled:
                raise ValidationError({"assessment": "Milestones require a project assessment or project Activity of Integration."})
            if self.assessment.is_workflow_locked:
                raise ValidationError("DOS-approved project milestones are read-only.")
            if self.due_date and self.due_date < self.assessment.assigned_date:
                raise ValidationError({"due_date": "Milestone due date cannot be before the project is assigned."})
            if self.due_date and self.assessment.due_date and self.due_date > self.assessment.due_date:
                raise ValidationError({"due_date": "Milestone due date cannot be after the project deadline."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.assessment} · {self.title}"


class ProjectTeam(BaseModel):
    assessment = models.ForeignKey(Assessment, related_name="project_teams", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    driving_question = models.TextField(blank=True)
    community_partner = models.CharField(max_length=180, blank=True)
    mentor = models.ForeignKey(User, related_name="mentored_project_teams", on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[("forming", "Forming"), ("active", "Active"), ("completed", "Completed"), ("archived", "Archived")], default="forming")

    class Meta:
        ordering = ["assessment", "name"]
        constraints = [models.UniqueConstraint(fields=["assessment", "name"], condition=Q(is_deleted=False), name="unique_active_project_team_name")]

    def clean(self):
        if self.assessment_id and not self.assessment.project_enabled:
            raise ValidationError({"assessment": "Project teams require a project assessment."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.assessment} · {self.name}"


class ProjectTeamMember(BaseModel):
    team = models.ForeignKey(ProjectTeam, related_name="members", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, related_name="project_memberships", on_delete=models.CASCADE)
    role = models.CharField(max_length=80, blank=True)
    joined_on = models.DateField(default=timezone.localdate)
    contribution_notes = models.TextField(blank=True)
    learner_reflection = models.TextField(blank=True)

    class Meta:
        ordering = ["team", "student__first_name", "student__last_name"]
        constraints = [models.UniqueConstraint(fields=["team", "student"], condition=Q(is_deleted=False), name="unique_active_project_team_member")]

    def clean(self):
        if self.team_id and self.student_id and self.team.assessment.stream_id and self.student.stream_id != self.team.assessment.stream_id:
            raise ValidationError({"student": "Learner is not currently assigned to the project's stream."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.team} · {self.student.full_name}"


class AssessmentResult(BaseModel):
    assessment = models.ForeignKey(Assessment, related_name="results", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, related_name="assessment_results", on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
    grade = models.CharField(max_length=5, blank=True)
    feedback = models.TextField(blank=True)
    marked_by = models.ForeignKey(User, related_name="marked_assessment_results", on_delete=models.SET_NULL, null=True, blank=True)
    marked_at = models.DateTimeField(default=timezone.now)
    moderated = models.BooleanField(default=False)
    moderated_by = models.ForeignKey(User, related_name="moderated_assessment_results", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["student__first_name", "student__last_name"]
        constraints = [models.UniqueConstraint(fields=["assessment", "student"], condition=Q(is_deleted=False), name="unique_active_assessment_result")]

    def clean(self):
        if self.assessment_id and self.assessment.is_workflow_locked:
            raise ValidationError("DOS-approved assessment results are read-only.")
        if self.assessment_id and self.score is not None and self.score > self.assessment.max_score:
            raise ValidationError({"score": f"Score cannot exceed {self.assessment.max_score}."})
        if self.assessment_id and self.student_id and self.assessment.stream_id and self.student.stream_id != self.assessment.stream_id:
            raise ValidationError({"student": "Student is not enrolled in this assessment's stream."})

    @property
    def percentage(self):
        if not self.assessment.max_score:
            return Decimal("0")
        return (self.score / self.assessment.max_score * 100).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.score}"


class CompetencyAssessment(BaseModel):
    assessment = models.ForeignKey(Assessment, related_name="competency_assessments", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, related_name="competency_assessments", on_delete=models.CASCADE)
    competency = models.ForeignKey(Competency, related_name="student_assessments", on_delete=models.PROTECT)
    indicator = models.ForeignKey(CompetencyIndicator, related_name="student_assessments", on_delete=models.SET_NULL, null=True, blank=True)
    scale_level = models.ForeignKey(CompetencyLevel, related_name="student_assessments", on_delete=models.PROTECT, null=True, blank=True)
    level = models.CharField(max_length=20, blank=True)
    comment = models.TextField(blank=True)
    assessed_by = models.ForeignKey(User, related_name="competency_ratings", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["competency__display_order"]
        constraints = [models.UniqueConstraint(fields=["assessment", "student", "competency"], condition=Q(is_deleted=False), name="unique_active_competency_assessment")]

    def clean(self):
        if self.assessment_id and self.assessment.is_workflow_locked:
            raise ValidationError("DOS-approved competency ratings are read-only.")
        if self.assessment_id and self.student_id and self.assessment.stream_id and self.student.stream_id != self.assessment.stream_id:
            raise ValidationError({"student": "Student is not enrolled in this assessment's stream."})
        if self.indicator_id and self.indicator.competency_id != self.competency_id:
            raise ValidationError({"indicator": "Indicator does not belong to the selected competency."})

    def save(self, *args, **kwargs):
        if self.scale_level_id:
            self.level = self.scale_level.name
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.competency}"


class AssessmentSubmission(BaseModel):
    assessment = models.ForeignKey(Assessment, related_name="submissions", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, related_name="assessment_submissions", on_delete=models.CASCADE)
    response_text = models.TextField(blank=True)
    attachment = models.FileField(upload_to="submissions/%Y/", null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=[("submitted", "Submitted"), ("late", "Late"), ("reviewed", "Reviewed"), ("returned", "Returned")], default="submitted")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assessment", "student"], condition=Q(is_deleted=False), name="unique_active_assessment_submission")]

    def save(self, *args, **kwargs):
        if self.assessment.due_date and timezone.localdate() > self.assessment.due_date:
            self.status = "late"
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.assessment}"


class AssessmentEvidence(BaseModel):
    assessment = models.ForeignKey(Assessment, related_name="evidence_records", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, related_name="assessment_evidence", on_delete=models.CASCADE)
    method = models.CharField(max_length=20, choices=[("observation", "Observation"), ("conversation", "Conversation"), ("product", "Product")])
    note = models.TextField()
    attachment = models.FileField(upload_to="assessment-evidence/%Y/", null=True, blank=True)
    learning_outcomes = models.ManyToManyField(LearningOutcome, related_name="evidence_records", blank=True)
    competencies = models.ManyToManyField(Competency, related_name="evidence_records", blank=True)
    context_notes = models.TextField(blank=True)
    captured_by = models.ForeignKey(User, related_name="captured_assessment_evidence", on_delete=models.SET_NULL, null=True)
    captured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-captured_at"]

    def clean(self):
        if self.assessment_id and self.assessment.is_workflow_locked:
            raise ValidationError("DOS-approved assessment evidence is read-only.")
        if self.assessment_id and self.student_id and self.assessment.stream_id != self.student.stream_id:
            raise ValidationError({"student": "Student is not in the assessment stream."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.get_method_display()}"


class EvidenceAsset(BaseModel):
    evidence = models.ForeignKey(AssessmentEvidence, related_name="assets", on_delete=models.CASCADE)
    media_type = models.CharField(max_length=20, choices=[
        ("image", "Image"), ("audio", "Audio"), ("video", "Video"),
        ("document", "Document"), ("link", "External link"), ("text", "Text note"),
    ])
    file = models.FileField(upload_to="assessment-evidence/assets/%Y/", null=True, blank=True)
    external_url = models.URLField(blank=True)
    caption = models.CharField(max_length=240, blank=True)
    transcript = models.TextField(blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)
    captured_by = models.ForeignKey(User, related_name="captured_evidence_assets", on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["captured_at", "pk"]

    def clean(self):
        if self.media_type == "link" and not self.external_url:
            raise ValidationError({"external_url": "A link asset requires a URL."})
        if self.media_type in {"image", "audio", "video", "document"} and not self.file:
            raise ValidationError({"file": f"A {self.media_type} asset requires a file."})
        if self.evidence_id and self.evidence.assessment.is_workflow_locked:
            raise ValidationError("DOS-approved multimedia evidence is read-only.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.evidence} · {self.get_media_type_display()}"


class RubricRating(BaseModel):
    result = models.ForeignKey(AssessmentResult, related_name="rubric_ratings", on_delete=models.CASCADE)
    criterion = models.ForeignKey(RubricCriterion, related_name="ratings", on_delete=models.PROTECT)
    level = models.ForeignKey(RubricLevel, related_name="ratings", on_delete=models.PROTECT)
    comment = models.CharField(max_length=180, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["result", "criterion"], condition=Q(is_deleted=False), name="unique_active_result_rubric_criterion")]

    def clean(self):
        if self.result_id and self.result.assessment.is_workflow_locked:
            raise ValidationError("DOS-approved rubric ratings are read-only.")
        if self.level_id and self.criterion_id and self.level.criterion_id != self.criterion_id:
            raise ValidationError({"level": "The selected level does not belong to this criterion."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.result.student} · {self.criterion} · {self.level.name}"


class SchemeOfWork(BaseModel):
    STATUS_CHOICES = [
        ("draft", "Draft"), ("submitted", "Submitted"), ("changes_requested", "Changes requested"),
        ("approved", "HOD approved"),
    ]
    allocation = models.ForeignKey(SubjectAllocation, related_name="schemes_of_work", on_delete=models.PROTECT)
    title = models.CharField(max_length=180, blank=True)
    prepared_by = models.ForeignKey(User, related_name="prepared_schemes", on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="draft")
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, related_name="reviewed_schemes", on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True)

    class Meta:
        ordering = ["-allocation__term__academic_year__start_date", "allocation__stream", "allocation__subject"]
        constraints = [
            models.UniqueConstraint(fields=["allocation"], condition=Q(is_deleted=False), name="unique_active_allocation_scheme")
        ]

    def clean(self):
        if self.prepared_by_id and self.prepared_by.role == "teacher" and self.prepared_by_id != self.allocation.teacher_id:
            raise ValidationError({"prepared_by": "The scheme must be prepared by the allocated teacher."})
        if self.status in {"approved", "changes_requested"} and not self.reviewed_by_id:
            raise ValidationError({"reviewed_by": "A reviewed scheme requires a reviewer."})
        if self.reviewed_by_id and self.status == "approved":
            department_head_id = self.allocation.subject.department.head_id if self.allocation.subject.department_id else None
            if not (self.reviewed_by.is_superuser or self.reviewed_by.role in {"super_admin", "headteacher", "director_of_studies"} or self.reviewed_by_id == department_head_id):
                raise ValidationError({"reviewed_by": "Approval must be performed by the subject HOD or academic management."})

    def save(self, *args, **kwargs):
        if not self.title and self.allocation_id:
            self.title = f"{self.allocation.subject.name} scheme · {self.allocation.stream} · {self.allocation.term.name}"
        if self.status == "submitted" and not self.submitted_at:
            self.submitted_at = timezone.now()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class SchemeWeek(BaseModel):
    scheme = models.ForeignKey(SchemeOfWork, related_name="weekly_plans", on_delete=models.CASCADE)
    week_number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    sequence = models.PositiveSmallIntegerField(default=1)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    topic = models.ForeignKey(CurriculumTopic, related_name="scheme_weeks", on_delete=models.PROTECT)
    learning_outcomes = models.ManyToManyField(LearningOutcome, related_name="scheme_weeks", blank=True)
    competencies = models.ManyToManyField(Competency, related_name="scheme_weeks", blank=True)
    planned_periods = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    teacher_activities = models.TextField(blank=True)
    learner_activities = models.TextField(blank=True)
    resources_required = models.TextField(blank=True)
    assessment_methods = models.TextField(blank=True)
    required_evidence = models.TextField(blank=True)
    completed = models.BooleanField(default=False)
    completion_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["scheme", "week_number", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "week_number", "sequence"],
                condition=Q(is_deleted=False),
                name="unique_active_scheme_week_sequence",
            )
        ]

    def clean(self):
        allocation = self.scheme.allocation
        if self.topic_id:
            if self.topic.subject_id != allocation.subject_id:
                raise ValidationError({"topic": "Topic does not belong to the allocated subject."})
            if self.topic.class_level_id != allocation.stream.class_level_id:
                raise ValidationError({"topic": "Topic does not belong to the allocated class level."})
            if self.topic.term_number != allocation.term.number:
                raise ValidationError({"topic": "Topic does not belong to the allocation term."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "Week end date cannot precede its start date."})
        for field_name, value in (("start_date", self.start_date), ("end_date", self.end_date)):
            if value and not allocation.term.start_date <= value <= allocation.term.end_date:
                raise ValidationError({field_name: "Planned dates must fall inside the allocation term."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.scheme} · Week {self.week_number} · {self.topic.title}"


class LessonPlan(BaseModel):
    STATUS_CHOICES = [
        ("draft", "Draft"), ("submitted", "Submitted"), ("changes_requested", "Changes requested"),
        ("approved", "Approved"), ("delivered", "Delivered"),
    ]
    allocation = models.ForeignKey(SubjectAllocation, related_name="lesson_plans", on_delete=models.PROTECT)
    scheme_week = models.ForeignKey(SchemeWeek, related_name="lesson_plans", on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=180)
    lesson_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=40, validators=[MinValueValidator(1)])
    topic = models.ForeignKey(CurriculumTopic, related_name="lesson_plans", on_delete=models.PROTECT)
    objectives = models.TextField()
    learning_outcomes = models.ManyToManyField(LearningOutcome, related_name="lesson_plans", blank=True)
    competencies = models.ManyToManyField(Competency, related_name="lesson_plans", blank=True)
    teaching_activities = models.TextField()
    learner_activities = models.TextField()
    assessment_method = models.TextField()
    teaching_resources = models.TextField(blank=True)
    differentiation = models.TextField(blank=True, help_text="Planned support and extension for different learner needs.")
    reflection = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="draft")
    prepared_by = models.ForeignKey(User, related_name="prepared_lesson_plans", on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_by = models.ForeignKey(User, related_name="reviewed_lesson_plans", on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True)

    class Meta:
        ordering = ["-lesson_date", "start_time", "allocation__subject"]

    def clean(self):
        allocation = self.allocation
        if not allocation.term.start_date <= self.lesson_date <= allocation.term.end_date:
            raise ValidationError({"lesson_date": "Lesson date must fall inside the allocation term."})
        if self.topic_id and (self.topic.subject_id != allocation.subject_id or self.topic.class_level_id != allocation.stream.class_level_id):
            raise ValidationError({"topic": "Topic must match the allocated subject and class level."})
        if self.scheme_week_id and self.scheme_week.scheme.allocation_id != self.allocation_id:
            raise ValidationError({"scheme_week": "Scheme week must belong to the same subject allocation."})
        if self.prepared_by_id and self.prepared_by.role == "teacher" and self.prepared_by_id != allocation.teacher_id:
            raise ValidationError({"prepared_by": "Lesson plan must be prepared by the allocated teacher."})
        if self.status in {"approved", "changes_requested"} and not self.reviewed_by_id:
            raise ValidationError({"reviewed_by": "A reviewed lesson plan requires a reviewer."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} · {self.lesson_date}"


class Skill(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class LearningOutcomeAssessment(BaseModel):
    LEVEL_CHOICES = [
        ("exceeded", "Exceeded expectation"), ("met", "Met expectation"),
        ("approaching", "Approaching expectation"), ("needs_support", "Needs support"),
    ]
    student = models.ForeignKey(Student, related_name="learning_outcome_assessments", on_delete=models.CASCADE)
    outcome = models.ForeignKey(LearningOutcome, related_name="student_assessments", on_delete=models.PROTECT)
    term = models.ForeignKey(Term, related_name="learning_outcome_assessments", on_delete=models.PROTECT)
    assessment = models.ForeignKey(Assessment, related_name="learning_outcome_ratings", on_delete=models.CASCADE, null=True, blank=True)
    scale_level = models.ForeignKey(CompetencyLevel, related_name="learning_outcome_assessments", on_delete=models.PROTECT, null=True, blank=True)
    level = models.CharField(max_length=24, blank=True, help_text="Legacy code snapshot; new ratings use the configured scale level.")
    comment = models.TextField(blank=True)
    assessed_by = models.ForeignKey(User, related_name="assessed_learning_outcomes", on_delete=models.SET_NULL, null=True, blank=True)
    assessed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["student", "outcome__display_order", "-assessed_at"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "student", "outcome"], condition=Q(is_deleted=False, assessment__isnull=False), name="unique_active_assessment_student_outcome"),
            models.UniqueConstraint(fields=["term", "student", "outcome"], condition=Q(is_deleted=False, assessment__isnull=True), name="unique_active_term_student_outcome"),
        ]

    def clean(self):
        if not self.scale_level_id and not self.level:
            raise ValidationError({"scale_level": "Choose an achievement level."})
        if self.assessment_id:
            if self.assessment.is_workflow_locked:
                raise ValidationError("DOS-approved learning-outcome ratings are read-only.")
            if self.assessment.term_id != self.term_id:
                raise ValidationError({"term": "Term must match the selected assessment."})
            if self.assessment.stream_id and self.student.stream_id != self.assessment.stream_id:
                raise ValidationError({"student": "Student is not in the assessment stream."})
            if self.assessment.topic_id and self.outcome.topic_id != self.assessment.topic_id:
                raise ValidationError({"outcome": "Learning outcome must belong to the assessment topic."})

    def save(self, *args, **kwargs):
        if self.scale_level_id:
            self.level = self.scale_level.code
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def display_level(self):
        if self.scale_level_id:
            return self.scale_level.name
        return dict(self.LEVEL_CHOICES).get(self.level, self.level)

    def __str__(self):
        return f"{self.student} · {self.outcome} · {self.display_level}"


class LearnerSkillRating(BaseModel):
    student = models.ForeignKey(Student, related_name="skill_ratings", on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, related_name="learner_ratings", on_delete=models.PROTECT)
    term = models.ForeignKey(Term, related_name="skill_ratings", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="skill_ratings", on_delete=models.PROTECT, null=True, blank=True)
    assessment = models.ForeignKey(Assessment, related_name="skill_ratings", on_delete=models.CASCADE, null=True, blank=True)
    level = models.ForeignKey(CompetencyLevel, related_name="skill_ratings", on_delete=models.PROTECT)
    comment = models.TextField(blank=True)
    assessed_by = models.ForeignKey(User, related_name="assessed_skills", on_delete=models.SET_NULL, null=True, blank=True)
    assessed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["student", "skill__display_order", "-assessed_at"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "student", "skill"], condition=Q(is_deleted=False, assessment__isnull=False), name="unique_active_assessment_student_skill")
        ]

    def clean(self):
        if self.assessment_id:
            if self.assessment.is_workflow_locked:
                raise ValidationError("DOS-approved skill ratings are read-only.")
            if self.assessment.term_id != self.term_id:
                raise ValidationError({"term": "Term must match the selected assessment."})
            if self.subject_id and self.assessment.subject_id != self.subject_id:
                raise ValidationError({"subject": "Subject must match the selected assessment."})
            if self.assessment.stream_id and self.student.stream_id != self.assessment.stream_id:
                raise ValidationError({"student": "Student is not in the assessment stream."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.skill} · {self.level}"


class LearnerValueRating(BaseModel):
    student = models.ForeignKey(Student, related_name="value_ratings", on_delete=models.CASCADE)
    value = models.ForeignKey(CurriculumValue, related_name="learner_ratings", on_delete=models.PROTECT)
    term = models.ForeignKey(Term, related_name="value_ratings", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="value_ratings", on_delete=models.PROTECT, null=True, blank=True)
    assessment = models.ForeignKey(Assessment, related_name="value_ratings", on_delete=models.CASCADE, null=True, blank=True)
    level = models.ForeignKey(CompetencyLevel, related_name="value_ratings", on_delete=models.PROTECT)
    comment = models.TextField(blank=True)
    assessed_by = models.ForeignKey(User, related_name="assessed_values", on_delete=models.SET_NULL, null=True, blank=True)
    assessed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["student", "value__display_order", "-assessed_at"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "student", "value"], condition=Q(is_deleted=False, assessment__isnull=False), name="unique_active_assessment_student_value")
        ]

    def clean(self):
        if self.assessment_id:
            if self.assessment.is_workflow_locked:
                raise ValidationError("DOS-approved value ratings are read-only.")
            if self.assessment.term_id != self.term_id:
                raise ValidationError({"term": "Term must match the selected assessment."})
            if self.subject_id and self.assessment.subject_id != self.subject_id:
                raise ValidationError({"subject": "Subject must match the selected assessment."})
            if self.assessment.stream_id and self.student.stream_id != self.assessment.stream_id:
                raise ValidationError({"student": "Student is not in the assessment stream."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.value} · {self.level}"


class PortfolioItem(BaseModel):
    CATEGORY_CHOICES = [
        ("project", "Project"), ("assignment", "Assignment"), ("observation", "Teacher observation"),
        ("practical", "Practical work"), ("photo", "Photo"), ("document", "Document"),
        ("assessment", "Assessment evidence"), ("reflection", "Reflection note"),
    ]
    student = models.ForeignKey(Student, related_name="portfolio_items", on_delete=models.CASCADE)
    term = models.ForeignKey(Term, related_name="portfolio_items", on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, related_name="portfolio_items", on_delete=models.PROTECT, null=True, blank=True)
    subject = models.ForeignKey(Subject, related_name="portfolio_items", on_delete=models.PROTECT, null=True, blank=True)
    assessment = models.ForeignKey(Assessment, related_name="portfolio_items", on_delete=models.SET_NULL, null=True, blank=True)
    project_milestone = models.ForeignKey(ProjectMilestone, related_name="portfolio_items", on_delete=models.SET_NULL, null=True, blank=True)
    project_team = models.ForeignKey(ProjectTeam, related_name="portfolio_items", on_delete=models.SET_NULL, null=True, blank=True)
    learning_outcome = models.ForeignKey(LearningOutcome, related_name="portfolio_items", on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    attachment = models.FileField(upload_to="student-portfolios/%Y/", null=True, blank=True)
    external_url = models.URLField(blank=True)
    reflection_notes = models.TextField(blank=True)
    teacher_feedback = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("submitted", "Submitted"), ("verified", "Verified")], default="draft")
    uploaded_by = models.ForeignKey(User, related_name="uploaded_portfolio_items", on_delete=models.SET_NULL, null=True, blank=True)
    verified_by = models.ForeignKey(User, related_name="verified_portfolio_items", on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-term__academic_year__start_date", "-created_at"]

    def clean(self):
        if self.stream_id and self.stream.academic_year_id != self.term.academic_year_id:
            raise ValidationError({"stream": "Portfolio stream and term must belong to the same academic year."})
        if self.assessment_id:
            if self.assessment.term_id != self.term_id:
                raise ValidationError({"assessment": "Assessment and portfolio item must belong to the same term."})
            if self.subject_id and self.assessment.subject_id != self.subject_id:
                raise ValidationError({"subject": "Subject must match the selected assessment."})
        if self.project_milestone_id:
            if not self.assessment_id:
                raise ValidationError({"assessment": "Choose the milestone's project assessment."})
            elif self.project_milestone.assessment_id != self.assessment_id:
                raise ValidationError({"project_milestone": "Milestone must belong to the selected assessment."})
        if self.project_team_id:
            if not self.assessment_id or self.project_team.assessment_id != self.assessment_id:
                raise ValidationError({"project_team": "Project team must belong to the selected assessment."})
            if not self.project_team.members.filter(student=self.student, is_deleted=False).exists():
                raise ValidationError({"student": "Learner is not a member of the selected project team."})
        if self.status == "verified" and not self.verified_by_id:
            raise ValidationError({"verified_by": "A verified portfolio item requires a verifier."})

    def save(self, *args, **kwargs):
        if self.status == "verified" and self.verified_by_id and not self.verified_at:
            self.verified_at = timezone.now()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.title}"


class TeacherObservation(BaseModel):
    CATEGORY_CHOICES = [
        ("participation", "Participation"), ("leadership", "Leadership"), ("confidence", "Confidence"),
        ("practical_behaviour", "Behaviour during practicals"), ("communication", "Communication"),
        ("innovation", "Innovation"), ("support", "Learner support"), ("general", "General"),
    ]
    student = models.ForeignKey(Student, related_name="teacher_observations", on_delete=models.CASCADE)
    term = models.ForeignKey(Term, related_name="teacher_observations", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="teacher_observations", on_delete=models.PROTECT, null=True, blank=True)
    assessment = models.ForeignKey(Assessment, related_name="teacher_observations", on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="general")
    observation_date = models.DateField(default=timezone.localdate)
    note = models.TextField()
    competencies = models.ManyToManyField(Competency, related_name="teacher_observations", blank=True)
    skills = models.ManyToManyField(Skill, related_name="teacher_observations", blank=True)
    values = models.ManyToManyField(CurriculumValue, related_name="teacher_observations", blank=True)
    observed_by = models.ForeignKey(User, related_name="learner_observations", on_delete=models.SET_NULL, null=True, blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-observation_date", "-created_at"]

    def clean(self):
        if not self.term.start_date <= self.observation_date <= self.term.end_date:
            raise ValidationError({"observation_date": "Observation date must fall inside the selected term."})
        if self.assessment_id:
            if self.assessment.term_id != self.term_id:
                raise ValidationError({"assessment": "Assessment and observation must belong to the same term."})
            if self.assessment.stream_id and self.assessment.stream_id != self.student.stream_id:
                raise ValidationError({"student": "Student is not in the assessment stream."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} · {self.get_category_display()} · {self.observation_date}"


class AssessmentReview(BaseModel):
    assessment = models.ForeignKey(Assessment, related_name="reviews", on_delete=models.CASCADE)
    stage = models.CharField(max_length=12, choices=[("hod", "Head of Department"), ("dos", "Director of Studies")])
    decision = models.CharField(max_length=24, choices=[("approved", "Approved"), ("changes_requested", "Changes requested")])
    reviewer = models.ForeignKey(User, related_name="assessment_reviews", on_delete=models.PROTECT)
    comment = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-reviewed_at"]

    def clean(self):
        if self.stage == "hod":
            department_head_id = self.assessment.subject.department.head_id if self.assessment.subject.department_id else None
            if not (self.reviewer.is_superuser or self.reviewer.role in {"super_admin", "headteacher", "director_of_studies"} or self.reviewer_id == department_head_id):
                raise ValidationError({"reviewer": "Reviewer is not the subject HOD or an academic manager."})
        elif self.stage == "dos" and not (self.reviewer.is_superuser or self.reviewer.role in {"super_admin", "headteacher", "director_of_studies"}):
            raise ValidationError({"reviewer": "DOS review requires an academic manager."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.assessment} · {self.get_stage_display()} · {self.get_decision_display()}"
