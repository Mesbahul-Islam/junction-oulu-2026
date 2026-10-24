from django.db import migrations


def repair(apps, schema_editor):
    """Picture links stored before the wire desk's entity fix had "&center-x=" decoded to
    "¢er-x=" (html.unescape reads "&cent" as ¢), so Kaleva's image CDN answered 400."""
    SourceDocument = apps.get_model("feed", "SourceDocument")
    for doc in SourceDocument.objects.filter(image_url__contains="¢").only("pk", "image_url"):
        SourceDocument.objects.filter(pk=doc.pk).update(image_url=doc.image_url.replace("¢", "&cent"))


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0003_sourcedocument_image_url"),
    ]

    operations = [migrations.RunPython(repair, migrations.RunPython.noop)]
