from django.conf import settings
from rest_framework import serializers

from .models import DESKS, AgentRun, RunStory

DESK_INFO = {
    "wire": ("Fetches the Kaleva RSS feeds, drops opinion and paid content", "Kaleva RSS"),
    "news_editor": ("Ranks every article for Oulu's readers, adds members' votes, picks the top ones", ""),
    "explainer": ("Writes a source-grounded brief and explains supported reader implications", ""),
    "translator": ("Translates into every reader language (Sámi is left to people)", ""),
    "fact_checker": ("Checks the draft's numbers against the article", "rules, no AI model"),
    "standards": ("JSN checks: risk, crime, minors, right of reply...", "rules, no AI model"),
    "copy_desk": ("Files the story: Ready to send or Needs review", "rules, no AI model"),
    "community_vote": ("Posts the next shortlist for members to vote on", "members, in the app"),
}
RUN_DESKS = {"wire", "news_editor", "community_vote"}


def _who(desk: str) -> str:
    from .graph import llm

    fixed = DESK_INFO[desk][1]
    if fixed:
        return fixed
    if desk == "news_editor":
        return "Jev (TypeSafe AI) + members' votes" if settings.TYPESAFE_API_KEY else "heuristic + members' votes"
    spec = llm.resolve(desk)["spec"]
    return "offline stub (no AI model)" if spec == "stub" else spec


class AgentRunSerializer(serializers.ModelSerializer):
    community_name = serializers.CharField(source="community.name", read_only=True)
    counts = serializers.SerializerMethodField()
    snippet_ids = serializers.SerializerMethodField()

    class Meta:
        model = AgentRun
        fields = ["id", "community", "community_name", "trigger", "status", "max_stories", "desk", "started_at",
                  "finished_at", "error", "counts", "snippet_ids", "created_at"]
        read_only_fields = fields

    def get_counts(self, run) -> dict:
        stories = list(run.stories.select_related("snippet"))
        snippets = [s.snippet for s in stories if s.snippet]
        return {
            "stories": len(stories),
            "ready": sum(1 for s in snippets if s.review_level == "ready" and not s.published_at),
            "needs_review": sum(1 for s in snippets if s.review_level == "needs_review" and not s.published_at),
            "published": sum(1 for s in snippets if s.published_at),
            "failed": sum(1 for s in stories if s.stage == RunStory.Stage.FAILED),
        }

    def get_snippet_ids(self, run) -> list[int]:
        return [s.snippet_id for s in run.stories.all() if s.snippet_id]


class RunStorySerializer(serializers.ModelSerializer):
    url = serializers.CharField(source="source_document.url", default="", read_only=True)
    section = serializers.CharField(source="source_document.publisher", default="", read_only=True)
    verdict = serializers.CharField(source="snippet.review_level", default="", read_only=True)
    reasons = serializers.JSONField(source="snippet.review_reasons", default=list, read_only=True)
    review_status = serializers.CharField(source="snippet.review_status", default="", read_only=True)
    published_at = serializers.DateTimeField(source="snippet.published_at", default=None, read_only=True)
    headline = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()

    class Meta:
        model = RunStory
        fields = ["id", "rank", "title", "url", "section", "jev_score", "ranked_by", "pick_reasons", "stage", "detail",
                  "error", "snippet", "headline", "languages", "verdict", "reasons", "review_status", "published_at"]
        read_only_fields = fields

    def get_headline(self, story) -> str:
        if not story.snippet_id:
            return ""
        v = story.snippet.versions.filter(language="fi").first()
        return v.headline if v else ""

    def get_languages(self, story) -> list[str]:
        return list(story.snippet.versions.values_list("language", flat=True)) if story.snippet_id else []


class AgentRunDetailSerializer(AgentRunSerializer):
    """A run as the live newsroom view shows it: each desk's progress and each story's."""

    desks = serializers.SerializerMethodField()
    stories = RunStorySerializer(many=True, read_only=True)

    class Meta(AgentRunSerializer.Meta):
        fields = AgentRunSerializer.Meta.fields + ["state", "desks", "stories"]
        read_only_fields = fields

    def get_desks(self, run) -> list[dict]:
        steps = list(run.steps.all())
        stories = list(run.stories.all())
        live = run.status in (AgentRun.Status.QUEUED, AgentRun.Status.RUNNING)
        out = []
        for key, label in DESKS:
            done_steps = [s for s in steps if s.agent == key]
            active = live and run.desk == key
            if key in RUN_DESKS:
                total, done = 1, len(done_steps)
                summary = (run.state or {}).get(key) or (done_steps[-1].output if done_steps else {})
            else:
                total, done = len(stories), len({s.story_id for s in done_steps})
                summary = {}
            working_on = next((s for s in stories if s.stage == key), None) if active else None
            status = "active" if active else "done" if total and done >= total else (
                "failed" if run.status == AgentRun.Status.FAILED and done < total else "waiting")
            if not live and total == 0:
                status = "skipped"
            out.append({
                "key": key, "label": label, "does": DESK_INFO[key][0], "who": _who(key), "status": status,
                "done": done, "total": total, "summary": summary,
                "seconds": round(sum(s.duration_ms for s in done_steps) / 1000, 1),
                "working_on": {"rank": working_on.rank, "title": working_on.title[:90], "detail": working_on.detail}
                if working_on else None,
            })
        return out


class AgentRunCreateSerializer(serializers.Serializer):
    max_stories = serializers.IntegerField(required=False, min_value=1, max_value=20)
    community = serializers.SlugField(required=False, help_text="The town to run for (a geographic community's slug)")

    def validate_community(self, slug):
        from apps.communities.models import CommunityGroup

        city = CommunityGroup.objects.filter(slug=slug, kind=CommunityGroup.Kind.GEO, is_active=True).first()
        if city is None:
            raise serializers.ValidationError("Not a town the newsroom covers.")
        return city


class CitySerializer(serializers.Serializer):
    """A town the newsroom covers, for the dashboard's city picker and Cities table."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    municipality = serializers.CharField()
    municipality_code = serializers.CharField()
    member_count = serializers.IntegerField()
    last_run_at = serializers.DateTimeField(allow_null=True)
    facts = serializers.SerializerMethodField()

    def get_facts(self, city) -> dict:
        from apps.communities.demographics import town_facts

        return town_facts(city)


class AddCitySerializer(serializers.Serializer):
    municipality_code = serializers.RegexField(r"^\d{3}$")


class SendSerializer(serializers.Serializer):
    snippets = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    all_ready = serializers.BooleanField(required=False, default=False)
