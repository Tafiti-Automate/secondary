def school_context(request):
    from academics.models import SchoolProfile, Term

    school = SchoolProfile.objects.filter(is_deleted=False).first()
    current_term = Term.objects.filter(is_deleted=False, is_current=True).select_related("academic_year").first()
    unread_notifications = None
    if request.user.is_authenticated:
        from communications.models import Notification
        unread_notifications = Notification.objects.filter(recipient=request.user, is_deleted=False, read_at__isnull=True)[:5]
    return {"school": school, "current_term": current_term, "notifications": unread_notifications}
