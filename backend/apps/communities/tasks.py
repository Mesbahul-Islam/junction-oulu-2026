"""Background work for Community News: machine translation of member posts."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.communities.tasks.translate_post")
def translate_post(post_id: int) -> list[str]:
    """Translate a community post into every language its community reads, one language
    per call, as plain text (no JSON for the model to get wrong). A translation is stored
    only if it is in the right language; with no working model nothing is stored (readers
    then see the original)."""
    from apps.agents.graph.llm import get_llm, ollama_model_problem, resolve
    from apps.agents.graph.text import LANGUAGE_LABELS, language_problem

    from . import services
    from .models import Post, PostTranslation

    post = Post.objects.select_related("community").filter(pk=post_id).first()
    if not post or post.status == Post.Status.REMOVED:
        return []
    llm = get_llm("translator")
    if llm.is_stub:
        return []
    # Don't tie up the worker on an unreachable Ollama server or a model that isn't pulled.
    problem = ollama_model_problem(resolve("translator"))
    if problem:
        logger.warning("Not translating post %s: %s", post_id, problem)
        return []
    done = []
    for lang in services.post_translation_targets(post):
        if PostTranslation.objects.filter(post=post, language=lang).exists():
            continue
        prompt = (
            f"Translate this message written by a member of a local community in Finland into "
            f"{LANGUAGE_LABELS.get(lang, lang)}. Keep its meaning, tone, names, times and numbers. "
            f"Reply with the translation only, nothing else.\n\nMESSAGE:\n{post.body}"
        )
        try:
            text = llm.text(prompt).strip().strip('"').strip()
        except Exception as exc:  # network, model error: try again on the next post registration
            logger.warning("Post %s: %s translation failed: %s", post_id, lang, exc)
            continue
        problem = "empty answer" if not text else language_problem(text, lang)
        if problem:
            logger.info("Post %s: %s translation not stored (%s)", post_id, lang, problem)
            continue
        PostTranslation.objects.create(post=post, language=lang, text=text, model=getattr(llm, "spec", ""))
        done.append(lang)
    return done
