from rest_framework import viewsets

from config.permissions import IsReadOnlyOrAcademicManager
from .models import (
    AcademicYear, CalendarEvent, ClassLevel, Department, SchoolProfile,
    Stream, Subject, SubjectAllocation, SubjectCombination, Term,
)
from .serializers import (
    AcademicYearSerializer, CalendarEventSerializer, ClassLevelSerializer,
    DepartmentSerializer, SchoolProfileSerializer, StreamSerializer,
    SubjectAllocationSerializer, SubjectCombinationSerializer,
    SubjectSerializer, TermSerializer,
)


class AcademicViewSet(viewsets.ModelViewSet):
    permission_classes = [IsReadOnlyOrAcademicManager]
    search_fields = ["name"]

    def get_queryset(self):
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.soft_delete()


def viewset_for(model, serializer, ordering=("pk",)):
    return type(
        f"{model.__name__}ViewSet",
        (AcademicViewSet,),
        {"queryset": model.objects.all(), "serializer_class": serializer, "ordering_fields": "__all__", "ordering": ordering},
    )


SchoolProfileViewSet = viewset_for(SchoolProfile, SchoolProfileSerializer)
AcademicYearViewSet = viewset_for(AcademicYear, AcademicYearSerializer, ("-start_date",))
TermViewSet = viewset_for(Term, TermSerializer)
DepartmentViewSet = viewset_for(Department, DepartmentSerializer, ("name",))
ClassLevelViewSet = viewset_for(ClassLevel, ClassLevelSerializer, ("level",))
StreamViewSet = viewset_for(Stream, StreamSerializer)
SubjectViewSet = viewset_for(Subject, SubjectSerializer, ("name",))
SubjectCombinationViewSet = viewset_for(SubjectCombination, SubjectCombinationSerializer, ("name",))
SubjectAllocationViewSet = viewset_for(SubjectAllocation, SubjectAllocationSerializer)
CalendarEventViewSet = viewset_for(CalendarEvent, CalendarEventSerializer, ("start_date",))
