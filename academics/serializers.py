from rest_framework import serializers

from .models import (
    AcademicYear, CalendarEvent, ClassLevel, Department, SchoolProfile,
    Stream, Subject, SubjectAllocation, SubjectCombination, Term,
)


class BaseAcademicSerializer(serializers.ModelSerializer):
    class Meta:
        read_only_fields = ("created_at", "updated_at", "deleted_at", "is_deleted")


def serializer_for(model):
    meta = type("Meta", (), {"model": model, "fields": "__all__", "read_only_fields": BaseAcademicSerializer.Meta.read_only_fields})
    return type(f"{model.__name__}Serializer", (BaseAcademicSerializer,), {"Meta": meta})


SchoolProfileSerializer = serializer_for(SchoolProfile)
AcademicYearSerializer = serializer_for(AcademicYear)
TermSerializer = serializer_for(Term)
DepartmentSerializer = serializer_for(Department)
ClassLevelSerializer = serializer_for(ClassLevel)
StreamSerializer = serializer_for(Stream)
SubjectSerializer = serializer_for(Subject)
SubjectCombinationSerializer = serializer_for(SubjectCombination)
SubjectAllocationSerializer = serializer_for(SubjectAllocation)
CalendarEventSerializer = serializer_for(CalendarEvent)
