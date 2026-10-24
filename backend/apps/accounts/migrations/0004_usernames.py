import re

import django.core.validators
import django.db.models.functions.text
from django.db import migrations, models


def fill_usernames(apps, schema_editor):
    """Existing accounts get a username from their email ("aino@example.com" -> "aino")."""
    User = apps.get_model("accounts", "User")
    taken = set()
    for user in User.objects.order_by("pk"):
        stem = re.sub(r"[^A-Za-z0-9_.]", "", user.email.split("@")[0])[:26] or "reader"
        stem = stem if len(stem) >= 3 else f"{stem}_reader"[:26]
        name, n = stem, 1
        while name.lower() in taken:
            n += 1
            name = f"{stem}{n}"
        taken.add(name.lower())
        User.objects.filter(pk=user.pk).update(username=name)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_backfill_interest_vector"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="username",
            field=models.CharField(max_length=30, null=True, blank=True),
        ),
        migrations.RunPython(fill_usernames, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                max_length=30,
                validators=[django.core.validators.RegexValidator(
                    "^[A-Za-z0-9_.]{3,30}$", "3–30 letters, digits, _ or . (no spaces).")],
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower("username"), name="uniq_username_ci"),
        ),
    ]
