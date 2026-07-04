from rest_framework.routers import DefaultRouter
from rest_framework import viewsets
from django.db.models import Q

from config.permissions import IsReadOnlyOrAcademicManager
from .models import Room, SchedulingRequirement, TimeSlot, TimetableEntry, TimetableGenerationRun
from .serializers import RoomSerializer, SchedulingRequirementSerializer, TimeSlotSerializer, TimetableEntrySerializer, TimetableGenerationRunSerializer


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsReadOnlyOrAcademicManager]

    def get_queryset(self):
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.soft_delete()


router = DefaultRouter()
router.register("rooms", type("RoomViewSet", (BaseViewSet,), {"queryset": Room.objects.all(), "serializer_class": RoomSerializer}), basename="room")
router.register("time-slots", type("TimeSlotViewSet", (BaseViewSet,), {"queryset": TimeSlot.objects.all(), "serializer_class": TimeSlotSerializer}), basename="time-slot")
router.register("requirements", type("SchedulingRequirementViewSet", (BaseViewSet,), {"queryset": SchedulingRequirement.objects.all(), "serializer_class": SchedulingRequirementSerializer}), basename="scheduling-requirement")
router.register("generation-runs", type("TimetableGenerationRunViewSet", (BaseViewSet,), {"queryset": TimetableGenerationRun.objects.all(), "serializer_class": TimetableGenerationRunSerializer, "http_method_names": ["get", "head", "options"]}), basename="generation-run")
class TimetableEntryViewSet(BaseViewSet):
    queryset = TimetableEntry.objects.all()
    serializer_class = TimetableEntrySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "teacher":
            return qs.filter(teacher=user)
        if user.role == "student":
            return qs.filter(stream__students__user=user)
        if user.role == "parent":
            return qs.filter(Q(stream__students__parent=user) | Q(stream__students__guardian_links__guardian__user=user)).distinct()
        return qs


router.register("entries", TimetableEntryViewSet, basename="entry")
urlpatterns = router.urls
