"""Fill in ranking weights for profiles whose interests were set without them.

Before signals.interests_changed existed, only onboarding filled ``interest_vector``;
users created by bootstrap, the admin or the shell had interests but empty weights,
so the feed's interest score was always 0 for them.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    Profile = apps.get_model("accounts", "Profile")
    for profile in Profile.objects.prefetch_related("interests"):
        old = profile.interest_vector or {}
        vector = {i.slug: old.get(i.slug, 1.0) for i in profile.interests.all()}
        if vector != old:
            profile.interest_vector = vector
            profile.save(update_fields=["interest_vector"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
