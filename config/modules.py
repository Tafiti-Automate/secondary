"""Module catalogue and helpers for configuring a school installation.

Applications stay installed so migrations remain predictable.  A school's
module configuration controls access and navigation at runtime instead.
"""

from collections import OrderedDict

from django.core.cache import cache
from django.db import OperationalError, ProgrammingError


MODULES = OrderedDict(
    (
        ("academics", {"name": "Academic structure", "description": "Academic years, terms, classes, streams, subjects and allocations.", "group": "Academic"}),
        ("students", {"name": "Students & admissions", "description": "Learner records, guardians, enrolment, movement and promotion.", "group": "Academic"}),
        ("assessments", {"name": "Assessment & CBC", "description": "Continuous assessment, competencies, outcomes, evidence and portfolios.", "group": "Academic"}),
        ("exams", {"name": "Examinations & UNEB", "description": "Examinations, mark entry, upper-secondary plans and UNEB records.", "group": "Academic"}),
        ("attendance", {"name": "Attendance", "description": "Daily learner attendance, alerts and attendance analytics.", "group": "Academic"}),
        ("timetables", {"name": "Timetables", "description": "Class and teacher timetable planning.", "group": "Academic"}),
        ("communications", {"name": "Communication", "description": "Announcements, messages, notifications, resources and consent.", "group": "Engagement"}),
        ("reports", {"name": "Reports & analytics", "description": "Report cards, transcripts, growth profiles and performance analytics.", "group": "Academic"}),
        ("staff", {"name": "Staff management", "description": "Staff profiles, employment details, bank details and documents.", "group": "Operations"}),
        ("fees", {"name": "Fees & billing", "description": "Fee structures, student invoices, receipts, payments and balances.", "group": "Finance"}),
        ("finance", {"name": "Finance & budgeting", "description": "Budgets, income, expenditure, vendors, approvals and cash flow.", "group": "Finance"}),
    )
)

ACADEMIC_MODULES = frozenset({"academics", "students", "assessments", "exams", "attendance", "timetables", "communications", "reports"})
FULL_MODULES = frozenset(MODULES)
PRESETS = {"academic": ACADEMIC_MODULES, "full": FULL_MODULES}


def module_cache_key(school_id):
    return f"school-modules:{school_id or 'default'}"


def clear_module_cache(school_id=None):
    cache.delete(module_cache_key(school_id))


def get_enabled_modules(school=None):
    """Return enabled codes; installations without configuration stay academic-only."""
    school_id = getattr(school, "pk", None)
    cache_key = module_cache_key(school_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return frozenset(cached)

    enabled = ACADEMIC_MODULES
    if school_id:
        try:
            from config.models import SchoolModule

            rows = SchoolModule.objects.filter(school_id=school_id, is_deleted=False)
            if rows.exists():
                enabled = frozenset(rows.filter(is_enabled=True).values_list("code", flat=True))
        except (OperationalError, ProgrammingError):
            # Keeps checks and the first migration safe before the table exists.
            enabled = ACADEMIC_MODULES
    cache.set(cache_key, tuple(enabled), 300)
    return frozenset(enabled)


def get_plan_name(enabled):
    enabled = frozenset(enabled)
    if enabled == FULL_MODULES:
        return "Full system"
    if enabled == ACADEMIC_MODULES:
        return "Academic only"
    return "Custom modules"


def module_is_enabled(code, school=None):
    return code in get_enabled_modules(school)
