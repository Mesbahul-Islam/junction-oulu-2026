"""Tagging agent - newsroom role: **metadata / archive desk** (FR-3.2, FR-2.x personalisation).

Human counterpart (FR-3.6): the editor reviewing the snippet (tags are
editable during review).
Produces topic tags (keyword taxonomy -> interest slugs), an
embedding for the recommender, and the geo bounding box (from the community).

The embedding is an LLM-free feature-hashing stub
(``text.hashing_embedding``). TODO: swap for a real multilingual embedding
model when the feed ranking needs semantic similarity.
"""

from __future__ import annotations

from typing import Any

from ..state import NewsroomState
from ..text import hashing_embedding, topic_tags

EMBEDDING_DIM = 64


def tagging(state: NewsroomState) -> dict[str, Any]:
    raw = {r["key"]: r for r in state.get("raw_items") or []}
    community = state.get("community") or {}
    bbox = community.get("bbox") or None
    tags_out: dict[str, dict] = {}

    for key, draft in (state.get("drafts") or {}).items():
        item = raw.get(key, {})
        text = " ".join([
            item.get("title", ""), item.get("body", ""), draft.get("headline", ""), draft.get("summary", ""),
            " ".join(draft.get("key_facts", [])),
        ])
        tags = topic_tags(text)
        if item.get("kind") == "community_signal":
            tags.append("community_signal")
        # Snippet.tags are interest slugs; risk tier / reader needs have their own fields.
        tags_out[key] = {
            "tags": list(dict.fromkeys(tags)),
            "embedding": hashing_embedding(text, EMBEDDING_DIM),
            "geo_bbox": list(bbox) if bbox else None,
        }
    return {"tags": tags_out}
