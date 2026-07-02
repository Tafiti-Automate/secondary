from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from academics.models import Stream, Subject, Term
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
