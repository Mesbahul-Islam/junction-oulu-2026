"""Accounts API (FR-1.1, FR-3.11). JWT login lives at /api/auth/token/; Google OAuth via allauth."""

from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import Interest, OnboardingLink
from .serializers import (
    InterestSerializer,
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
