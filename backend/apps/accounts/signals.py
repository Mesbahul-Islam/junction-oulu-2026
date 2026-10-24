from django.conf import settings
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    """FR-1.1: every user gets a Profile (password signup and Google OAuth alike)."""
    if created:
        Profile.objects.get_or_create(user=instance)


def sync_interest_vector(profile: Profile) -> None:
    """Keep the ranking weights (``interest_vector``) in step with the chosen interests.

    New interests start at 1.0, removed ones are dropped, and weights of kept interests
    are preserved (so weights learned later aren't reset by an unrelated edit).
    """
    old = profile.interest_vector or {}
    vector = {slug: old.get(slug, 1.0) for slug in profile.interests.values_list("slug", flat=True)}
    if vector != old:
        profile.interest_vector = vector
        profile.save(update_fields=["interest_vector", "updated_at"])


@receiver(m2m_changed, sender=Profile.interests.through)
def interests_changed(sender, instance, action, reverse, pk_set, **kwargs):
    """FR-2.3: whenever interests change (onboarding, admin, bootstrap, shell), update the weights."""
    if reverse and action == "pre_clear":  # Interest.profiles.clear(): remember who loses it
        instance._cleared_profile_ids = list(instance.profiles.values_list("pk", flat=True))
        return
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if not reverse:
        sync_interest_vector(instance)
    else:  # changed from the Interest side: instance is an Interest
        ids = pk_set if pk_set is not None else getattr(instance, "_cleared_profile_ids", [])
        for profile in Profile.objects.filter(pk__in=ids):
            sync_interest_vector(profile)
