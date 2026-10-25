"""Accounts API (FR-1.1, FR-3.11). JWT login lives at /api/auth/token/; Google OAuth via allauth."""

from django.conf import settings
from django.http import HttpResponseRedirect
from django.views import View
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import Interest, OnboardingLink, User
from .serializers import (
    InterestSerializer,
    LocateSerializer,
    OnboardingLinkSerializer,
    OnboardingSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(APIView):
    """POST /api/accounts/register/ — FR-1.1 email/password signup."""

    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.register_user(**ser.validated_data)
        # TODO: return JWT pair directly so the client can skip the /api/auth/token/ round trip.
        refresh = RefreshToken.for_user(user)
        data = UserSerializer(user).data
        data["tokens"] = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
        return Response(data, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/accounts/me/ — FR-1.1 own account & profile."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class OnboardingView(APIView):
    """POST /api/accounts/onboarding/ — FR-1.1 interests/location/language, FR-3.11 arrival date + QR code."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OnboardingSerializer

    def post(self, request):
        ser = OnboardingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.complete_onboarding(request.user, ser.validated_data)
        return Response(UserSerializer(user).data)


class LocateView(APIView):
    """POST /api/accounts/locate/ {"lat", "lng"} — which municipality the reader is in, and the
    newsroom town that serves it. The coordinates are only used for the lookup: not stored or logged."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LocateSerializer

    def post(self, request):
        from apps.communities import places

        ser = LocateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        code = places.locate(ser.validated_data["lat"], ser.validated_data["lng"])
        if code is None:
            return Response({"detail": "That location isn't in a Finnish municipality."}, status=404)
        return Response(places.town(code))


class MunicipalityListView(APIView):
    """GET /api/accounts/municipalities/ — every municipality for the town picker, with the ones
    the newsroom covers marked. GET .../<code>/ — one town, as POST /locate/ returns it."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, code=None):
        from apps.communities import places

        if code is None:
            return Response(places.municipalities())
        if not places.municipality_name(code):
            return Response({"detail": "Unknown municipality."}, status=404)
        return Response(places.town(code))


class InterestViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/accounts/interests/ — interest taxonomy for onboarding (FR-1.1)."""

    permission_classes = [permissions.AllowAny]
    serializer_class = InterestSerializer
    queryset = Interest.objects.all()
    pagination_class = None


class OnboardingLinkResolveView(generics.RetrieveAPIView):
    """GET /api/accounts/onboarding-link/<code>/ — FR-3.11 resolve a QR code before signup."""

    permission_classes = [permissions.AllowAny]
    serializer_class = OnboardingLinkSerializer
    queryset = OnboardingLink.objects.select_related("community")
    lookup_field = "code"


class ReaderListView(generics.ListAPIView):
    """GET /api/accounts/readers/ (staff): onboarded readers, to preview the feed as each of them."""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = UserSerializer
    pagination_class = None

    def get_queryset(self):
        return User.objects.filter(onboarded=True).select_related("profile").prefetch_related("profile__interests", "roles").order_by("email")


class OAuthCallbackView(View):
    """Redirects after Google OAuth via allauth to frontend or admin with JWT token."""

    def get(self, request):
        if request.user.is_authenticated:
            refresh = RefreshToken.for_user(request.user)
            token = str(refresh.access_token)
            next_param = request.GET.get("next") or request.session.get("oauth_next", "")
            if "admin" in next_param:
                return HttpResponseRedirect(f"/#token={token}")
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            return HttpResponseRedirect(f"{frontend_url}/welcome#token={token}")
        return HttpResponseRedirect("/")
