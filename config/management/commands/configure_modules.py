from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academics.models import SchoolProfile
from config.models import SchoolModule
from config.modules import MODULES, PRESETS, clear_module_cache


class Command(BaseCommand):
    help = "Apply the academic or full-system module preset to the configured school."

    def add_arguments(self, parser):
        parser.add_argument("preset", choices=tuple(PRESETS))

    def handle(self, *args, **options):
        school = SchoolProfile.objects.filter(is_deleted=False).first()
        if not school:
            raise CommandError("Create a school profile before configuring modules.")
        selected = PRESETS[options["preset"]]
        with transaction.atomic():
            for code in MODULES:
                SchoolModule.objects.update_or_create(
                    school=school,
                    code=code,
                    defaults={"is_enabled": code in selected, "is_deleted": False},
                )
        clear_module_cache(school.pk)
        self.stdout.write(self.style.SUCCESS(f"Applied {options['preset']} preset to {school}."))
