from django.urls import path
from .views import AnnouncementCreateView, AnnouncementListView, AnnouncementUpdateView, NotificationListView, NotificationReadView, ResourceCreateView, ResourceListView

app_name = "communications"
urlpatterns = [
    path("announcements/", AnnouncementListView.as_view(), name="announcements"),
    path("announcements/add/", AnnouncementCreateView.as_view(), name="announcement-add"),
    path("announcements/<int:pk>/edit/", AnnouncementUpdateView.as_view(), name="announcement-edit"),
    path("resources/", ResourceListView.as_view(), name="resources"),
    path("resources/add/", ResourceCreateView.as_view(), name="resource-add"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
]
