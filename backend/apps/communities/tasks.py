"""Background work for Community News: machine translation of member posts."""

import logging

from celery import shared_task
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PostTranslationOut(BaseModel):
    text: str = Field(description="The post translated into the target language")


@shared_task(name="apps.communities.tasks.translate_post")
def translate_post(post_id: int) -> list[str]:
    """Translate a community post into every language its community reads, one language
    per call. Only translations that pass the language check are stored; with no working
    model nothing is stored (readers then see the original)."""
    from apps.agents.graph.llm import get_llm, structured_call
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
    from apps.agents.graph.llm import ollama_model_problem, resolve

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
            f"{LANGUAGE_LABELS.get(lang, lang)} ({lang}). Keep its meaning, tone, names, times and numbers. "
            f"Translate only; don't add anything.\n\nMESSAGE:\n{post.body}"
        )
        errors: list = []
        out = structured_call(prompt, PostTranslationOut, lambda: PostTranslationOut(text=""), llm=llm, errors=errors, agent="translator")
        text = (out.text or "").strip()
        if not text or errors or language_problem(text, lang):
            logger.info("Post %s: no usable %s translation (%s)", post_id, lang, errors or language_problem(text, lang))
            continue
        PostTranslation.objects.create(post=post, language=lang, text=text, model=getattr(llm, "spec", ""))
        done.append(lang)
    return done
