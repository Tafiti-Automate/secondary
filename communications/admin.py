from django.contrib import admin
from .models import Announcement, LearningResource, Notification

admin.site.register([Announcement, LearningResource, Notification])
