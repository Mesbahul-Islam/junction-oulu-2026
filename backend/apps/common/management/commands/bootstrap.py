"""One command to get a working dev database: migrate, seed, create an admin.

Safe to run repeatedly. Docker runs it on every `docker compose up` via the
one-shot `setup` service, before web/worker/beat start. Order:

1. migrate
2. seed_demo, seed_markets (fast, idempotent)
3. admin user, demo readers
4. Fantasy Liiga, first start only: sync_liiga (real season data from the Liiga
   API) then seed_fantasy_demo. Skipped once fantasy data exists, so restarts stay
   fast; a Liiga API failure is reported but doesn't stop the app from starting.
"""

import datetime
import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

# Local demo accounts (also listed in docs/GUIDE.md). Never use these anywhere shared.
DEMO_READER_PASSWORD = "demo-reader"
DEMO_READERS = [
    # email, situation, language, interest slugs, days since arrival in Finland
    ("newcomer@example.com", "newcomer", "uk", ["housing", "work", "health", "services"], 5),
    ("fan@example.com", "resident", "fi", ["sports", "culture", "events"], None),
]


# Topic communities the demo readers belong to (besides Oulu), so their Community News has variety.
DEMO_MEMBERSHIPS = {
    "newcomer@example.com": ["oulu-newcomers", "oulu-families"],
    "fan@example.com": ["karpat-sports", "oulu-culture"],
}

# Neighbours who write the demo posts: email, display name, language, communities.
DEMO_NEIGHBOURS = [
    ("aino@example.com", "Aino", "fi", ["oulu", "oulu-culture", "oulu-families"]),
    ("jussi@example.com", "Jussi", "fi", ["oulu", "karpat-sports"]),
    ("hassan@example.com", "Hassan", "ar", ["oulu", "oulu-newcomers"]),
    ("iryna@example.com", "Iryna", "uk", ["oulu", "oulu-newcomers", "oulu-families"]),
    ("maria@example.com", "Maria", "en", ["oulu", "oulu-students", "oulu-culture"]),
    ("erik@example.com", "Erik", "sv", ["oulu", "oulu-students", "oulu-families"]),
]

# 20 member posts, newest first (author, community, text), in the languages people really write in.
# Posts ending in "?" also reach the newsroom as reader questions.
DEMO_POSTS = [
    ("jussi@example.com", "karpat-sports", "Kärpät voitti Tapparan 4–2! Raksilan tunnelma oli ihan huikea."),
    ("iryna@example.com", "oulu-newcomers",
     "Порада: картку Kela можна замовити онлайн, але спочатку потрібні банківські коди. Мені допоміг чат OmaKela."),
    ("maria@example.com", "oulu", "Found a black cat with a red collar near the Tuira bridge this morning. It's safe at my place, message me if it's yours!"),
    ("hassan@example.com", "oulu", "هل يعرف أحد طبيب أسنان في أولو يتحدث العربية أو الإنجليزية؟"),
    ("fan@example.com", "karpat-sports", "Myydäänkö lauantain peliin vielä lippuja ovelta?"),
    ("aino@example.com", "oulu-culture", "Taidemuseon perjantai-illan opastus on tällä viikolla suomeksi ja englanniksi, klo 17."),
    ("erik@example.com", "oulu-families", "Finns det svenskspråkig dagvård i Uleåborg?"),
    ("newcomer@example.com", "oulu-newcomers", "Free Finnish conversation group at the main library on Tuesdays at 17:00. Total beginners welcome, I went last week and it was great."),
    ("jussi@example.com", "oulu", "Nallikarin talviuintipaikan sauna on taas auki. Keskiviikkoisin yhteinen uintiilta klo 18, uudetkin mukaan!"),
    ("maria@example.com", "oulu-students", "Is the PSOAS queue faster for shared flats than for studios?"),
    ("hassan@example.com", "oulu-newcomers", "How long did your residence permit card take to arrive after Migri approved the application?"),
    ("aino@example.com", "oulu", "Pekurinkulman kirpputorille mahtuu vielä myyjiä lauantaina. Pöytä on ilmainen, tule ajoissa!"),
    ("iryna@example.com", "oulu-families", "Хтось знає, де в Оулу недорого купити зимовий одяг для дітей?"),
    ("maria@example.com", "oulu-culture", "Anyone going to the music video festival this weekend? Looking for people to go with, I'm new here."),
    ("erik@example.com", "oulu-students", "Selling a winter bike with studded tyres, 60 €. Pick up at the Linnanmaa campus this week."),
    ("aino@example.com", "oulu", "Milloin Hupisaarten uusi kävelysilta valmistuu?"),
    ("fan@example.com", "oulu", "Kärpät home game on Saturday: the 18:30 bus 3 from the centre gets very full, take the 18:10 one."),
    ("newcomer@example.com", "oulu", "Does anyone know where to get a library card in Oulu? I arrived last week. Thanks!"),
    ("fan@example.com", "oulu", "Ice on the Toppilansalmi walking path this morning, careful with strollers and bikes."),
    ("newcomer@example.com", "oulu", "Ukrainian-speaking parents in Oulu: we meet at the main library on Sundays at 12, everyone welcome."),
    # A rumour members reported as misleading; it gets a Community Note (DEMO_NOTES).
    ("jussi@example.com", "oulu", "Heard Kela will stop paying housing allowance to everyone in Oulu next month. Better start looking for a cheaper flat now!"),
]

# Replies under demo posts: (index in DEMO_POSTS, author, text). Authors are members of that post's community.
DEMO_REPLIES = [
    (0, "fan@example.com", "Mikä ilta! Kolmas maali oli kauden paras."),
    (2, "jussi@example.com", "Näin saman kissan eilen Tuirassa. Toivottavasti omistaja löytyy!"),
    (3, "aino@example.com", "Keskustan hammaslääkäriasemalla palvellaan myös englanniksi, kysy ajanvarauksesta."),
    (3, "maria@example.com", "My dentist at the city health centre spoke English, just ask when you book."),
    (6, "aino@example.com", "Keskustassa on ruotsinkielinen päiväkoti. Kysy kaupungin varhaiskasvatuksen palveluohjauksesta."),
    (10, "iryna@example.com", "Мені картку надіслали приблизно через два тижні після рішення."),
    (10, "newcomer@example.com", "About two weeks for me too."),
    (12, "aino@example.com", "Kierrätyskeskus on halvin, ja Pekurinkulman kirpputori lauantaisin."),
    (17, "maria@example.com", "Just go to any library with your ID, it took me five minutes!"),
]

# Community Notes on demo posts: (index in DEMO_POSTS, author, claim, context, source, raters, flaggers).
# The first has helpful ratings from residents and a newcomer, so it is shown ("Readers added context");
# the second still needs ratings. Flaggers reported the post as false or misleading.
DEMO_NOTES = [
    (20, "maria@example.com", "Kela hasn't announced any end to housing allowance in Oulu.",
     "Housing allowance is decided by Kela case by case, under the same national rules everywhere in Finland. "
     "There is no Oulu-wide stop. If you're worried about your own allowance, check your decision in OmaKela or ask Kela.",
     "https://www.kela.fi/housing-allowance", ["aino@example.com", "newcomer@example.com", "erik@example.com"],
     ["newcomer@example.com", "iryna@example.com"]),
    (8, "aino@example.com", "The shared swimming evening may not be every Wednesday.",
     "Winter opening hours at Nallikari change during the season. Check the city's sauna page before you go.",
     "https://www.ouka.fi", ["erik@example.com"], []),
]


class Command(BaseCommand):
    help = "Migrate, load demo data and create the dev admin user (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--no-seed", action="store_true", help="Only migrate and create the admin.")
        parser.add_argument("--no-fantasy", action="store_true", help="Skip the Liiga sync and fantasy demo data.")

    def handle(self, *args, no_seed=False, no_fantasy=False, **options):
        call_command("migrate", interactive=False, verbosity=1)
        if not no_seed:
            call_command("seed_demo")
            call_command("seed_markets")
        self._ensure_admin()
        if not no_seed:
            self._ensure_demo_readers()
            self._ensure_demo_posts()
            self._ensure_rewards()
            if not no_fantasy and os.environ.get("SEED_FANTASY", "true").lower() not in ("0", "false", "no"):
                self._ensure_fantasy()
        self.stdout.write(self.style.SUCCESS("Bootstrap complete."))

    def _ensure_fantasy(self):
        """First start only: import the Liiga season, then create demo managers and leagues."""
        from apps.fantasy.models import Player, Sponsor, Squad

        if Squad.objects.exists():
            self.stdout.write("Fantasy data already present; skipping Liiga sync (run `manage.py sync_liiga` to update).")
            if not Sponsor.objects.exists():
                try:
                    call_command("seed_sponsors")  # brand partners and prizes, added after the first fantasy release
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"Brand prizes skipped: {exc}. Run later: manage.py seed_sponsors"))
            return
        try:
            if not Player.objects.exists():
                self.stdout.write("Importing the Liiga season (first start, needs internet)...")
                call_command("sync_liiga")
            call_command("seed_fantasy_demo")
            call_command("seed_sponsors")
        except Exception as exc:  # network down, Liiga API changed ...: the rest of the app still starts
            self.stdout.write(self.style.WARNING(
                f"Fantasy seed skipped: {type(exc).__name__}: {exc}\n"
                "Run later: docker compose exec web python manage.py sync_liiga && "
                "docker compose exec web python manage.py seed_fantasy_demo"))

    def _ensure_rewards(self):
        """Reward partners, perks and sample contribution statistics, first start only."""
        from apps.rewards.models import Partner

        if not Partner.objects.exists():
            call_command("seed_rewards")

    def _ensure_demo_readers(self):
        """Two readers with opposite profiles, to compare personalised feeds, plus the neighbours
        who write the demo posts (local dev only)."""
        from apps.accounts.models import Interest
        from apps.communities.models import CommunityGroup, Membership

        User = get_user_model()
        for email, situation, language, interests, days in DEMO_READERS:
            if User.objects.filter(email=email).exists():
                continue
            user = User.objects.create_user(
                email=email, password=DEMO_READER_PASSWORD, reader_situation=situation, preferred_language=language,
                arrival_date=datetime.date.today() - datetime.timedelta(days=days) if days is not None else None,
                onboarded=True,
            )
            user.profile.interests.set(Interest.objects.filter(slug__in=interests))
            self.stdout.write(f"Created demo reader {email}.")
        for email, name, language, _ in DEMO_NEIGHBOURS:
            if not User.objects.filter(email=email).exists():
                User.objects.create_user(email=email, password=DEMO_READER_PASSWORD, display_name=name,
                                         preferred_language=language, onboarded=True)
        memberships = {email: ["oulu", *slugs] for email, slugs in DEMO_MEMBERSHIPS.items()}
        memberships.update({email: slugs for email, _, _, slugs in DEMO_NEIGHBOURS})
        groups = {g.slug: g for g in CommunityGroup.objects.all()}
        for user in User.objects.filter(email__in=memberships):
            for slug in memberships[user.email]:
                if slug in groups:
                    Membership.objects.get_or_create(user=user, community=groups[slug])

    def _ensure_demo_posts(self):
        """Member posts so the app's Community News tab isn't empty. Adds any that are missing."""
        from apps.communities.models import CommunityGroup, Post
        from apps.communities.services import register_post

        User = get_user_model()
        authors = {u.email: u for u in User.objects.filter(email__in={email for email, _, _ in DEMO_POSTS})}
        groups = {g.slug: g for g in CommunityGroup.objects.all()}
        now = timezone.now()
        created = 0
        for i, (email, slug, body) in enumerate(DEMO_POSTS):
            if email not in authors or slug not in groups or Post.objects.filter(community=groups[slug], body=body).exists():
                continue
            register_post(Post.objects.create(community=groups[slug], author=authors[email], body=body))
            created += 1
        if created:
            # Spread all demo posts over the last two days in list order, so the feed looks lived in.
            for i, (email, slug, body) in enumerate(DEMO_POSTS):
                Post.objects.filter(community__slug=slug, author__email=email, body=body).update(
                    created_at=now - datetime.timedelta(hours=2.5 * i))
            self.stdout.write(f"Created {created} demo community posts.")
        self._ensure_demo_engagement()
        self._ensure_demo_notes()

    def _ensure_demo_notes(self):
        """Community Notes on demo posts: one shown, one waiting for ratings (see DEMO_NOTES)."""
        from apps.communities.models import Membership, Post, PostFlag, PostLike
        from apps.notes import services as notes

        User = get_user_model()
        users = {u.email: u for u in User.objects.all()}
        for index, author, claim, context, source, raters, flaggers in DEMO_NOTES:
            email, slug, body = DEMO_POSTS[index]
            post = Post.objects.filter(community__slug=slug, author__email=email, body=body, parent=None).first()
            if not post or post.community_notes.exists() or author not in users:
                continue
            for flagger in flaggers:
                PostFlag.objects.get_or_create(post=post, user=users[flagger], defaults={"reason": "false"})
            if index == 20:  # the rumour spreads: make it hot
                for user_id in Membership.objects.filter(community=post.community).exclude(user=post.author) \
                        .values_list("user_id", flat=True)[:14]:
                    PostLike.objects.get_or_create(post=post, user_id=user_id)
                Post.objects.filter(pk=post.pk).update(share_count=4)
            note = notes.create_note(author=users[author], post=post, claim_summary=claim, context=context,
                                     citation_urls=[source])
            for rater in raters:
                if rater in users:
                    notes.rate(note, users[rater], "helpful", ["clear_sources", "important_context"])

    def _ensure_demo_engagement(self):
        """Replies, likes and share counts on the demo posts, so the post actions show real numbers."""
        from apps.communities.models import Membership, Post, PostLike
        from apps.communities.services import register_post

        User = get_user_model()
        posts = [Post.objects.filter(community__slug=slug, author__email=email, body=body, parent=None).first()
                 for email, slug, body in DEMO_POSTS]
        users = {u.email: u for u in User.objects.all()}
        for index, email, body in DEMO_REPLIES:
            parent = posts[index]
            if parent and email in users and not parent.replies.filter(body=body).exists():
                register_post(Post.objects.create(community=parent.community, author=users[email], body=body, parent=parent))
        if PostLike.objects.filter(post__in=[p for p in posts if p]).exists():
            return  # already seeded once; leave real likes and shares alone
        for i, post in enumerate(posts):
            if not post:
                continue
            members = list(Membership.objects.filter(community=post.community).exclude(user=post.author)
                           .order_by("user__email").values_list("user_id", flat=True))
            for user_id in members[: (i * 5 + 3) % (len(members) + 1)]:
                PostLike.objects.get_or_create(post=post, user_id=user_id)
            Post.objects.filter(pk=post.pk).update(share_count=(i * 3 + 1) % 9)

    def _ensure_admin(self):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not email or not password:
            self.stdout.write("DJANGO_SUPERUSER_EMAIL/PASSWORD not set; skipping admin user.")
            return
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            self.stdout.write(f"Admin {email} already exists.")
            return
        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created admin {email}."))
