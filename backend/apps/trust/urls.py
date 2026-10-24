from django.urls import path

from . import views

app_name = "trust"

urlpatterns = [
    path("me/", views.MyTrustView.as_view(), name="me"),
    path("voices/", views.VoicesView.as_view(), name="voices"),
    path("candidates/", views.CandidatesView.as_view(), name="candidates"),
    path("candidates/<int:pk>/decide/", views.DecideView.as_view(), name="decide"),
]
