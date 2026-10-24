"""Show which model each newsroom agent uses, and optionally test each one.

    python manage.py llm_check          # configuration only
    python manage.py llm_check --ping   # also one tiny real call per distinct model
"""

import time

from django.core.management.base import BaseCommand
from pydantic import BaseModel

from apps.agents.graph import llm


class Ping(BaseModel):
    ok: bool
    word: str


class Command(BaseCommand):
    help = "Show (and with --ping, test) the LLM configured for each agent."

    def add_arguments(self, parser):
        parser.add_argument("--ping", action="store_true", help="Make one small real call per distinct model.")

    def _check_ollama_models(self, rows):
        """Ollama only serves models that were pulled first; say which are missing."""
        for r in rows:
            if r["provider"] != "ollama" or r["stub_reason"]:
                continue
            try:
                import ollama

                client = ollama.Client(host=r["base_url"] or None, timeout=5)
                names = {m.model for m in client.list().models}
            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f"\n  Can't reach Ollama ({r['base_url'] or 'OLLAMA_HOST'}): {exc}\n"
                    "  Ollama is not part of docker-compose. Set LLM_BASE_URL in .env to a running Ollama server "
                    "(e.g. http://host.docker.internal:11434) and run `docker compose up -d`."))
                return
            wanted = r["model"] if ":" in r["model"] else f"{r['model']}:latest"
            if wanted not in names:
                self.stdout.write(self.style.WARNING(
                    f"\n  Ollama has no model {r['model']!r} yet. Download it once on the Ollama server with:\n"
                    f"    ollama pull {r['model']}"))
            return

    def handle(self, *args, ping, **options):
        rows = [llm.resolve(agent) for agent in llm.AGENTS]
        width = max(len(r["spec"]) for r in rows)
        for r in rows:
            status = self.style.WARNING(f"STUB: {r['stub_reason']}") if r["stub_reason"] else self.style.SUCCESS("ready")
            self.stdout.write(f"  {r['agent']:<13} {r['spec']:<{width}}  {status}")
        self._check_ollama_models(rows)
        if not ping:
            self.stdout.write("\nRun with --ping to test each model with a real call.")
            return

        self.stdout.write("")
        tested = set()
        for agent in llm.AGENTS:
            client = llm.get_llm(agent)
            spec = getattr(client, "spec", "stub")
            if client.is_stub or spec in tested:
                continue
            tested.add(spec)
            t0 = time.perf_counter()
            try:
                out = client.structured('Reply with ok=true and word="Oulu".', Ping)
                ms = int((time.perf_counter() - t0) * 1000)
                self.stdout.write(self.style.SUCCESS(f"  {spec}: OK in {ms} ms -> {out.model_dump()}"))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  {spec}: FAILED: {type(exc).__name__}: {str(exc)[:300]}"))
        if not tested:
            self.stdout.write("  Nothing to ping: every agent is on the offline stub.")
