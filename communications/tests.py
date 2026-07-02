from django.test import TestCase

from accounts.models import User
from .models import Notification


class NotificationTests(TestCase):
    def test_mark_read_is_idempotent(self):
        user = User.objects.create_user("parent", role="parent")
        notification = Notification.objects.create(recipient=user, title="Result published", message="A report is ready.")
        notification.mark_read()
        first = notification.read_at
        notification.mark_read()
        self.assertEqual(notification.read_at, first)
