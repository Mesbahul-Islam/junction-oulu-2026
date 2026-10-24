from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MemberTrust
from .serializers import MemberTrustSerializer, VoiceSerializer
from .services import can_decide, decide, refresh


class MyTrustView(APIView):
    """Your standing in each community you belong to, with what you still need for the next level."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rows = [refresh(request.user, m.community) for m in request.user.memberships.select_related("community")]
        return Response(MemberTrustSerializer(rows, many=True).data)


class VoicesView(APIView):
    """Approved trusted voices, optionally ?community=<slug>. Used for badges and the voices list."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = MemberTrust.objects.filter(level=MemberTrust.Level.TRUSTED).select_related("user", "community")
        if slug := request.query_params.get("community"):
            qs = qs.filter(community__slug=slug)
        return Response(VoiceSerializer(qs, many=True).data)


class CandidatesView(APIView):
    """Eligible members waiting for a decision, in the communities you can decide for."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = (MemberTrust.objects.filter(level=MemberTrust.Level.ELIGIBLE, declined_at__isnull=True)
              .select_related("user", "community"))
        rows = [t for t in qs if can_decide(request.user, t.community)]
        return Response(MemberTrustSerializer(rows, many=True).data)


class DecideView(APIView):
    """POST {"approve": true|false, "note": "..."} by a community editor or admin."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        trust = get_object_or_404(MemberTrust.objects.select_related("community"), pk=pk)
        if not can_decide(request.user, trust.community):
            return Response({"detail": "Only this community's editors can decide."}, status=status.HTTP_403_FORBIDDEN)
        try:
            trust = decide(trust, request.user, bool(request.data.get("approve")), str(request.data.get("note", "")))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MemberTrustSerializer(trust).data)
