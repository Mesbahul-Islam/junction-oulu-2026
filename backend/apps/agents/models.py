"""The AI newsroom's bookkeeping (FR-3.1–3.3, FR-3.6).

A newsroom ``AgentRun`` fetches the Kaleva feeds, lets Jev pick the stories worth covering
and sends each one through the desks (brief and explanation, translator, fact-checker,
standards editor) to the human editors. ``RunStory`` follows one story through the desks
so the dashboard can show live progress; ``AgentStep`` logs each piece of desk work.
"""

from django.db import models

from apps.common.models import TimeStampedModel

# The newsroom's desks in working order. Each is an agent; the human editors come after.
DESKS = [
    ("wire", "Wire desk"),
    ("news_editor", "News editor"),
    ("explainer", "Brief and explanation"),
    ("translator", "Translator"),
    ("fact_checker", "Fact-checker"),
    ("standards", "Standards editor"),
    ("copy_desk", "Copy desk"),
    ("community_vote", "Community vote"),
]


class AgentRun(TimeStampedModel):
    class Trigger(models.TextChoices):
        SCHEDULE = "schedule", "Schedule"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    community = models.ForeignKey(
        "communities.CommunityGroup",
        on_delete=models.CASCADE,
        related_name="agent_runs",
    )
    trigger = models.CharField(max_length=32, choices=Trigger.choices, default=Trigger.SCHEDULE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    max_stories = models.PositiveSmallIntegerField(default=4)
    desk = models.CharField(max_length=20, blank=True, help_text="Desk working right now (while running).")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    state = models.JSONField(default=dict, blank=True, help_text="Run summary: what each desk did.")
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"AgentRun #{self.pk} ({self.community_id}, {self.status})"


class RunStory(TimeStampedModel):
    """One story picked by the news editor, followed through the desks."""

    class Stage(models.TextChoices):
        PICKED = "picked", "Picked"
        EXPLAINER = "explainer", "Brief and explanation"
        TRANSLATOR = "translator", "Translator"
        FACT_CHECKER = "fact_checker", "Fact-checker"
        STANDARDS = "standards", "Standards editor"
        COPY_DESK = "copy_desk", "Copy desk"
        DONE = "done", "With the editors"
        FAILED = "failed", "Failed"

    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="stories")
    rank = models.PositiveSmallIntegerField()
    source_document = models.ForeignKey("feed.SourceDocument", null=True, on_delete=models.SET_NULL, related_name="+")
    title = models.CharField(max_length=500)
    jev_score = models.FloatField(null=True, blank=True)
    ranked_by = models.CharField(max_length=20, blank=True)  # "jev" | "heuristic"
    pick_reasons = models.JSONField(default=list, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.PICKED)
    detail = models.CharField(max_length=200, blank=True)  # e.g. "Ukrainian (3 of 7)"
    snippet = models.ForeignKey("feed.Snippet", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["run", "rank"]

    def __str__(self):
        return f"#{self.rank} {self.title[:60]}"


class CoverageCandidate(TimeStampedModel):
    """An article on the shortlist members vote on ("What should we cover next?").

    Each run's news editor posts the best stories it didn't cover yet; members' votes then
    count in the next run's pick. Titles are machine-translated so everyone can vote.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open for votes"
        COVERED = "covered", "Covered"
        DROPPED = "dropped", "Dropped"

    community = models.ForeignKey("communities.CommunityGroup", on_delete=models.CASCADE, related_name="coverage_candidates")
    source_document = models.ForeignKey("feed.SourceDocument", on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    jev_score = models.FloatField(default=0.0)
    ranked_by = models.CharField(max_length=20, blank=True)
    reasons = models.JSONField(default=list, blank=True)
    titles = models.JSONField(default=dict, blank=True)  # {language: title}; Finnish is the source title
    covered_by = models.ForeignKey(RunStory, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-jev_score"]
        constraints = [models.UniqueConstraint(fields=["community", "source_document"], name="uniq_candidate_doc")]

    def __str__(self):
        return self.source_document.title[:80]


class CoverageVote(TimeStampedModel):
    """A member's vote for a shortlisted story (one per member and story)."""

    candidate = models.ForeignKey(CoverageCandidate, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="coverage_votes")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["candidate", "user"], name="uniq_coverage_vote")]


class AgentStep(TimeStampedModel):
    """One piece of desk work: a whole-run desk (wire, news editor) or one desk on one story."""

    Agent = models.TextChoices("Agent", DESKS)

    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="steps")
    story = models.ForeignKey(RunStory, null=True, blank=True, on_delete=models.CASCADE, related_name="steps")
    agent = models.CharField(max_length=32, choices=Agent.choices)
    input = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    snippet = models.ForeignKey(
        "feed.Snippet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_steps",
    )
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.agent} step of run #{self.run_id}"
