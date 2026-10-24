from django.urls import path

from . import views

app_name = "rewards"

urlpatterns = [
    path("stats/", views.StatsReceiverView.as_view(), name="stats"),
    path("me/", views.MyRewardsView.as_view(), name="me"),
    path("perks/<int:pk>/redeem/", views.RedeemView.as_view(), name="redeem"),
    path("plan/", views.PlanView.as_view(), name="plan"),
]
