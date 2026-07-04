from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import ConversationThread, EmergencyBroadcast, Notification


class NotificationTests(TestCase):
    def test_mark_read_is_idempotent(self):
        user = User.objects.create_user("parent", role="parent")
        notification = Notification.objects.create(recipient=user, title="Result published", message="A report is ready.")
        notification.mark_read()
        first = notification.read_at
        notification.mark_read()
        self.assertEqual(notification.read_at, first)

    def test_conversation_is_visible_only_to_participants(self):
        parent = User.objects.create_user("thread-parent", role="parent")
        outsider = User.objects.create_user("thread-outsider", role="parent")
        thread = ConversationThread.objects.create(subject="Learner support", created_by=parent)
        thread.participants.add(parent)
        self.client.force_login(parent)
        self.assertEqual(self.client.get(reverse("communications:conversations")).status_code, 200)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("communications:conversation-detail", args=[thread.pk])).status_code, 404)

    def test_emergency_broadcast_uses_recipient_language(self):
        manager = User.objects.create_user("broadcast-dos", role="director_of_studies")
        parent = User.objects.create_user("luganda-parent", role="parent", preferred_language="lg")
        broadcast = EmergencyBroadcast.objects.create(
            title="School closed", message="Please collect learners.", audience="parents",
            channels=["in_app"], translations={"lg": {"title": "Essomero liggadde", "message": "Jjangu onone abayizi."}}, created_by=manager,
        )
        self.client.force_login(manager)

        response = self.client.post(reverse("communications:emergency-send", args=[broadcast.pk]))

        self.assertEqual(response.status_code, 302)
        notice = Notification.objects.get(recipient=parent)
        self.assertEqual(notice.title, "Essomero liggadde")
        self.assertEqual(notice.message, "Jjangu onone abayizi.")
        self.assertEqual(self.client.get(reverse("communications:emergency-list")).status_code, 200)
