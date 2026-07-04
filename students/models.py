from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from academics.models import AcademicYear, Stream, Subject, SubjectCombination, Term
from config.models import BaseModel


class Student(BaseModel):
    STATUS_CHOICES = [("active", "Active"), ("graduated", "Graduated"), ("transferred", "Transferred"), ("withdrawn", "Withdrawn"), ("suspended", "Suspended")]
    student_number = models.CharField(max_length=24, unique=True, null=True, blank=True, help_text="Permanent learner identifier used across admission years.")
    admission_number = models.CharField(max_length=24, unique=True, blank=True)
    user = models.OneToOneField(User, related_name="student_profile", on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={"role": "student"})
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    other_names = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=[("male", "Male"), ("female", "Female")])
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=60, default="Ugandan")
    national_id = models.CharField("NIN", max_length=30, blank=True)
    religion = models.CharField(max_length=50, blank=True)
    photo = models.ImageField(upload_to="students/photos/%Y/", blank=True, null=True)
    stream = models.ForeignKey(Stream, related_name="students", on_delete=models.SET_NULL, null=True, blank=True)
    parent = models.ForeignKey(User, related_name="children", on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={"role": "parent"})
    medical_information = models.TextField(blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    allergies = models.TextField(blank=True)
    special_needs = models.TextField(blank=True)
    previous_school = models.CharField(max_length=200, blank=True)
    previous_school_details = models.TextField(blank=True)
    subject_combination = models.ForeignKey(SubjectCombination, related_name="students", on_delete=models.SET_NULL, null=True, blank=True)
    address = models.TextField(blank=True)
    district = models.CharField(max_length=80, blank=True)
    house = models.CharField(max_length=50, blank=True)
    date_admitted = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    is_boarding = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        indexes = [models.Index(fields=["student_number"]), models.Index(fields=["admission_number"]), models.Index(fields=["status", "stream"])]

    def clean(self):
        if self.date_of_birth and self.date_of_birth >= timezone.localdate():
            raise ValidationError({"date_of_birth": "Date of birth must be in the past."})
        if self.user_id and self.user.role != "student":
            raise ValidationError({"user": "The linked account must have the Student role."})
        if self.parent_id and self.parent.role != "parent":
            raise ValidationError({"parent": "The linked account must have the Parent role."})

    def save(self, *args, **kwargs):
        if not self.student_number:
            prefix = "STU-"
            latest = Student.objects.filter(student_number__startswith=prefix).order_by("student_number").last()
            try:
                sequence = int(latest.student_number.removeprefix(prefix)) + 1 if latest else 1
            except (ValueError, AttributeError):
                sequence = Student.objects.filter(student_number__startswith=prefix).count() + 1
            candidate = f"{prefix}{sequence:06d}"
            while Student.objects.filter(student_number=candidate).exclude(pk=self.pk).exists():
                sequence += 1
                candidate = f"{prefix}{sequence:06d}"
            self.student_number = candidate
        if not self.admission_number:
            year = (self.date_admitted or timezone.localdate()).year
            prefix = f"{year}/"
            latest = Student.objects.filter(admission_number__startswith=prefix).order_by("admission_number").last()
            try:
                sequence = int(latest.admission_number.split("/")[-1]) + 1 if latest else 1
            except (ValueError, AttributeError):
                sequence = Student.objects.filter(admission_number__startswith=prefix).count() + 1
            candidate = f"{prefix}{sequence:04d}"
            while Student.objects.filter(admission_number=candidate).exclude(pk=self.pk).exists():
                sequence += 1
                candidate = f"{prefix}{sequence:04d}"
            self.admission_number = candidate
        self.is_active = self.status == "active"
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return " ".join(filter(None, [self.first_name, self.other_names, self.last_name]))

    @property
    def avatar_atlas_position(self) -> str:
        """Return a stable tile position in the 6x6 static demo avatar atlas."""
        index = ((self.pk or 1) - 1) % 36
        return f"{(index % 6) * 20}% {(index // 6) * 20}%"

    def __str__(self):
        return f"{self.admission_number} · {self.full_name}"


class Guardian(BaseModel):
    user = models.OneToOneField(User, related_name="guardian_profile", on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={"role": "parent"})
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=30)
    alternate_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    employer = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)
    national_id = models.CharField("NIN", max_length=30, blank=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name


class StudentGuardian(BaseModel):
    student = models.ForeignKey(Student, related_name="guardian_links", on_delete=models.CASCADE)
    guardian = models.ForeignKey(Guardian, related_name="student_links", on_delete=models.CASCADE)
    relationship = models.CharField(max_length=30, choices=[("father", "Father"), ("mother", "Mother"), ("guardian", "Guardian"), ("sibling", "Sibling"), ("other", "Other")], default="guardian")
    is_primary = models.BooleanField(default=False)
    receives_reports = models.BooleanField(default=True)
    receives_alerts = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "guardian"], condition=Q(is_deleted=False), name="unique_active_student_guardian")]

    def save(self, *args, **kwargs):
        if self.is_primary:
            StudentGuardian.objects.filter(student=self.student, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.full_name} · {self.guardian.full_name}"


class Enrollment(BaseModel):
    student = models.ForeignKey(Student, related_name="enrollments", on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, related_name="enrollments", on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, related_name="enrollments", on_delete=models.PROTECT)
    subject_combination = models.ForeignKey(SubjectCombination, related_name="enrollments", on_delete=models.SET_NULL, null=True, blank=True)
    roll_number = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[("enrolled", "Enrolled"), ("promoted", "Promoted"), ("repeated", "Repeated"), ("completed", "Completed"), ("withdrawn", "Withdrawn")], default="enrolled")
    enrolled_on = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-academic_year__start_date", "stream", "roll_number"]
        constraints = [models.UniqueConstraint(fields=["student", "academic_year"], condition=Q(is_deleted=False), name="unique_active_student_enrollment")]

    def clean(self):
        if self.stream_id and self.academic_year_id and self.stream.academic_year_id != self.academic_year_id:
            raise ValidationError("The stream must belong to the selected academic year.")

    def __str__(self):
        return f"{self.student} · {self.academic_year}"


class StudentSubjectRegistration(BaseModel):
    enrollment = models.ForeignKey(Enrollment, related_name="subject_registrations", on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, related_name="student_registrations", on_delete=models.PROTECT)
    category = models.CharField(max_length=20, choices=[("core", "Core"), ("elective", "Elective"), ("principal", "Principal"), ("subsidiary", "Subsidiary")], default="core")
    status = models.CharField(max_length=20, choices=[("active", "Active"), ("dropped", "Dropped"), ("completed", "Completed")], default="active")
    registered_on = models.DateField(default=timezone.localdate)
    dropped_on = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ["subject__name"]
        constraints = [models.UniqueConstraint(fields=["enrollment", "subject"], condition=Q(is_deleted=False), name="unique_active_enrollment_subject")]

    def clean(self):
        if not self.enrollment_id or not self.subject_id:
            return
        curriculum = self.enrollment.stream.class_level.curriculum
        expected = "lower" if curriculum == "lower" else "upper"
        if self.subject.curriculum_level not in {expected, "both"}:
            raise ValidationError({"subject": f"This subject is not available for {expected} secondary."})
        level = self.enrollment.stream.class_level.level
        if self.status == "active" and level in {1, 2, 3, 4}:
            maximum = 12 if level in {1, 2} else 9
            active_count = StudentSubjectRegistration.objects.filter(
                enrollment=self.enrollment,
                status="active",
                is_deleted=False,
            ).exclude(pk=self.pk).count()
            if active_count >= maximum:
                raise ValidationError(f"{self.enrollment.stream.class_level} permits at most {maximum} active subjects.")
        if self.status == "dropped" and not self.dropped_on:
            raise ValidationError({"dropped_on": "Record the date when a subject is dropped."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.enrollment.student} · {self.subject}"


class StudentMovement(BaseModel):
    student = models.ForeignKey(Student, related_name="movements", on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=24, choices=[("transfer_in", "Transferred in"), ("transfer_out", "Transferred out"), ("withdrawal", "Withdrawn"), ("suspension", "Suspended"), ("reinstatement", "Reinstated"), ("graduation", "Graduated")])
    effective_date = models.DateField(default=timezone.localdate)
    previous_school = models.CharField(max_length=180, blank=True)
    destination = models.CharField(max_length=180, blank=True)
    reason = models.TextField(blank=True)
    reference_number = models.CharField(max_length=60, blank=True)
    document = models.FileField(upload_to="student-movements/%Y/", null=True, blank=True)
    authorised_by = models.ForeignKey(User, related_name="authorised_student_movements", on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["-effective_date", "-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        status_map = {"transfer_out": "transferred", "withdrawal": "withdrawn", "suspension": "suspended", "graduation": "graduated", "reinstatement": "active", "transfer_in": "active"}
        if self.movement_type in status_map:
            Student.objects.filter(pk=self.student_id).update(status=status_map[self.movement_type], is_active=status_map[self.movement_type] == "active")

    def __str__(self):
        return f"{self.student} · {self.get_movement_type_display()}"


class StudentPromotion(BaseModel):
    student = models.ForeignKey(Student, related_name="promotions", on_delete=models.CASCADE)
    from_stream = models.ForeignKey(Stream, related_name="promotions_from", on_delete=models.SET_NULL, null=True, blank=True)
    to_stream = models.ForeignKey(Stream, related_name="promotions_to", on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.CharField(max_length=20)
    term = models.ForeignKey(Term, related_name="promotion_decisions", on_delete=models.SET_NULL, null=True, blank=True)
    decision = models.CharField(max_length=20, choices=[("promoted", "Promoted"), ("repeated", "Repeat class"), ("completed", "Completed S6"), ("deferred", "Decision deferred")], default="promoted")
    promoted = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, related_name="approved_promotions", on_delete=models.SET_NULL, null=True, blank=True)
    decision_date = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-decision_date"]

    def save(self, *args, **kwargs):
        self.promoted = self.decision == "promoted"
        super().save(*args, **kwargs)
        if self.to_stream_id and self.decision in {"promoted", "repeated"}:
            Student.objects.filter(pk=self.student_id).update(stream=self.to_stream, status="active", is_active=True)
        elif self.decision == "completed":
            StudentMovement.objects.update_or_create(
                student=self.student,
                movement_type="graduation",
                effective_date=self.decision_date,
                is_deleted=False,
                defaults={
                    "reason": self.remarks or "Completed final academic level.",
                    "authorised_by": self.approved_by,
                },
            )

    def __str__(self):
        return f"{self.student} · {self.get_decision_display()}"


class StudentAccommodation(BaseModel):
    CATEGORY_CHOICES = [
        ("learning", "Learning support"), ("visual", "Visual access"),
        ("hearing", "Hearing access"), ("mobility", "Mobility access"),
        ("medical", "Medical support"), ("language", "Language support"),
        ("assessment", "Assessment access arrangement"), ("other", "Other"),
    ]
    student = models.ForeignKey(Student, related_name="accommodations", on_delete=models.CASCADE)
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=160)
    need_description = models.TextField()
    support_strategy = models.TextField()
    start_date = models.DateField(default=timezone.localdate)
    review_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[("active", "Active"), ("review", "Due for review"), ("ended", "Ended")], default="active")
    confidential = models.BooleanField(default=True)
    recorded_by = models.ForeignKey(User, related_name="recorded_student_accommodations", on_delete=models.SET_NULL, null=True)
    reviewed_by = models.ForeignKey(User, related_name="reviewed_student_accommodations", on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date", "category", "title"]

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot precede the accommodation start date."})
        if self.review_date and self.review_date < self.start_date:
            raise ValidationError({"review_date": "Review date cannot precede the accommodation start date."})
        if self.status == "ended" and not self.end_date:
            raise ValidationError({"end_date": "An ended accommodation requires an end date."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.full_name} · {self.title}"


class StudentInterest(BaseModel):
    CATEGORY_CHOICES = [
        ("academic", "Academic"), ("creative", "Creative arts"),
        ("sport", "Sport"), ("vocational", "Vocational"),
        ("technology", "Technology"), ("community", "Community service"),
        ("leadership", "Leadership"), ("other", "Other"),
    ]
    student = models.ForeignKey(Student, related_name="interests", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES, default="academic")
    engagement_level = models.CharField(max_length=20, choices=[("exploring", "Exploring"), ("active", "Actively engaged"), ("advanced", "Advanced")], default="exploring")
    notes = models.TextField(blank=True)
    first_observed = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)
    recorded_by = models.ForeignKey(User, related_name="recorded_student_interests", on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["category", "name"]
        constraints = [
            models.UniqueConstraint(fields=["student", "name"], condition=Q(is_deleted=False), name="unique_active_student_interest")
        ]

    def __str__(self):
        return f"{self.student.full_name} · {self.name}"


class StudentAchievement(BaseModel):
    CATEGORY_CHOICES = [
        ("academic", "Academic"), ("project", "Project"), ("leadership", "Leadership"),
        ("sport", "Sport"), ("arts", "Creative arts"), ("vocational", "Vocational"),
        ("community", "Community service"), ("innovation", "Innovation"), ("other", "Other"),
    ]
    LEVEL_CHOICES = [
        ("school", "School"), ("district", "District"), ("regional", "Regional"),
        ("national", "National"), ("international", "International"),
    ]
    student = models.ForeignKey(Student, related_name="achievements", on_delete=models.CASCADE)
    title = models.CharField(max_length=180)
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES)
    achievement_date = models.DateField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="school")
    issuer = models.CharField(max_length=180, blank=True)
    description = models.TextField(blank=True)
    evidence = models.FileField(upload_to="student-achievements/%Y/", null=True, blank=True)
    external_reference = models.URLField(blank=True)
    verified_by = models.ForeignKey(User, related_name="verified_student_achievements", on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-achievement_date", "title"]

    def clean(self):
        if self.achievement_date and self.achievement_date > timezone.localdate():
            raise ValidationError({"achievement_date": "Achievement date cannot be in the future."})
        if self.verified_by_id and not self.verified_at:
            self.verified_at = timezone.now()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.full_name} · {self.title}"
