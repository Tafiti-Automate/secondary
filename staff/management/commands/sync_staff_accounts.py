from django.core.management.base import BaseCommand

from accounts.models import User
from staff.models import StaffMember


class Command(BaseCommand):
    help = "Create or refresh staff profiles from existing non-student portal accounts."

    def handle(self, *args, **options):
        users = User.objects.filter(is_active=True, is_deleted=False).exclude(role__in=("student", "parent"))
        created = updated = 0
        for user in users:
            first_name = user.first_name or user.username
            last_name = user.last_name or ""
            _, was_created = StaffMember.objects.update_or_create(
                user=user,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": user.phone or "Not recorded",
                    "email": user.email,
                    "job_title": user.get_role_display(),
                    "is_teaching_staff": user.role == "teacher",
                    "status": "active",
                    "is_deleted": False,
                },
            )
            created += int(was_created)
            updated += int(not was_created)
        self.stdout.write(self.style.SUCCESS(f"Staff sync complete: {created} created, {updated} updated."))
