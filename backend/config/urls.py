import hashlib

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.urls import include, path
from django.views.decorators.cache import never_cache
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.views import OAuthCallbackView

def fantasy_frontend(request):
    """Basic Fantasy Liiga UI (backend/frontend/fantasy.html) over /api/fantasy/."""
    return FileResponse(open(settings.BASE_DIR / "frontend" / "fantasy.html", "rb"), content_type="text/html")


@never_cache
def frontend(request):
    """Serve the newsroom with asset fingerprints so refreshes pick up UI fixes."""
    root = settings.BASE_DIR / "frontend"
    page = (root / "index.html").read_text()
    for asset in ("admin.css", "admin.js"):
        version = hashlib.sha256((root / "static" / "newsroom" / asset).read_bytes()).hexdigest()[:12]
        url = f"/static/newsroom/{asset}"
        page = page.replace(url, f"{url}?v={version}")
    return HttpResponse(page, content_type="text/html")


urlpatterns = [
    path("", frontend, name="frontend"),
    # The same dashboard under /newsroom/, so it can share one public address with the reader
    # app: the reader app's dev server forwards /newsroom/ (and /api, /static ...) to Django.
    path("newsroom/", frontend, name="newsroom"),
    path("fantasy/", fantasy_frontend, name="fantasy-frontend"),
    path("admin/", admin.site.urls),
    path("accounts/oauth/callback/", OAuthCallbackView.as_view(), name="oauth_callback"),
    path("accounts/", include("allauth.urls")),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/communities/", include("apps.communities.urls")),
    path("api/feed/", include("apps.feed.urls")),
    path("api/agents/", include("apps.agents.urls")),
    path("api/editorial/", include("apps.editorial.urls")),
    path("api/notes/", include("apps.notes.urls")),
    path("api/markets/", include("apps.markets.urls")),
    path("api/fantasy/", include("apps.fantasy.urls")),
    path("api/trust/", include("apps.trust.urls")),
    path("api/rewards/", include("apps.rewards.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
