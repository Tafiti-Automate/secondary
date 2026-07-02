from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone

from academics.models import AcademicYear, ClassLevel, Stream, Subject, Term
from accounts.models import User
from assessments.models import Competency, CompetencyLevel, CurriculumValue, LearningOutcome, Skill
from config.models import BaseModel
from students.models import Student


class ReportCard(BaseModel):
    student = models.ForeignKey(Student, related_name="report_cards", on_delete=models.CASCADE)
    term = models.ForeignKey(Term, related_name="report_cards", on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, related_name="report_cards", on_delete=models.PROTECT)
    ca_weight = models.DecimalField("continuous assessment weight", max_digits=5, decimal_places=2, default=40)
    exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=60)
    assessment_policy = models.ForeignKey("assessments.AssessmentPolicy", related_name="report_cards", on_delete=models.PROTECT, null=True, blank=True)
    total_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    average_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    class_position = models.PositiveIntegerField(null=True, blank=True)
    class_size = models.PositiveIntegerField(default=0)
    attendance_present = models.PositiveIntegerField(default=0)
    attendance_absent = models.PositiveIntegerField(default=0)
    attendance_late = models.PositiveIntegerField(default=0)
    teacher_remark = models.TextField(blank=True)
    dos_remark = models.TextField(blank=True)
    headteacher_comment = models.TextField(blank=True)
    portfolio_summary = models.TextField(blank=True)
    promotion_decision = models.CharField(max_length=20, choices=[("pending", "Pending"), ("promoted", "Promoted"), ("repeated", "Repeat class"), ("completed", "Completed"), ("deferred", "Deferred")], default="pending")
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("reviewed", "Reviewed"), ("published", "Published"), ("locked", "Locked")], default="draft")
    generated_by = models.ForeignKey(User, related_name="generated_report_cards", on_delete=models.SET_NULL, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    has_missing_marks = models.BooleanField(default=False)
    missing_mark_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["student__first_name", "student__last_name"]
        constraints = [models.UniqueConstraint(fields=["student", "term"], condition=Q(is_deleted=False), name="unique_active_student_term_report")]

    @property
    def attendance_total(self):
        return self.attendance_present + self.attendance_absent + self.attendance_late

    @property
    def attendance_percentage(self):
        return round(self.attendance_present / self.attendance_total * 100, 1) if self.attendance_total else 0

    def publish(self):
        if self.has_missing_marks:
            raise ValidationError("This report has missing subject evidence and cannot be published.")
        self.status = "published"
        self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])

    def __str__(self):
        return f"{self.student} · {self.term}"


class ReportSubjectResult(BaseModel):
    report_card = models.ForeignKey(ReportCard, related_name="subject_results", on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, related_name="report_results", on_delete=models.PROTECT)
    continuous_assessment_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    examination_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    final_score = models.DecimalField(max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    grade = models.CharField(max_length=5, blank=True)
    points = models.PositiveSmallIntegerField(null=True, blank=True)
    descriptor = models.CharField(max_length=120, blank=True)
    subject_position = models.PositiveIntegerField(null=True, blank=True)
    teacher_remark = models.CharField(max_length=180, blank=True)
    ongoing_available = models.BooleanField(default=False)
    summative_available = models.BooleanField(default=False)
    summative_required = models.BooleanField(default=True)
    missing_reason = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ["subject__name"]
        constraints = [models.UniqueConstraint(fields=["report_card", "subject"], condition=Q(is_deleted=False), name="unique_active_report_subject")]

    def __str__(self):
        return f"{self.report_card.student} · {self.subject}"

    @property
    def is_complete(self):
        return self.ongoing_available and (self.summative_available or not self.summative_required)


class ReportCompetencyRating(BaseModel):
    report_card = models.ForeignKey(ReportCard, related_name="competency_ratings", on_delete=models.CASCADE)
    competency = models.ForeignKey(Competency, related_name="report_ratings", on_delete=models.PROTECT)
    level = models.ForeignKey(CompetencyLevel, related_name="report_ratings", on_delete=models.PROTECT)
    comment = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ["competency__display_order"]
        constraints = [models.UniqueConstraint(fields=["report_card", "competency"], condition=Q(is_deleted=False), name="unique_active_report_competency")]

    def __str__(self):
        return f"{self.competency} · {self.level}"


class ReportLearningOutcomeRating(BaseModel):
    report_card = models.ForeignKey(ReportCard, related_name="learning_outcome_ratings", on_delete=models.CASCADE)
    outcome = models.ForeignKey(LearningOutcome, related_name="report_ratings", on_delete=models.PROTECT)
    scale_level = models.ForeignKey(CompetencyLevel, related_name="report_learning_outcome_ratings", on_delete=models.PROTECT, null=True, blank=True)
    level = models.CharField(max_length=24, blank=True)
    comment = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ["outcome__topic__subject__name", "outcome__display_order"]
        constraints = [models.UniqueConstraint(fields=["report_card", "outcome"], condition=Q(is_deleted=False), name="unique_active_report_learning_outcome")]

    def __str__(self):
        return f"{self.report_card.student} · {self.outcome} · {self.display_level}"

    @property
    def display_level(self):
        if self.scale_level_id:
            return self.scale_level.name
        legacy = dict(LearningOutcomeAssessment.LEVEL_CHOICES)
        return legacy.get(self.level, self.level)


class ReportSkillRating(BaseModel):
    report_card = models.ForeignKey(ReportCard, related_name="skill_ratings", on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, related_name="report_ratings", on_delete=models.PROTECT)
    level = models.ForeignKey(CompetencyLevel, related_name="report_skill_ratings", on_delete=models.PROTECT)
    comment = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ["skill__display_order", "skill__name"]
        constraints = [models.UniqueConstraint(fields=["report_card", "skill"], condition=Q(is_deleted=False), name="unique_active_report_skill")]

    def __str__(self):
        return f"{self.skill} · {self.level}"


class ReportValueRating(BaseModel):
    report_card = models.ForeignKey(ReportCard, related_name="value_ratings", on_delete=models.CASCADE)
    value = models.ForeignKey(CurriculumValue, related_name="report_ratings", on_delete=models.PROTECT)
    level = models.ForeignKey(CompetencyLevel, related_name="report_value_ratings", on_delete=models.PROTECT)
    comment = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ["value__display_order", "value__name"]
        constraints = [models.UniqueConstraint(fields=["report_card", "value"], condition=Q(is_deleted=False), name="unique_active_report_value")]

    def __str__(self):
        return f"{self.value} · {self.level}"


class AcademicTranscript(BaseModel):
    student = models.ForeignKey(Student, related_name="academic_transcripts", on_delete=models.PROTECT)
    serial_number = models.CharField(max_length=32, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("issued", "Issued"), ("void", "Void")], default="draft")
    issued_by = models.ForeignKey(User, related_name="issued_transcripts", on_delete=models.SET_NULL, null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.status == "issued" and not self.issued_by_id:
            raise ValidationError({"issued_by": "An issued transcript requires an issuing officer."})

    def save(self, *args, **kwargs):
        if not self.serial_number:
            year = timezone.localdate().year
            prefix = f"TR-{year}-"
            latest = AcademicTranscript.objects.filter(serial_number__startswith=prefix).order_by("serial_number").last()
            try:
                sequence = int(latest.serial_number.rsplit("-", 1)[-1]) + 1 if latest else 1
            except (ValueError, AttributeError):
                sequence = AcademicTranscript.objects.filter(serial_number__startswith=prefix).count() + 1
            self.serial_number = f"{prefix}{sequence:05d}"
        if self.status == "issued" and not self.issued_at:
            self.issued_at = timezone.now()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.serial_number} · {self.student}"


class TranscriptEntry(BaseModel):
    transcript = models.ForeignKey(AcademicTranscript, related_name="entries", on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, related_name="transcript_entries", on_delete=models.PROTECT)
    term = models.ForeignKey(Term, related_name="transcript_entries", on_delete=models.PROTECT, null=True, blank=True)
    class_level = models.ForeignKey(ClassLevel, related_name="transcript_entries", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="transcript_entries", on_delete=models.PROTECT)
    score = models.DecimalField(max_digits=7, decimal_places=2)
    grade = models.CharField(max_length=5, blank=True)
    points = models.PositiveSmallIntegerField(null=True, blank=True)
    remark = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ["academic_year__start_date", "term__number", "subject__name"]
        constraints = [
            models.UniqueConstraint(fields=["transcript", "academic_year", "term", "subject"], condition=Q(is_deleted=False), name="unique_active_transcript_term_subject")
        ]

    def clean(self):
        if self.term_id and self.term.academic_year_id != self.academic_year_id:
            raise ValidationError({"term": "Transcript term and academic year do not match."})
        if self.transcript_id and self.transcript.status == "issued":
            raise ValidationError("Issued transcript entries are read-only.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transcript.student} · {self.academic_year} · {self.subject}"
