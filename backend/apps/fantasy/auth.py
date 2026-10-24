"""DEV ONLY: browse the logged-in fantasy endpoints without logging in.

Active only when settings.DEBUG is True (FANTASY_DEV_AUTH_BYPASS defaults to
DEBUG) and no real credentials were sent. Acts as the user given by
`?as=<email or squad id>` or the `X-Fantasy-As` header, else the first superuser.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication


class DevBypassAuthentication(BaseAuthentication):
    def authenticate(self, request):
        if not (settings.DEBUG and getattr(settings, "FANTASY_DEV_AUTH_BYPASS", True)):
            return None
        User = get_user_model()
        email = request.query_params.get("as") or request.headers.get("X-Fantasy-As")
        if email and email.isdigit():
            from .models import Squad

            squad = Squad.objects.select_related("user").filter(pk=int(email)).first()
            user = squad.user if squad else None
        elif email:
            user = User.objects.filter(email__iexact=email).first()
        else:
            user = User.objects.filter(is_superuser=True).order_by("pk").first()
        return (user, None) if user else None
