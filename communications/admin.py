from django.contrib import admin
from .models import Announcement, ConsentRecord, ConversationMessage, ConversationThread, EmergencyBroadcast, LearningResource, Notification

admin.site.register([Announcement, LearningResource, Notification, ConversationThread, ConversationMessage, ConsentRecord, EmergencyBroadcast])
