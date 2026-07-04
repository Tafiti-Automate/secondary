from django.urls import path
from .views import AnnouncementCreateView, AnnouncementListView, AnnouncementUpdateView, ConsentCreateView, ConsentListView, ConversationCreateView, ConversationDetailView, ConversationListView, EmergencyBroadcastCreateView, EmergencyBroadcastListView, EmergencyBroadcastSendView, NotificationListView, NotificationReadView, ResourceCreateView, ResourceListView

app_name = "communications"
urlpatterns = [
    path("announcements/", AnnouncementListView.as_view(), name="announcements"),
    path("announcements/add/", AnnouncementCreateView.as_view(), name="announcement-add"),
    path("announcements/<int:pk>/edit/", AnnouncementUpdateView.as_view(), name="announcement-edit"),
    path("resources/", ResourceListView.as_view(), name="resources"),
    path("resources/add/", ResourceCreateView.as_view(), name="resource-add"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
    path("conversations/", ConversationListView.as_view(), name="conversations"),
    path("conversations/add/", ConversationCreateView.as_view(), name="conversation-add"),
    path("conversations/<int:pk>/", ConversationDetailView.as_view(), name="conversation-detail"),
    path("consents/", ConsentListView.as_view(), name="consents"),
    path("consents/add/", ConsentCreateView.as_view(), name="consent-add"),
    path("emergency/", EmergencyBroadcastListView.as_view(), name="emergency-list"),
    path("emergency/add/", EmergencyBroadcastCreateView.as_view(), name="emergency-add"),
    path("emergency/<int:pk>/send/", EmergencyBroadcastSendView.as_view(), name="emergency-send"),
]
