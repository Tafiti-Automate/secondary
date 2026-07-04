from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, TemplateView, UpdateView

from academics.models import Stream, Term
from config.crud import AuditedFormMixin, SoftDeleteView
from config.mixins import AcademicManagerRequiredMixin
from config.tables import ModelTableView
from .forms import RoomForm, SchedulingRequirementForm, TimeSlotForm, TimetableEntryForm
from .models import Room, SchedulingRequirement, TimeSlot, TimetableEntry, TimetableGenerationRun
from .services import generate_conflict_free_timetable


class TimetableGridView(LoginRequiredMixin, TemplateView):
    template_name = "timetables/grid.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        term_id = self.request.GET.get("term")
        stream_id = self.request.GET.get("stream")
        entries = TimetableEntry.objects.filter(is_deleted=False).select_related("term", "stream", "subject", "teacher", "room", "time_slot")
        if term_id:
            entries = entries.filter(term_id=term_id)
        else:
            entries = entries.filter(term__is_current=True)
        if user.role == "teacher":
            entries = entries.filter(teacher=user)
        elif user.role == "student" and hasattr(user, "student_profile"):
            entries = entries.filter(stream=user.student_profile.stream)
        elif user.role == "parent":
            entries = entries.filter(Q(stream__students__parent=user) | Q(stream__students__guardian_links__guardian__user=user)).distinct()
        else:
            if not stream_id:
                default_stream = Stream.objects.filter(is_deleted=False, academic_year__is_current=True).order_by("class_level__level", "name").first()
                stream_id = str(default_stream.pk) if default_stream else None
            if stream_id:
                entries = entries.filter(stream_id=stream_id)
        slots = TimeSlot.objects.filter(is_deleted=False).order_by("display_order")
        matrix = []
        entry_map = {(entry.day_of_week, entry.time_slot_id): entry for entry in entries}
        for day, label in TimetableEntry.DAYS[:6]:
            matrix.append({"day": label, "cells": [{"slot": slot, "entry": entry_map.get((day, slot.pk))} for slot in slots]})
        context.update({"matrix": matrix, "slots": slots, "terms": Term.objects.filter(is_deleted=False), "streams": Stream.objects.filter(is_deleted=False), "selected_stream": stream_id})
        return context


class SetupTableView(AcademicManagerRequiredMixin, ModelTableView):
    pass


class SetupCreateView(AcademicManagerRequiredMixin, AuditedFormMixin, CreateView):
    template_name = "shared/form.html"
    audit_action = "create"


class SetupUpdateView(AcademicManagerRequiredMixin, AuditedFormMixin, UpdateView):
    template_name = "shared/form.html"
    audit_action = "update"


class SetupDeleteView(AcademicManagerRequiredMixin, SoftDeleteView):
    pass


class TimetableGenerateView(AcademicManagerRequiredMixin, View):
    template_name = "timetables/generate.html"

    def get(self, request):
        return render(request, self.template_name, {"terms": Term.objects.filter(is_deleted=False), "runs": TimetableGenerationRun.objects.filter(is_deleted=False).select_related("term", "requested_by")[:15]})

    def post(self, request):
        term = get_object_or_404(Term, pk=request.POST.get("term"), is_deleted=False)
        run = generate_conflict_free_timetable(term, request.user, dry_run=request.POST.get("dry_run") == "1")
        if run.unresolved_count:
            messages.warning(request, f"Scheduled {run.generated_count} lesson(s); {run.unresolved_count} could not be placed. Review the run details below.")
        else:
            messages.success(request, f"{'Simulated' if run.status == 'simulated' else 'Scheduled'} {run.generated_count} lesson(s) with no conflicts.")
        return redirect("timetables:generate")
