from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from academics.models import SubjectAllocation
from students.models import Student, StudentSubjectRegistration
from .models import Room, TimeSlot, TimetableEntry, TimetableGenerationRun


@transaction.atomic
def generate_conflict_free_timetable(term, requested_by, dry_run=False):
    """Greedy, deterministic scheduler that preserves every existing timetable entry."""
    run = TimetableGenerationRun.objects.create(term=term, requested_by=requested_by, status="running")
    slots = list(TimeSlot.objects.filter(slot_type="lesson", is_deleted=False).order_by("display_order", "start_time"))
    rooms = list(Room.objects.filter(is_active=True, is_deleted=False).order_by("capacity", "name"))
    existing = list(TimetableEntry.objects.filter(term=term, is_deleted=False).select_related("stream", "subject", "teacher", "room", "time_slot"))
    used_stream = {(item.stream_id, item.day_of_week, item.time_slot_id) for item in existing}
    used_teacher = {(item.teacher_id, item.day_of_week, item.time_slot_id) for item in existing if item.teacher_id}
    used_room = {(item.room_id, item.day_of_week, item.time_slot_id) for item in existing if item.room_id}
    subject_day = defaultdict(int)
    for item in existing:
        if item.subject_id:
            subject_day[(item.stream_id, item.subject_id, item.day_of_week)] += 1

    allocations = SubjectAllocation.objects.filter(
        term=term, is_active=True, is_deleted=False,
    ).select_related("stream", "stream__academic_year", "subject", "teacher").select_related("scheduling_requirement").order_by(
        "stream__class_level__level", "stream__name", "-lessons_per_week", "subject__name",
    )
    planned, unresolved = [], []
    for allocation in allocations:
        already = sum(1 for item in existing if item.stream_id == allocation.stream_id and item.subject_id == allocation.subject_id and item.teacher_id == allocation.teacher_id)
        needed = max(allocation.lessons_per_week - already, 0)
        requirement = getattr(allocation, "scheduling_requirement", None)
        days = requirement.allowed_days if requirement and requirement.allowed_days else [1, 2, 3, 4, 5]
        daily_max = requirement.max_lessons_per_day if requirement else 1
        registered = StudentSubjectRegistration.objects.filter(
            enrollment__stream=allocation.stream, enrollment__academic_year=term.academic_year,
            enrollment__status="enrolled", enrollment__is_deleted=False,
            subject=allocation.subject, status="active", is_deleted=False,
        ).count()
        headcount = registered or Student.objects.filter(stream=allocation.stream, is_active=True, is_deleted=False).count()

        for lesson_number in range(needed):
            chosen = None
            for day in days:
                if subject_day[(allocation.stream_id, allocation.subject_id, day)] >= daily_max:
                    continue
                for slot in slots:
                    if (allocation.stream_id, day, slot.pk) in used_stream or (allocation.teacher_id, day, slot.pk) in used_teacher:
                        continue
                    candidates = rooms
                    if requirement and requirement.required_room_type:
                        candidates = [room for room in candidates if room.room_type == requirement.required_room_type]
                    candidates = [room for room in candidates if room.capacity >= headcount and (room.pk, day, slot.pk) not in used_room]
                    if requirement and requirement.preferred_room_id and requirement.preferred_room in candidates:
                        candidates = [requirement.preferred_room, *[room for room in candidates if room.pk != requirement.preferred_room_id]]
                    room = candidates[0] if candidates else None
                    if rooms and not room:
                        continue
                    chosen = (day, slot, room)
                    break
                if chosen:
                    break
            if not chosen:
                unresolved.append({"allocation": allocation.pk, "stream": str(allocation.stream), "subject": str(allocation.subject), "lesson": lesson_number + 1, "reason": "No conflict-free teacher, stream, period and suitable room combination."})
                continue
            day, slot, room = chosen
            used_stream.add((allocation.stream_id, day, slot.pk))
            used_teacher.add((allocation.teacher_id, day, slot.pk))
            if room:
                used_room.add((room.pk, day, slot.pk))
            subject_day[(allocation.stream_id, allocation.subject_id, day)] += 1
            data = {"stream": str(allocation.stream), "subject": str(allocation.subject), "teacher": str(allocation.teacher), "day": day, "slot": slot.name, "room": str(room or "")}
            planned.append(data)
            if not dry_run:
                TimetableEntry.objects.create(term=term, stream=allocation.stream, day_of_week=day, time_slot=slot, subject=allocation.subject, teacher=allocation.teacher, room=room, notes="Auto-generated")

    run.generated_count = len(planned)
    run.unresolved_count = len(unresolved)
    run.status = "simulated" if dry_run else ("partial" if unresolved else "completed")
    run.result = {"planned": planned, "unresolved": unresolved, "preserved_existing": len(existing), "dry_run": dry_run}
    run.completed_at = timezone.now()
    run.save(update_fields=["generated_count", "unresolved_count", "status", "result", "completed_at", "updated_at"])
    return run
