from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from academics.models import Stream, Subject, SubjectAllocation, Term
from accounts.models import User
from config.models import BaseModel


class Room(BaseModel):
    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=20, blank=True)
    room_type = models.CharField(max_length=30, choices=[("classroom", "Classroom"), ("laboratory", "Laboratory"), ("computer", "Computer laboratory"), ("workshop", "Workshop"), ("hall", "Hall"), ("field", "Sports field")], default="classroom")
    capacity = models.PositiveIntegerField(default=60)
    location = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TimeSlot(BaseModel):
    name = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_type = models.CharField(max_length=20, choices=[("lesson", "Lesson"), ("break", "Break"), ("lunch", "Lunch"), ("assembly", "Assembly"), ("prep", "Prep")], default="lesson")
    display_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["display_order", "start_time"]

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})

    def __str__(self):
        return f"{self.name} ({self.start_time:%H:%M}–{self.end_time:%H:%M})"


class TimetableEntry(BaseModel):
    DAYS = [(1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"), (5, "Friday"), (6, "Saturday"), (7, "Sunday")]
    term = models.ForeignKey(Term, related_name="timetable_entries", on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, related_name="timetable_entries", on_delete=models.PROTECT)
    day_of_week = models.PositiveSmallIntegerField(choices=DAYS)
    time_slot = models.ForeignKey(TimeSlot, related_name="timetable_entries", on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, related_name="timetable_entries", on_delete=models.PROTECT, null=True, blank=True)
    teacher = models.ForeignKey(User, related_name="timetable_entries", on_delete=models.PROTECT, null=True, blank=True, limit_choices_to={"role": "teacher"})
    room = models.ForeignKey(Room, related_name="timetable_entries", on_delete=models.PROTECT, null=True, blank=True)
    notes = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ["day_of_week", "time_slot__display_order", "stream"]
        constraints = [models.UniqueConstraint(fields=["term", "stream", "day_of_week", "time_slot"], condition=Q(is_deleted=False), name="unique_active_stream_timetable_slot")]

    def clean(self):
        if self.stream_id and self.term_id and self.stream.academic_year_id != self.term.academic_year_id:
            raise ValidationError("The stream and term must belong to the same academic year.")
        conflicts = TimetableEntry.objects.filter(term=self.term, day_of_week=self.day_of_week, time_slot=self.time_slot, is_deleted=False).exclude(pk=self.pk)
        errors = []
        if self.teacher_id and conflicts.filter(teacher=self.teacher).exists():
            errors.append("The teacher already has a lesson in this period.")
        if self.room_id and conflicts.filter(room=self.room).exists():
            errors.append("The room is already allocated in this period.")
        if conflicts.filter(stream=self.stream).exists():
            errors.append("The stream already has an activity in this period.")
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_day_of_week_display()} · {self.time_slot} · {self.stream}"


class SchedulingRequirement(BaseModel):
    allocation = models.OneToOneField(SubjectAllocation, related_name="scheduling_requirement", on_delete=models.CASCADE)
    required_room_type = models.CharField(max_length=30, choices=[("", "Any suitable room"), *Room._meta.get_field("room_type").choices], blank=True)
    preferred_room = models.ForeignKey(Room, related_name="preferred_scheduling_requirements", on_delete=models.SET_NULL, null=True, blank=True)
    allowed_days = models.JSONField(default=list, blank=True, help_text="Weekday numbers, for example [1,2,3,4,5]. Empty means Monday–Friday.")
    max_lessons_per_day = models.PositiveSmallIntegerField(default=1)
    notes = models.TextField(blank=True)

    def clean(self):
        invalid = [day for day in self.allowed_days if day not in range(1, 7)]
        if invalid:
            raise ValidationError({"allowed_days": "Days must be numbers from 1 (Monday) to 6 (Saturday)."})
        if self.preferred_room_id and self.required_room_type and self.preferred_room.room_type != self.required_room_type:
            raise ValidationError({"preferred_room": "Preferred room does not match the required room type."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Scheduling · {self.allocation}"


class TimetableGenerationRun(BaseModel):
    term = models.ForeignKey(Term, related_name="timetable_generation_runs", on_delete=models.PROTECT)
    requested_by = models.ForeignKey(User, related_name="timetable_generation_runs", on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=[("running", "Running"), ("completed", "Completed"), ("partial", "Completed with gaps"), ("simulated", "Simulation"), ("failed", "Failed")], default="running")
    generated_count = models.PositiveIntegerField(default=0)
    unresolved_count = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.term} · {self.get_status_display()} · {self.created_at:%d %b %Y %H:%M}"
