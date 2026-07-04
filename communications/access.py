from django.db.models import Q

from academics.models import Stream
from accounts.models import User
from config.mixins import ACADEMIC_MANAGERS
from students.models import Student


def conversation_scope(user):
    people = User.objects.filter(is_active=True, is_deleted=False)
    students = Student.objects.filter(is_active=True, is_deleted=False)
    if user.is_superuser or user.role in ACADEMIC_MANAGERS:
        return people, students
    if user.role in {"parent", "student"}:
        people = people.filter(Q(pk=user.pk) | Q(role__in=["headteacher", "director_of_studies", "teacher"]))
        if user.role == "parent":
            students = students.filter(Q(parent=user) | Q(guardian_links__guardian__user=user)).distinct()
        else:
            students = students.filter(user=user)
        return people, students
    if user.role == "teacher":
        streams = Stream.objects.filter(Q(class_teacher=user) | Q(subject_allocations__teacher=user)).distinct()
        students = students.filter(stream__in=streams)
        people = people.filter(
            Q(role__in=ACADEMIC_MANAGERS | {"teacher"}) | Q(student_profile__stream__in=streams) |
            Q(children__stream__in=streams) | Q(guardian_profile__student_links__student__stream__in=streams)
        ).distinct()
        return people, students
    return people.filter(pk=user.pk), students.none()
