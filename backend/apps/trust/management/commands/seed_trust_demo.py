"""Demo activity for trusted voices in the Oulu community (local dev only).

Creates four demo raters (*@demo.trust) in different life situations, then lets two existing
members earn trust through the real rules: notes rated by people in different situations,
questions the editors accepted, and likes. One is approved as a trusted voice by the dev admin,
the other is left eligible so the approval step can be shown. Safe to run again.

    manage.py seed_trust_demo
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.communities.models import CommunityContribution, CommunityGroup, Membership, Post, PostLike
from apps.feed.models import Snippet
from apps.notes import services as notes
from apps.notes.models import CommunityNote
from apps.trust.models import MemberTrust
from apps.trust.services import decide, refresh

RATERS = [("student", "student"), ("seasonal", "seasonal_worker"), ("newcomer", "newcomer"), ("local", "resident")]
QUESTIONS = {
    "maria": ["Where can I renew a bus card for my child?", "Which health centre do I call at night?"],
    "aino": ["Is the library open on Sunday?", "Where do I register a newborn?", "How do I sign up for Finnish classes?"],
}


class Command(BaseCommand):
    help = "Create demo activity so trusted voices show in the Oulu community"

    def handle(self, *args, **opts):
        User = get_user_model()
        community = CommunityGroup.objects.filter(slug="oulu").first()
        snippets = list(Snippet.objects.filter(community=community, review_status="published").prefetch_related("source_documents"))
        if community is None or not snippets:
            raise CommandError("Needs the Oulu community and at least one published story")

        raters = []
        for name, situation in RATERS:
            user, _ = User.objects.get_or_create(
                email=f"{name}@demo.trust",
                defaults={"username": f"{name}_demo", "reader_situation": situation, "onboarded": True},
            )
            if not user.has_usable_password():
                user.set_password("demo1234")
                user.save()
            Membership.objects.get_or_create(user=user, community=community)
            raters.append(user)

        for username, questions in QUESTIONS.items():
            member = User.objects.filter(username=username).first()
            if member is None:
                continue
            Membership.objects.get_or_create(user=member, community=community)
            # Notes that point readers to the original source, rated by raters in different situations.
            for snippet in snippets:
                if CommunityNote.objects.filter(author=member, snippet=snippet).exists():
                    continue
                doc = snippet.source_documents.first()
                note = notes.create_note(
                    author=member, snippet=snippet,
                    claim_summary="The full original article has more detail than this summary.",
                    context="Read the original for the complete background and quotes.",
                    citation_urls=[doc.url if doc else "https://www.kaleva.fi/"],
                )
                for rater in raters:
                    notes.rate(note, rater, "helpful", [])
            # Questions the editors accepted.
            for body in questions:
                CommunityContribution.objects.get_or_create(
                    community=community, author=member, kind="question", body=body,
                    defaults={"status": "accepted", "contributor_consent": True},
                )
            # Likes from other members on their posts.
            for post in Post.objects.filter(author=member, community=community, status="visible"):
                for rater in raters:
                    PostLike.objects.get_or_create(post=post, user=rater)

        admin = User.objects.filter(is_superuser=True).order_by("pk").first()
        for username in QUESTIONS:
            member = User.objects.filter(username=username).first()
            if member is None:
                continue
            trust = refresh(member, community)
            self.stdout.write(f"@{username}: {trust.score} points, {trust.verified} verified, {trust.level}")
        maria = MemberTrust.objects.filter(user__username="maria", community=community).first()
        if maria and maria.level == MemberTrust.Level.ELIGIBLE and admin:
            decide(maria, admin, True, "Demo: approved by the dev admin")
            self.stdout.write("@maria approved as a trusted voice; @aino left for an editor to decide")
        self.stdout.write(self.style.SUCCESS("Done"))
