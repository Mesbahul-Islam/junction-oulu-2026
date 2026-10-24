"""Brand-sponsored prizes.

Each brand decides its own prizes. Four kinds:
  rank    the top 3 of a leaderboard (Finland or Oulu, gameweek or season)
  player  the brand names a player; if he counts for your team and reaches the points target, you win
  points  reach a points total in a gameweek
  tier    finish the season in a tier (e.g. Gold or better)
Weekly prizes are issued as vouchers with a code when the gameweek is final. Season prizes after the final.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import Gameweek, GameweekScore, Reward, Season, Voucher
from . import leaderboards

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
BRAND_DIR = Path(settings.MEDIA_ROOT) / "fantasy" / "brands"


def _code(reward: Reward, gameweek: Gameweek | None) -> str:
    prefix = reward.sponsor.slug.upper().replace("-", "")[:8]
    tag = f"GW{gameweek.number}" if gameweek else "S"
    while True:
        code = f"{prefix}-{tag}-{''.join(secrets.choice(CODE_ALPHABET) for _ in range(6))}"
        if not Voucher.objects.filter(code=code).exists():
            return code


def winners(reward: Reward, gameweek: Gameweek | None = None) -> list[dict]:
    """Leaderboard rows inside the reward's rank range (ties at the edge all win)."""
    period = "week" if reward.period == Reward.Period.WEEK else "season"
    board = leaderboards.leaderboard(
        reward.season, period, reward.scope, gameweek=gameweek,
        community=reward.community_slug or None, limit=reward.rank_to + 50,
    )
    return [r for r in board["rows"] if reward.rank_from <= r["rank"] <= reward.rank_to and r["points"] > 0]


def gameweek_winners(reward: Reward, gameweek: Gameweek) -> list[tuple[int, int]]:
    """[(squad_id, rank)] who won a weekly prize. rank is 0 for prizes that aren't about placing."""
    if reward.kind == Reward.Kind.RANK:
        return [(r["squad_id"], r["rank"]) for r in winners(reward, gameweek)]
    scores = GameweekScore.objects.filter(gameweek=gameweek, final=True, squad__season=reward.season)
    if reward.kind == Reward.Kind.POINTS and reward.threshold:
        return [(sid, 0) for sid in scores.filter(total__gte=reward.threshold).values_list("squad_id", flat=True)]
    if reward.kind == Reward.Kind.PLAYER and reward.player_id and reward.threshold:
        # The brand's player counted for your team (started, or came on as an auto-sub) and reached the target.
        return [(sc.squad_id, 0) for sc in scores.only("squad_id", "detail")
                if any(d["player"] == reward.player_id and d["points"] >= reward.threshold for d in sc.detail)]
    return []


def award_gameweek(gameweek: Gameweek) -> int:
    """Vouchers for every weekly prize of a finished gameweek. Safe to run again."""
    if gameweek.status != Gameweek.Status.FINISHED:
        return 0
    created = 0
    rewards = Reward.objects.filter(season=gameweek.season, period=Reward.Period.WEEK, active=True).select_related("sponsor")
    with transaction.atomic():
        for reward in rewards:
            for squad_id, rank in gameweek_winners(reward, gameweek):
                _, new = Voucher.objects.get_or_create(
                    reward=reward, squad_id=squad_id, gameweek=gameweek,
                    defaults={"rank": rank, "code": _code(reward, gameweek),
                              "expires_at": timezone.now() + timedelta(days=reward.voucher_days)},
                )
                created += new
    return created


def _trim(img):
    """Cut away empty margins (transparent or near-white) so logos fill their space."""
    from PIL import Image, ImageChops

    flat = Image.new("RGB", img.size, (255, 255, 255))
    flat.paste(img, mask=img.split()[3])
    box = ImageChops.difference(flat, Image.new("RGB", img.size, (255, 255, 255))).point(lambda v: 255 if v > 24 else 0).getbbox()
    return img.crop(box) if box else img


def brand_image(source: Path, slug: str, max_side: int = 480, force: bool = False) -> str:
    """A trimmed, web-sized WebP copy of a brand image under MEDIA_ROOT/fantasy/brands/. Returns its media path."""
    from PIL import Image

    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    out = BRAND_DIR / f"{slug}.webp"
    if force or not out.exists():
        img = _trim(Image.open(source).convert("RGBA"))
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        img.save(out, "WEBP", quality=85, method=6)
    return str(out.relative_to(settings.MEDIA_ROOT))


def current_rewards(season: Season) -> list[Reward]:
    return list(Reward.objects.filter(season=season, active=True).select_related("sponsor"))
