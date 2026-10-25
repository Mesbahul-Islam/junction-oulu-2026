from django.conf import settings


def frontend_url(request):
    """Lets server-rendered pages (allauth) link back to the reader app."""
    return {"frontend_url": settings.FRONTEND_URL}
