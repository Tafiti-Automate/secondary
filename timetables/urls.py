from django.urls import path, reverse_lazy
from .forms import RoomForm, TimeSlotForm, TimetableEntryForm
from .models import Room, TimeSlot, TimetableEntry
from .views import SetupCreateView, SetupDeleteView, SetupTableView, SetupUpdateView, TimetableGridView

app_name = "timetables"
urlpatterns = [path("", TimetableGridView.as_view(), name="grid")]

SETUP = {
    "entries": (TimetableEntry, TimetableEntryForm, ("Day", "Period", "Stream", "Subject", "Teacher", "Room"), ("get_day_of_week_display", "time_slot", "stream", "subject", "teacher", "room"), "Timetable entries"),
    "rooms": (Room, RoomForm, ("Room", "Type", "Capacity", "Location", "Active"), ("name", "get_room_type_display", "capacity", "location", "is_active"), "Rooms"),
    "time-slots": (TimeSlot, TimeSlotForm, ("Period", "Starts", "Ends", "Type", "Order"), ("name", "start_time", "end_time", "get_slot_type_display", "display_order"), "Time slots"),
}
for slug, (model, form, columns, fields, title) in SETUP.items():
    list_name, add_name, edit_name, delete_name = f"{slug}-list", f"{slug}-add", f"{slug}-edit", f"{slug}-delete"
    success = reverse_lazy(f"timetables:{list_name}")
    urlpatterns += [
        path(f"manage/{slug}/", SetupTableView.as_view(model=model, columns=columns, field_paths=fields, page_title=title, create_url_name=f"timetables:{add_name}", edit_url_name=f"timetables:{edit_name}", delete_url_name=f"timetables:{delete_name}"), name=list_name),
        path(f"manage/{slug}/add/", SetupCreateView.as_view(model=model, form_class=form, success_url=success, extra_context={"page_title": f"Add {model._meta.verbose_name}", "eyebrow": "Timetable setup", "submit_label": "Save record"}), name=add_name),
        path(f"manage/{slug}/<int:pk>/edit/", SetupUpdateView.as_view(model=model, form_class=form, success_url=success, extra_context={"page_title": f"Edit {model._meta.verbose_name}", "eyebrow": "Timetable setup", "submit_label": "Save changes"}), name=edit_name),
        path(f"manage/{slug}/<int:pk>/delete/", SetupDeleteView.as_view(model=model, success_url_name=f"timetables:{list_name}"), name=delete_name),
    ]
