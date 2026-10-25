"""Listen: a story read aloud by ElevenLabs in the language its text is in.

Nothing is translated here: the voice reads the version the reader sees, which the translator desk
wrote and an editor approved, so what they hear matches the screen. Sámi is never voiced (no
ElevenLabs model speaks it, and its text comes from people); the reader app then uses the browser's voice.
"""

from __future__ import annotations

import hashlib

import httpx
from django.conf import settings

from apps.common.choices import SAMI_LANGUAGES

from .models import AudioClip

# Flash answers in ~1.5 s for a story; v3 (~14 s) is the only model that speaks Somali and Estonian.
# ponytail: v3 makes the first listen of so/et slow; pre-make clips on approval (Celery) if that matters.
MODEL = "eleven_flash_v2_5"
SLOW_MODEL_LANGUAGES = {"so": "eleven_v3", "et": "eleven_v3"}
URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_64"
TIMEOUT = 60


def supported(language: str) -> bool:
    return bool(settings.ELEVENLABS_API_KEY) and language not in SAMI_LANGUAGES


def script(version, situation: str | None = None) -> str:
    """Headline, summary, key facts and, when this version has it, "what this means for you"
    for the reader's situation. A fallback in another language is left out: one voice, one language."""
    parts = [version.headline, version.summary, *(version.key_facts or [])]
    if situation:
        parts.append((version.explainer or {}).get(situation) or "")
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def model_for(language: str) -> str:
    return SLOW_MODEL_LANGUAGES.get(language, MODEL)


def clip_key(text: str, language: str, voice: str) -> str:
    return hashlib.sha256(f"{model_for(language)}|{voice}|{language}|{text}".encode()).hexdigest()


def clip_for(version, situation: str | None = None) -> bytes:
    """The mp3 for this version, from the cache or made once by ElevenLabs. Raises httpx.HTTPError."""
    text, voice = script(version, situation), settings.ELEVENLABS_VOICE
    key = clip_key(text, version.language, voice)
    cached = AudioClip.objects.filter(key=key).values_list("data", flat=True).first()
    if cached is not None:
        return bytes(cached)
    resp = httpx.post(
        URL.format(voice=voice),
        headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
        json={"text": text, "model_id": model_for(version.language), "language_code": version.language},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    AudioClip.objects.get_or_create(key=key, defaults={"version": version, "data": resp.content})
    return resp.content
