import json
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Notification


def deliver_notification(notification):
    """Deliver through the configured provider and retain provider errors for retry."""
    try:
        if notification.channel == "in_app":
            pass
        elif notification.channel == "email":
            if not notification.recipient.email:
                raise ValueError("Recipient has no email address.")
            send_mail(notification.title, notification.message, settings.DEFAULT_FROM_EMAIL, [notification.recipient.email])
        elif notification.channel in {"sms", "whatsapp"}:
            endpoint = settings.SMS_WEBHOOK_URL if notification.channel == "sms" else settings.WHATSAPP_WEBHOOK_URL
            if not endpoint:
                raise ValueError(f"{notification.get_channel_display()} provider is not configured.")
            if not notification.recipient.phone:
                raise ValueError("Recipient has no phone number.")
            payload = json.dumps({"to": notification.recipient.phone, "message": notification.message, "title": notification.title}).encode()
            headers = {"Content-Type": "application/json"}
            if settings.NOTIFICATION_WEBHOOK_TOKEN:
                headers["Authorization"] = f"Bearer {settings.NOTIFICATION_WEBHOOK_TOKEN}"
            with urlopen(Request(endpoint, data=payload, headers=headers, method="POST"), timeout=15) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Provider returned HTTP {response.status}.")
        notification.status, notification.sent_at, notification.error_message = "sent", timezone.now(), ""
    except Exception as exc:
        notification.status, notification.error_message = "failed", str(exc)
    notification.save(update_fields=["status", "sent_at", "error_message", "updated_at"])
    return notification


def queue_notification(recipient, title, message, channel="in_app", link="", deliver_now=True):
    notification = Notification.objects.create(recipient=recipient, title=title, message=message, channel=channel, link=link)
    return deliver_notification(notification) if deliver_now else notification
