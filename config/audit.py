from accounts.models import AuditLog


def record_audit(request, action, obj, description, changes=None):
    return AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        entity_type=obj._meta.verbose_name.title(),
        entity_id=str(obj.pk),
        description=description,
        changes=changes or {},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
