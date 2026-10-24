import hmac

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ContributorStats, Level, Perk
from .serializers import IngestSerializer, PerkSerializer, PlanSerializer, RedemptionSerializer, StatsSerializer
from .services import PerkError, cancel, ingest, month_now, next_step, plan_of, redeem, subscribe


class SenderKey(permissions.BasePermission):
    """The service sending statistics shows REWARDS_INGEST_KEY in the X-Rewards-Key header.
    With no key set, only a DEBUG (local) server accepts statistics."""

    def has_permission(self, request, view):
        key = getattr(settings, "REWARDS_INGEST_KEY", "")
        if not key:
            return settings.DEBUG
        return hmac.compare_digest(request.headers.get("X-Rewards-Key", ""), key)


class StatsReceiverView(APIView):
    """Receive contribution statistics for one or more members.

    POST {"source": "community-stats",
          "members": [{"email": "maria@example.com", "period": "2026-10",
                       "contributions": {"posts_approved": 6, "photos_approved": 3, "corrections_accepted": 2, "rejected": 0},
                       "community_rating": {"average": 4.7, "count": 21},
                       "trusted_voice": true, "trust_score": 74}]}
    A single member object without the "members" list is accepted too.
    """

    authentication_classes = []
    permission_classes = [SenderKey]

    def post(self, request):
        body = request.data if "members" in request.data else {"members": [request.data]}
        ser = IngestSerializer(data=body)
        ser.is_valid(raise_exception=True)
        rows = [{**row, "_raw": raw} for row, raw in zip(ser.validated_data["members"], body["members"])]
        result = ingest(rows, source=ser.validated_data["source"])
        return Response(result, status=status.HTTP_200_OK)


class MyRewardsView(APIView):
    """Your level, what earned it, what's next, every partner offer (locked or not), your codes and plan."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        stats = ContributorStats.objects.filter(user=request.user).first()
        level = stats.level if stats else Level.READER
        perks = Perk.objects.filter(active=True).select_related("partner")
        codes = request.user.redemptions.select_related("perk__partner")
        return Response({
            "stats": StatsSerializer(stats).data if stats else {
                "points": 0, "level": level, "level_label": Level(level).label, "next": next_step(None)},
            "perks": PerkSerializer(perks, many=True, context={"level": level}).data,
            "codes": RedemptionSerializer(codes, many=True).data,
            "month": month_now(),
            "plan": PlanSerializer(plan).data if (plan := plan_of(request.user)) else None,
        })


class RedeemView(APIView):
    """POST: get a code for this partner (the same code again if you already took one this month)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        perk = get_object_or_404(Perk.objects.select_related("partner"), pk=pk)
        try:
            code = redeem(request.user, perk)
        except PerkError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RedemptionSerializer(code).data)


class PlanView(APIView):
    """POST {"billing": "monthly" | "yearly"} starts or switches ad-free reading; DELETE cancels it
    (ad-free until the renewal date)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            plan = subscribe(request.user, str(request.data.get("billing", "")))
        except PerkError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PlanSerializer(plan).data)

    def delete(self, request):
        plan = cancel(request.user)
        return Response(PlanSerializer(plan).data if plan else None)
