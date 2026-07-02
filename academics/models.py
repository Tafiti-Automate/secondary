from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from accounts.models import User
from config.models import BaseModel


class SchoolProfile(BaseModel):
    name = models.CharField(max_length=180, default="My Secondary School")
    motto = models.CharField(max_length=180, blank=True)
    emis_number = models.CharField("EMIS number", max_length=40, blank=True)
    centre_number = models.CharField("UNEB centre number", max_length=40, blank=True)
    ownership = models.CharField(max_length=30, choices=[("government", "Government"), ("private", "Private"), ("community", "Community"), ("faith", "Faith-based")], default="private")
    address = models.CharField(max_length=255, blank=True)
    district = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="school/", blank=True, null=True)
    headteacher_name = models.CharField(max_length=120, blank=True)
    report_footer = models.TextField(blank=True)

    class Meta:
        verbose_name = "school profile"

    def __str__(self):
        return self.name


class AcademicYear(BaseModel):
    name = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]

    def clean(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "The academic year must end after it starts."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_current:
            AcademicYear.objects.exclude(pk=self.pk).update(is_current=False)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Term(BaseModel):
    academic_year = models.ForeignKey(AcademicYear, related_name="terms", on_delete=models.PROTECT)
    name = models.CharField(max_length=30)
    number = models.PositiveSmallIntegerField(default=1, choices=[(1, "Term I"), (2, "Term II"), (3, "Term III")])
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-academic_year__start_date", "number"]
        constraints = [models.UniqueConstraint(fields=["academic_year", "number"], condition=Q(is_deleted=False), name="unique_active_term_number")]

    def clean(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "The term must end after it starts."})
        if self.academic_year_id and (self.start_date < self.academic_year.start_date or self.end_date > self.academic_year.end_date):
            raise ValidationError("Term dates must fall inside the academic year.")

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_current:
            Term.objects.exclude(pk=self.pk).update(is_current=False)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.academic_year} · {self.name}"


class Department(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=12, blank=True)
    description = models.TextField(blank=True)
    head = models.ForeignKey(User, related_name="headed_departments", on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={"role": "teacher"})

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ClassLevel(BaseModel):
    name = models.CharField(max_length=50, unique=True)
    curriculum = models.CharField(max_length=30, choices=[("lower", "Lower Secondary CBC"), ("upper", "Upper Secondary")])
    level = models.PositiveIntegerField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["level"]

    def __str__(self):
        return self.name


class Stream(BaseModel):
    name = models.CharField(max_length=30)
    class_level = models.ForeignKey(ClassLevel, related_name="streams", on_delete=models.PROTECT)
    academic_year = models.ForeignKey(AcademicYear, related_name="streams", on_delete=models.PROTECT)
    class_teacher = models.ForeignKey(User, related_name="managed_streams", on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={"role": "teacher"})
    room_name = models.CharField(max_length=50, blank=True)
    capacity = models.PositiveIntegerField(default=60)

    class Meta:
        ordering = ["class_level__level", "name"]
        constraints = [models.UniqueConstraint(fields=["name", "class_level", "academic_year"], condition=Q(is_deleted=False), name="unique_active_stream")]

    def __str__(self):
        return f"{self.class_level} {self.name}"


class Subject(BaseModel):
    SUBJECT_TYPES = [("core", "Core"), ("elective", "Elective"), ("subsidiary", "Subsidiary"), ("vocational", "Vocational")]
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=30, blank=True)
    code = models.CharField(max_length=20, unique=True)
    uneb_code = models.CharField("UNEB code", max_length=20, blank=True)
    department = models.ForeignKey(Department, related_name="subjects", on_delete=models.SET_NULL, null=True, blank=True)
    is_core = models.BooleanField(default=True)
    subject_type = models.CharField(max_length=20, choices=SUBJECT_TYPES, default="core")
    curriculum_level = models.CharField(max_length=20, choices=[("lower", "Lower Secondary"), ("upper", "Upper Secondary"), ("both", "Both")], default="both")
    pass_mark = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.is_core = self.subject_type == "core"
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} · {self.name}"


class SubjectCombination(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    curriculum_level = models.CharField(max_length=20, choices=[("lower", "Lower Secondary"), ("upper", "Upper Secondary")], default="upper")
    subjects = models.ManyToManyField(Subject, related_name="combinations")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.code or self.name


class SubjectAllocation(BaseModel):
    teacher = models.ForeignKey(User, related_name="subject_allocations", on_delete=models.PROTECT, limit_choices_to={"role": "teacher"})
    subject = models.ForeignKey(Subject, related_name="allocations", on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, related_name="subject_allocations", on_delete=models.PROTECT)
    term = models.ForeignKey(Term, related_name="subject_allocations", on_delete=models.PROTECT)
    lessons_per_week = models.PositiveSmallIntegerField(default=4)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["stream__class_level__level", "subject__name"]
        constraints = [models.UniqueConstraint(fields=["teacher", "subject", "stream", "term"], condition=Q(is_deleted=False), name="unique_active_subject_allocation")]

    def clean(self):
        if self.teacher_id and self.teacher.role not in {"teacher", "director_of_studies", "headteacher", "super_admin"}:
            raise ValidationError({"teacher": "Only academic staff can receive subject allocations."})
        if self.term_id and self.stream_id and self.term.academic_year_id != self.stream.academic_year_id:
            raise ValidationError("The allocation term and stream must belong to the same academic year.")

    def __str__(self):
        return f"{self.teacher} · {self.subject} · {self.stream}"


class CalendarEvent(BaseModel):
    term = models.ForeignKey(Term, related_name="calendar_events", on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    category = models.CharField(max_length=30, choices=[("academic", "Academic"), ("exam", "Examination"), ("holiday", "Holiday"), ("meeting", "Meeting"), ("activity", "School activity")], default="academic")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["start_date"]

    def __str__(self):
        return self.title
