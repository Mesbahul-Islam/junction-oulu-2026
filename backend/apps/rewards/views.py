from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Perk
from .serializers import PerkSerializer, PlanSerializer, RedemptionSerializer
from .services import PerkError, cancel, month_now, plan_of, redeem, standing, subscribe


class MyRewardsView(APIView):
    """Your level (from your trust standing), what's next, every partner offer (locked or not), your codes and plan."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        stats = standing(request.user)
        level = stats["level"]
        perks = Perk.objects.filter(active=True).select_related("partner")
        codes = request.user.redemptions.select_related("perk__partner")
        return Response({
            "stats": stats,
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
