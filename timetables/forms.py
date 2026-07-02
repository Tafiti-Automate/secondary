from config.forms import StyledModelForm
from .models import Room, TimeSlot, TimetableEntry


class RoomForm(StyledModelForm):
    class Meta:
        model = Room
        fields = ("name", "code", "room_type", "capacity", "location", "is_active")


class TimeSlotForm(StyledModelForm):
    class Meta:
        model = TimeSlot
        fields = ("name", "start_time", "end_time", "slot_type", "display_order")


class TimetableEntryForm(StyledModelForm):
    class Meta:
        model = TimetableEntry
        fields = ("term", "stream", "day_of_week", "time_slot", "subject", "teacher", "room", "notes")
