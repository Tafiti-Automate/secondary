from django.core.management.base import BaseCommand

from communications.models import Notification
from communications.services import deliver_notification


class Command(BaseCommand):
    help = "Deliver pending or retry failed academic notifications."

    def add_arguments(self, parser):
        parser.add_argument("--retry-failed", action="store_true")
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        statuses = ["pending", "failed"] if options["retry_failed"] else ["pending"]
        notifications = Notification.objects.filter(is_deleted=False, status__in=statuses).select_related("recipient")[: options["limit"]]
        sent = failed = 0
        for notification in notifications:
            deliver_notification(notification)
            if notification.status == "sent":
                sent += 1
            else:
                failed += 1
        self.stdout.write(self.style.SUCCESS(f"Processed {sent + failed}: {sent} sent, {failed} failed."))
