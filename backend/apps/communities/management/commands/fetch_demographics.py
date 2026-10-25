"""Public demographics for geographic communities, from Statistics Finland.

    manage.py fetch_demographics --snapshot   # fetch all of Finland into data/municipalities.json
    manage.py fetch_demographics              # every active geographic community, from the snapshot
    manage.py fetch_demographics oulu kemi    # these communities (slugs)
    manage.py fetch_demographics --live oulu  # straight from Statistics Finland instead
    manage.py fetch_demographics --municipality Kittilä   # print one municipality, store nothing
    manage.py fetch_demographics --borders 2026           # rewrite the municipality borders file
"""

from django.core.management.base import BaseCommand, CommandError

from apps.communities import demographics, places
from apps.communities.models import CommunityGroup


class Command(BaseCommand):
    help = "Population, languages, students and tourism figures from Statistics Finland"

    def add_arguments(self, parser):
        parser.add_argument("slugs", nargs="*", help="Community slugs (default: all active geographic communities)")
        parser.add_argument("--snapshot", action="store_true",
                            help="Fetch every municipality and rewrite the checked-in snapshot file")
        parser.add_argument("--live", action="store_true", help="Fetch from Statistics Finland, not the snapshot")
        parser.add_argument("--municipality", help="Print the figures for one municipality without storing them")
        parser.add_argument("--borders", type=int, metavar="YEAR",
                            help="Download that year's municipality map and rewrite the borders file")

    def handle(self, *args, slugs=(), snapshot=False, live=False, municipality=None, borders=None, **opts):
        if borders:
            count = places.write_borders(borders)
            self.stdout.write(self.style.SUCCESS(f"Wrote {count} municipality borders to {places.BORDERS}"))
            return
        try:
            if snapshot:
                count = demographics.write_snapshot()
                self.stdout.write(self.style.SUCCESS(f"Wrote {count} municipalities to {demographics.SNAPSHOT}"))
                if not slugs:
                    return
            if municipality:
                code = demographics.municipality_code(municipality)
                data = demographics.fetch(code) if live else demographics.load_snapshot().get(code)
                if data is None:
                    raise CommandError(f"{municipality} is not in the snapshot; try --live")
                self.stdout.write(self.summary(data))
                return
        except demographics.DemographicsError as exc:
            raise CommandError(str(exc)) from exc
        groups = CommunityGroup.objects.filter(kind=CommunityGroup.Kind.GEO, is_active=True)
        if slugs:
            groups = CommunityGroup.objects.filter(slug__in=slugs)
        if not groups:
            raise CommandError("No matching communities.")
        for group in groups:
            try:
                data = demographics.refresh(group, live=live)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"{group.slug}: {exc}"))
                continue
            self.stdout.write(self.style.SUCCESS(f"{group.slug}: ") + self.summary(data))

    @staticmethod
    def summary(d: dict) -> str:
        p, lang = d.get("population", {}), d.get("languages", {})
        parts = [f"{d.get('municipality') or d['municipality_code']} ({p.get('year', '?')}): "
                 f"{p.get('total', '?')} residents, {p.get('foreign_language_pct', '?')} % foreign-language speakers"]
        if lang.get("top_foreign"):
            parts.append("top languages " + ", ".join(lang_["name"] for lang_ in lang["top_foreign"][:5]))
        if "students" in d:
            parts.append(f"{d['students'].get('pct', '?')} % students")
        if "tourism" in d:
            parts.append(f"{d['tourism'].get('beds_per_1000_residents', '?')} tourist beds per 1000")
        if d.get("errors"):
            parts.append("errors: " + "; ".join(d["errors"]))
        return " · ".join(parts)
