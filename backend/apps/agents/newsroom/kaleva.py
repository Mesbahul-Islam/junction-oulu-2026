"""Read a Kaleva article in full: the tool the brief desk's model calls.

The RSS feed only carries a headline and a sentence or two. The free articles in it
("rss-maksuttomat") have their full text on the article page, inside ``<article>``, so a
plain request is enough: no browser. Only kaleva.fi links are fetched (the model can't
make the server request anything else), and the text is cached on the ``SourceDocument``
so each article is downloaded once.
"""

from __future__ import annotations

import html
import json
import logging
import re
from urllib.parse import urlparse

from django.apps import apps
from django.utils.dateparse import parse_datetime

from .wire import USER_AGENT

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = {"kaleva.fi", "www.kaleva.fi"}
MAX_CHARS = 9000  # enough for a long news article; keeps small models within their context
TIMEOUT = 15

_ARTICLE = re.compile(r"<article\b.*?</article>", re.S | re.I)
_PARA = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_LD_JSON = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)
# Promotions and page furniture inside <article> that aren't part of the story.
_NOT_STORY = re.compile(r"tutustu peleihin|aivojumppaa|^tilaa\b|lue myös|kirjaudu|^mainos|uutiskirje", re.I)


def allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return urlparse(url).scheme == "https" and host in ALLOWED_HOSTS


def extract(page: str) -> dict:
    """{"title", "published", "text"} from an article page ("" where not found)."""
    meta = {}
    for block in _LD_JSON.findall(page):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") in ("NewsArticle", "Article"):
                meta = item
    article = _ARTICLE.search(page)
    paragraphs = []
    for raw in _PARA.findall(article.group(0) if article else ""):
        text = re.sub(r"\s+", " ", html.unescape(_TAG.sub("", raw))).strip()
        if len(text) >= 25 and not _NOT_STORY.search(text) and text not in paragraphs:
            paragraphs.append(text)
    return {
        "title": str(meta.get("headline", "")),
        "published": str(meta.get("datePublished", "")),
        "text": "\n\n".join(paragraphs)[:MAX_CHARS],
    }


def fetch_article(url: str) -> dict:
    """The full article at ``url`` (cached). {"title", "published", "text", "error"}."""
    import httpx

    if not allowed(url):
        return {"title": "", "published": "", "text": "", "error": "Only https://www.kaleva.fi article links can be read."}
    SourceDocument = apps.get_model("feed", "SourceDocument")
    cached = SourceDocument.objects.filter(url=url).exclude(full_text="").order_by("-version").first()
    if cached:
        return {"title": cached.title, "published": "", "text": cached.full_text, "error": ""}
    resp, problem = None, ""
    for _ in range(2):  # one retry: Kaleva occasionally drops a connection
        try:
            resp = httpx.get(url, timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            break
        except Exception as exc:
            logger.info("Couldn't read %s: %s", url, exc)
            resp, problem = None, type(exc).__name__
    if resp is None:
        return {"title": "", "published": "", "text": "", "error": f"Couldn't download the article ({problem})."}
    article = extract(resp.text)
    if not article["text"]:
        return {**article, "error": "The page had no article text (maybe a paid article)."}
    SourceDocument.objects.filter(url=url).update(full_text=article["text"])
    if published := parse_datetime(article["published"] or ""):
        SourceDocument.objects.filter(url=url, published_at__isnull=True).update(published_at=published)
    return {**article, "error": ""}


def article_tool():
    """The LangChain tool the brief desk's model can call."""
    from langchain_core.tools import tool

    @tool
    def fetch_kaleva_article(url: str) -> str:
        """Download the full text of a Kaleva news article. Call it with the article's https://www.kaleva.fi URL
        before writing, because the RSS description is only a short teaser."""
        article = fetch_article(url)
        if article["error"]:
            return f"ERROR: {article['error']}"
        return f"TITLE: {article['title']}\nPUBLISHED: {article['published']}\n\n{article['text']}"

    return fetch_kaleva_article
