"""Account business logic (no HTTP). FR-1.1 onboarding, FR-3.11 QR links."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Interest, Location, OnboardingLink, User


def register_user(email: str, password: str, **extra) -> User:
    """FR-1.1: email/password signup. Profile is created by the post_save signal."""
    return User.objects.create_user(email=email, password=password, **extra)


def resolve_onboarding_link(code: str) -> OnboardingLink | None:
    return OnboardingLink.objects.select_related("community").filter(code=code).first()


def resolve_location(*, location_id=None, postal_code="", lat=None, lng=None, name="") -> Location | None:
    """Return an existing Location or create one from postal code / coordinates.

    TODO: geocode postal code / lat-lng -> municipality (e.g. via Digitransit or Paavo data)
    and match against CommunityGroup.bbox.
    """
    if location_id:
        return Location.objects.filter(pk=location_id).first()
    if not postal_code and (lat is None or lng is None):
        return None
    if postal_code and lat is None:
        loc = Location.objects.filter(postal_code=postal_code).first()
        if loc:
            return loc
    return Location.objects.create(name=name, postal_code=postal_code or "", lat=lat, lng=lng)


@transaction.atomic
def complete_onboarding(user: User, data: dict) -> User:
    """FR-1.1 / FR-3.11: store interests, location, language, situation and arrival date.

    If an onboarding link code is given, its language/community/arrival offset act as defaults,
    and the user is joined to the link's community.
    """
    link = resolve_onboarding_link(data["onboarding_code"]) if data.get("onboarding_code") else None

    user.preferred_language = data.get("preferred_language") or (link.language if link and link.language else user.preferred_language)
    user.reader_situation = data.get("reader_situation", user.reader_situation)
    arrival = data.get("arrival_date")
    if arrival is None and link is not None:
        arrival = timezone.localdate() - timedelta(days=link.default_arrival_offset_days)
    if arrival is not None:
        user.arrival_date = arrival
    user.onboarded = True
    user.save()

    profile = user.profile
    slugs = data.get("interests") or []
    interests = list(Interest.objects.filter(slug__in=slugs))
    profile.interests.set(interests)  # signals.interests_changed updates profile.interest_vector
    location = resolve_location(
        location_id=data.get("location_id"),
        postal_code=data.get("postal_code", ""),
        lat=data.get("lat"),
        lng=data.get("lng"),
    )
    if location:
        profile.location = location
    profile.save()

    if link and link.community_id:
        from apps.communities.services import join_community

        join_community(user, link.community)
    # TODO: auto-join geo community by matching location against CommunityGroup.bbox.
    return user
