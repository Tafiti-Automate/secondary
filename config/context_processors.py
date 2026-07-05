def school_context(request):
    from academics.models import SchoolProfile, Term
    from config.modules import MODULES, get_enabled_modules, get_plan_name

    school = SchoolProfile.objects.filter(is_deleted=False).first()
    current_term = Term.objects.filter(is_deleted=False, is_current=True).select_related("academic_year").first()
    unread_notifications = None
    if request.user.is_authenticated:
        from communications.models import Notification
        unread_notifications = Notification.objects.filter(recipient=request.user, is_deleted=False, read_at__isnull=True)[:5]
    enabled_modules = get_enabled_modules(school)
    return {
        "school": school,
        "current_term": current_term,
        "notifications": unread_notifications,
        "enabled_modules": enabled_modules,
        "module_catalog": MODULES,
        "module_plan_name": get_plan_name(enabled_modules),
    }
