from django.utils import timezone


class ActivityTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            previous = request.session.get("last_activity_write", 0)
            now = timezone.now()
            if now.timestamp() - previous > 300:
                request.user.__class__.objects.filter(pk=request.user.pk).update(last_activity=now)
                request.session["last_activity_write"] = now.timestamp()
        return response
