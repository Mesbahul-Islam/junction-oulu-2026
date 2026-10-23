"""Agent run bookkeeping (FR-3.1–3.3, FR-3.6).

Every LangGraph pipeline execution is an ``AgentRun``; every node execution in
that run is an ``AgentStep``. Together they form the audit trail that shows
editors which AI "newsroom role" produced what.
"""

from django.db import models

from apps.common.models import TimeStampedModel


class AgentRun(TimeStampedModel):
    class Trigger(models.TextChoices):
        SCHEDULE = "schedule", "Schedule"
        MANUAL = "manual", "Manual"
        COMMUNITY_SIGNAL = "community_signal", "Community signal"

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
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    state = models.JSONField(default=dict, blank=True, help_text="Final LangGraph state (JSON-safe).")
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"AgentRun #{self.pk} ({self.community_id}, {self.status})"


class AgentStep(TimeStampedModel):
    class Agent(models.TextChoices):
        SCOUT = "scout", "Scout"
        ASSIGNMENT = "assignment", "Assignment"
        SYNTHESIZER = "synthesizer", "Synthesizer"
        EXPLAINER = "explainer", "Explainer"
        TRANSLATOR = "translator", "Translator"
        FACT_CHECKER = "fact_checker", "Fact-checker"
        STANDARDS = "standards", "Standards"
        TAGGING = "tagging", "Tagging"

    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="steps")
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
