"""Translate shown Community Notes into the readers' languages (like community posts)."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.notes.tasks.translate_note")
def translate_note(note_id: int) -> list[str]:
    """One plain-text call per language; only answers in the right language are kept."""
    from apps.agents.graph.llm import get_llm, ollama_model_problem, resolve
    from apps.agents.graph.text import LANGUAGE_LABELS, language_problem
    from apps.communities.services import post_translation_targets

    from .models import CommunityNote

    note = CommunityNote.objects.select_related("post__community").filter(pk=note_id, post__isnull=False).first()
    llm = get_llm("translator")
    if note is None or llm.is_stub or ollama_model_problem(resolve("translator")):
        return []
    done, translations = [], dict(note.translations or {})
    for lang in post_translation_targets(note.post):
        if lang == note.language or lang in translations:
            continue
        name = LANGUAGE_LABELS.get(lang, lang)
        parts = {}
        for field in ("claim_summary", "context"):
            try:
                text = llm.text(f"Translate this text into {name}. Keep names, numbers and links. "
                                f"Reply with the translation only.\n\nTEXT:\n{getattr(note, field)}").strip().strip('"')
            except Exception as exc:
                logger.warning("Note %s: %s translation failed: %s", note_id, lang, exc)
                break
            if not text or language_problem(text, lang):
                break
            parts[field] = text
        if len(parts) == 2:
            translations[lang] = parts
            done.append(lang)
    if done:
        CommunityNote.objects.filter(pk=note_id).update(translations=translations)
    return done
