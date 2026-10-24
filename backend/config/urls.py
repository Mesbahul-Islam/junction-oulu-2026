from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.views import OAuthCallbackView

def fantasy_frontend(request):
    """Basic Fantasy Liiga UI (backend/frontend/fantasy.html) over /api/fantasy/."""
    return FileResponse(open(settings.BASE_DIR / "frontend" / "fantasy.html", "rb"), content_type="text/html")


def frontend(request):
    """The dev UI: one static page that talks to the API below (backend/frontend/index.html)."""
    return FileResponse(open(settings.BASE_DIR / "frontend" / "index.html", "rb"), content_type="text/html")


urlpatterns = [
    path("", frontend, name="frontend"),
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
