from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "accounts"

router = DefaultRouter()
router.register("interests", views.InterestViewSet, basename="interest")

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("me/", views.MeView.as_view(), name="me"),
    path("onboarding/", views.OnboardingView.as_view(), name="onboarding"),
    path("onboarding-link/<str:code>/", views.OnboardingLinkResolveView.as_view(), name="onboarding-link"),
    path("readers/", views.ReaderListView.as_view(), name="readers"),
    path("locate/", views.LocateView.as_view(), name="locate"),
    path("municipalities/", views.MunicipalityListView.as_view(), name="municipalities"),
    path("municipalities/<str:code>/", views.MunicipalityListView.as_view(), name="municipality"),
    path("", include(router.urls)),
]
