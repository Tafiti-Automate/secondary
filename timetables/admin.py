from django.contrib import admin
from .models import Room, TimeSlot, TimetableEntry

admin.site.register([Room, TimeSlot, TimetableEntry])
