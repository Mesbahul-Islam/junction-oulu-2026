"""Small player photos for the app.

Liiga's originals are ~450 KB PNGs shown in a 48 px circle, so each one is fetched once,
cropped to a square from the top (the face), shrunk to THUMB_SIZE px and stored as WebP
(~5 KB) under MEDIA_ROOT/fantasy/players/. The photo endpoint serves these with long cache
headers, and `sync_liiga` makes them ahead of time so even the first view is quick.
"""

from __future__ import annotations

import io
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

THUMB_SIZE = 96  # 2x the largest circle in the app, for sharp phone screens
PHOTO_DIR = Path(settings.MEDIA_ROOT) / "fantasy" / "players"


def thumbnail_path(player) -> Path:
    return PHOTO_DIR / f"{player.liiga_id}.webp"


FACE_CROP = 0.72  # head and shoulders: a square this share of the width, centred, from the top
# Photos are cached as immutable; bump this when the crop or size changes so apps fetch the new ones.
PHOTO_VERSION = 2


def ensure_thumbnail(player, http=None, force: bool = False) -> Path | None:
    """The player's thumbnail, made now if missing (or remade with force). None if there is no picture."""
    path = thumbnail_path(player)
    if path.exists() and not force:
        return path
    if not player.picture_url:
        return None
    import httpx
    from PIL import Image

    try:
        resp = (http or httpx).get(player.picture_url, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img = img.convert("RGBA")
        side = int(min(img.size) * FACE_CROP)
        left = (img.width - side) // 2
        img = img.crop((left, 0, left + side, side))
        img = img.resize((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        img.save(tmp, "WEBP", quality=80, method=6)
        tmp.replace(path)  # atomic: a half-written file is never served
        return path
    except Exception as exc:
        logger.info("No thumbnail for player %s: %s", player.liiga_id, exc)
        return None


def generate_thumbnails(players, workers: int = 8, force: bool = False) -> int:
    """Make missing thumbnails (all of them with force) in parallel. Returns how many exist afterwards."""
    import httpx

    todo = [p for p in players if p.picture_url and (force or not thumbnail_path(p).exists())]
    with httpx.Client() as http, ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda p: ensure_thumbnail(p, http, force), todo))
    return sum(1 for p in players if thumbnail_path(p).exists())
