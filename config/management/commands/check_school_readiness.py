from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from academics.models import AcademicYear, SchoolProfile
from assessments.readiness import curriculum_coverage_for_year
from exams.readiness import uneb_export_preflight
from students.models import Enrollment


class Command(BaseCommand):
    help = "Run curriculum, enrolment, UNEB and production go-live checks."

    def add_arguments(self, parser):
        parser.add_argument("--academic-year", help="Academic-year name; defaults to the current year.")
        parser.add_argument("--production", action="store_true", help="Also enforce production security settings.")
        parser.add_argument("--uneb-level", choices=("uce", "uace"))
        parser.add_argument("--uneb-year", type=int)
        parser.add_argument("--fail-on-warnings", action="store_true")

    def handle(self, *args, **options):
        errors = []
        warnings = []
        year = self._academic_year(options.get("academic_year"), errors)
        school = SchoolProfile.objects.filter(is_deleted=False).first()
        if not school:
            errors.append("School profile is not configured.")
        else:
            if not school.emis_number:
                warnings.append("School EMIS number is missing.")
            if not school.centre_number:
                warnings.append("School UNEB centre number is missing.")
            if not school.address:
                warnings.append("School address is missing.")

        if year:
            coverage = curriculum_coverage_for_year(year)
            errors.extend(coverage.errors)
            warnings.extend(coverage.warnings)
            self._check_enrolments(year, errors, warnings)
            self.stdout.write(f"Checked {coverage.checked_allocations} distinct teaching allocation(s) for {year}.")

        level, exam_year = options.get("uneb_level"), options.get("uneb_year")
        if bool(level) != bool(exam_year):
            errors.append("Use --uneb-level and --uneb-year together.")
        elif level and exam_year:
            preflight = uneb_export_preflight(level, exam_year)
            errors.extend(preflight.errors)
            warnings.extend(preflight.warnings)
            self.stdout.write(f"UNEB preflight selected {len(preflight.records)} approved record(s).")

        if options.get("production"):
            self._check_production(errors, warnings)

        for message in sorted(set(warnings)):
            self.stdout.write(self.style.WARNING(f"WARNING: {message}"))
        for message in sorted(set(errors)):
            self.stdout.write(self.style.ERROR(f"ERROR: {message}"))
        if errors or (warnings and options.get("fail_on_warnings")):
            raise CommandError(
                f"School readiness failed with {len(set(errors))} error(s) and {len(set(warnings))} warning(s)."
            )
        self.stdout.write(self.style.SUCCESS(
            f"School readiness passed with {len(set(warnings))} warning(s)."
        ))

    @staticmethod
    def _academic_year(name, errors):
        if name:
            year = AcademicYear.objects.filter(name=name, is_deleted=False).first()
            if not year:
                errors.append(f"Academic year '{name}' does not exist.")
            return year
        year = AcademicYear.objects.filter(is_current=True, is_deleted=False).first()
        if not year:
            errors.append("No current academic year is configured.")
        return year

    @staticmethod
    def _check_enrolments(year, errors, warnings):
        enrollments = Enrollment.objects.filter(
            academic_year=year,
            is_deleted=False,
        ).exclude(status="withdrawn").select_related("student", "stream__class_level").prefetch_related("subject_registrations")
        if not enrollments.exists():
            errors.append(f"No learner enrolments exist for {year}.")
            return
        for enrollment in enrollments:
            active_subjects = [
                item for item in enrollment.subject_registrations.all()
                if not item.is_deleted and item.status == "active"
            ]
            level = enrollment.stream.class_level.level
            label = f"{enrollment.student.full_name} ({enrollment.stream})"
            if level in {1, 2} and len(active_subjects) != 12:
                errors.append(f"{label}: S1/S2 requires 12 active subjects; found {len(active_subjects)}.")
            elif level in {3, 4} and not 8 <= len(active_subjects) <= 9:
                errors.append(f"{label}: S3/S4 requires 8–9 active subjects; found {len(active_subjects)}.")
            elif level in {5, 6} and not active_subjects:
                errors.append(f"{label}: no active S5/S6 subjects are registered.")
            if enrollment.student.stream_id and enrollment.student.stream.academic_year_id == year.pk and enrollment.student.stream_id != enrollment.stream_id:
                warnings.append(f"{label}: current placement differs from the academic-year enrolment.")

    @staticmethod
    def _check_production(errors, warnings):
        if settings.DEBUG:
            errors.append("DEBUG must be False in production.")
        if settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
            errors.append("Production must use PostgreSQL, not SQLite.")
        if not settings.ALLOWED_HOSTS or any(host in {"*", "localhost", "127.0.0.1"} for host in settings.ALLOWED_HOSTS):
            errors.append("ALLOWED_HOSTS must contain only the production host names.")
        if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
            errors.append("Secure session and CSRF cookies are required in production.")
        if not settings.SECURE_SSL_REDIRECT:
            errors.append("SECURE_SSL_REDIRECT must be enabled in production.")
        if settings.SECURE_HSTS_SECONDS < 31536000:
            warnings.append("HSTS is below the recommended one-year production value.")
        if len(settings.SECRET_KEY) < 50 or "change" in settings.SECRET_KEY.lower():
            errors.append("SECRET_KEY must be a strong secrets-managed production value.")
