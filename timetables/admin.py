from django.contrib import admin
from .models import Room, SchedulingRequirement, TimeSlot, TimetableEntry, TimetableGenerationRun

admin.site.register([Room, TimeSlot, TimetableEntry, SchedulingRequirement, TimetableGenerationRun])
