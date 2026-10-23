from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
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
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
