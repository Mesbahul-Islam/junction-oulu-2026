"""Idempotent demo seed: Oulu community and topic communities, interests, onboarding links, Kaleva RSS feeds, glossary, context.

Usage: python manage.py seed_demo
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Interest, OnboardingLink
from apps.communities.models import CommunityGroup, ContextEntry, FeedbackPrompt, GlossaryTerm, SourceFeed

KALEVA_RSS = "https://kaleva.fi/feedit/rss/managed-listing/{}/"
KALEVA_FEEDS = [
    ("rss-uusimmat", "Kaleva – Uusimmat"),
    ("oulun-seutu", "Kaleva – Oulun seutu"),
    ("pohjois-suomi", "Kaleva – Pohjois-Suomi"),
    ("kotimaa", "Kaleva – Kotimaa"),
    ("ulkomaat", "Kaleva – Ulkomaat"),
    ("kulttuuri", "Kaleva – Kulttuuri"),
    ("jaakiekko", "Kaleva – Jääkiekko"),
]

INTERESTS = [
    ("housing", "Housing"),
    ("work", "Work"),
    ("health", "Health"),
    ("transport", "Transport"),
    ("education", "Education"),
    ("culture", "Culture"),
    ("sports", "Sports"),
    ("events", "Events"),
    ("services", "Services"),
    ("weather", "Weather"),
]

# Topic communities in Oulu, recommended to readers whose situation or topics match.
# (slug, name, description, audiences, interests, languages)
TOPIC_COMMUNITIES = [
    ("oulu-newcomers", "New in Oulu", "Ask and help with the first months: Kela, housing, registering, finding your way.",
     ["newcomer"], ["services", "housing", "work", "health"], ["fi", "en", "uk", "ar", "ru", "so"]),
    ("oulu-seasonal-workers", "Seasonal workers", "Work, housing and getting around for people here for the season.",
     ["seasonal_worker"], ["work", "housing", "transport", "weather"], ["fi", "en", "uk", "et", "ru"]),
    ("oulu-students", "Students in Oulu", "University and OAMK life: housing, events, cheap eats and transport.",
     ["student"], ["education", "housing", "events", "transport"], ["fi", "en", "sv"]),
    ("oulu-families", "Families in Oulu", "Schools, daycare, health services and things to do with kids.",
     [], ["education", "health", "services"], ["fi", "en", "sv", "ar"]),
    ("karpat-sports", "Kärpät & sports", "Match talk, results and local sport, from Liiga to junior teams.",
     [], ["sports", "events"], ["fi", "en", "sv"]),
    ("oulu-culture", "Culture & events", "Concerts, theatre, festivals and what's on this weekend.",
     [], ["culture", "events"], ["fi", "en"]),
]

# (code, language, default_arrival_offset_days)
ONBOARDING_LINKS = [
    ("OULU-WELCOME", None, 0),
    ("OULU-UNI-EN", "en", 0),
    ("OULU-UK", "uk", 0),
    ("OULU-SEASONAL", "en", 0),
]

GLOSSARY_EN = [
    ("Kela", "Kela (Social Insurance Institution of Finland)",
     "Handles social security benefits: housing allowance, unemployment, health insurance card."),
    ("Migri", "Migri (Finnish Immigration Service)", "Residence permits, citizenship, asylum."),
    ("verokortti", "tax card", "Tells your employer how much income tax to withhold. Order from Vero (OmaVero)."),
    ("henkilötunnus", "personal identity code",
     "Finnish ID number (format DDMMYY-XXXX). Needed for banks, healthcare, Kela."),
    ("TE-palvelut", "TE Services (Employment Services)",
     "Public employment services; since 2025 run by municipalities (in Oulu: Oulun seudun työllisyysalue)."),
    ("kotikunta", "municipality of residence",
     "Registered home municipality; determines access to public health care and many services."),
]

CONTEXT_ENTRIES = [
    ("How a tax card works",
     "A tax card (verokortti) tells your employer what percentage of income tax to withhold from your pay. "
     "New residents get one from the Finnish Tax Administration (Vero) – online via OmaVero or at a tax office. "
     "Without a tax card the employer must withhold 60%. You can request a revised card if your income changes."),
    ("How to register a municipality of residence",
     "To get a municipality of residence (kotikunta), register your address with the Digital and Population Data "
     "Services Agency (DVV). You generally need a right to reside in Finland and an intention to live here "
     "permanently (usually over one year). A home municipality gives access to municipal health care and services."),
    ("What Kela does",
     "Kela pays social security benefits such as housing allowance, student financial aid and sickness allowance. "
     "Eligibility often depends on being covered by Finnish social security; apply via OmaKela."),
]

PLACEHOLDER_NOTE = "[DEMO PLACEHOLDER – human-reviewed sample text, verify before publishing] "


class Command(BaseCommand):
    help = "Seed demo data for Oulu (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        oulu, _ = CommunityGroup.objects.get_or_create(
            slug="oulu",
            defaults={
                "name": "Oulu",
                "kind": CommunityGroup.Kind.GEO,
                "municipality": "Oulu",
                "bbox": [25.2, 64.9, 25.8, 65.2],
                "languages": ["fi", "en", "sv", "uk", "ar", "se"],
                "is_active": True,
            },
        )

        for slug, name in INTERESTS:
            Interest.objects.get_or_create(slug=slug, defaults={"name": name})

        if not oulu.description:
            oulu.description = "Everyone in Oulu: local talk, neighbourly help and questions for the newsroom."
            oulu.save(update_fields=["description", "updated_at"])
        for slug, name, description, audiences, interests, languages in TOPIC_COMMUNITIES:
            group, created = CommunityGroup.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "kind": CommunityGroup.Kind.TOPIC, "municipality": "Oulu",
                          "description": description, "audiences": audiences, "languages": languages},
            )
            if created:
                group.interests.set(Interest.objects.filter(slug__in=interests))

        for code, lang, offset in ONBOARDING_LINKS:
            OnboardingLink.objects.get_or_create(
                code=code, defaults={"community": oulu, "language": lang, "default_arrival_offset_days": offset}
            )

        for path, name in KALEVA_FEEDS:
            SourceFeed.objects.get_or_create(
                community=oulu, url=KALEVA_RSS.format(path), defaults={"name": name, "kind": SourceFeed.Kind.RSS}
            )

        for term_fi, term, note in GLOSSARY_EN:
            GlossaryTerm.objects.get_or_create(
                community=None, language="en", term_fi=term_fi, defaults={"term": term, "note": note}
            )

        now = timezone.now()
        for topic, body in CONTEXT_ENTRIES:
            ContextEntry.objects.get_or_create(
                community=oulu,
                language="en",
                topic=topic,
                defaults={"body": PLACEHOLDER_NOTE + body, "valid_from": date(2026, 1, 1), "reviewed_at": now},
            )

        FeedbackPrompt.objects.get_or_create(
            community=oulu, language="en", question="What was useful in today's news? What was missing?"
        )

        if options["verbosity"] < 1:
            return
        self.stdout.write(self.style.SUCCESS(
            f"Seeded: communities={CommunityGroup.objects.count()}, interests={Interest.objects.count()}, "
            f"onboarding_links={OnboardingLink.objects.count()}, feeds={oulu.source_feeds.count()}, "
            f"glossary={GlossaryTerm.objects.count()}, context={ContextEntry.objects.count()}"
        ))
