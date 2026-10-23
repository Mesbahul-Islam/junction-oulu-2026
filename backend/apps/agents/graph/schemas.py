"""Pydantic output schemas for ``structured_call``."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AssignmentProposal(BaseModel):
    reader_needs: list[str] = Field(
        description="1-3 of: information, understanding, usefulness, emotion, break, community"
    )
    risk_tier: str = Field(description="high | medium | low")
    rationale: str = Field(default="", description="One sentence why")


class DraftOut(BaseModel):
    headline: str = Field(description="Finnish headline, max ~90 characters, no sensationalism")
    summary: str = Field(description="Finnish summary, 2-3 sentences")
    key_facts: list[str] = Field(description="3-5 short Finnish facts copied faithfully from the source")


class ExplainerOut(BaseModel):
    newcomer: str = Field(description="What this means for someone who just moved to Finland (Finnish)")
    seasonal_worker: str = Field(description="What this means for a seasonal worker (Finnish)")
    student: str = Field(description="What this means for a student (Finnish)")
    resident: str = Field(description="What this means for a long-term resident (Finnish)")


class SituationTexts(BaseModel):
    """Fixed keys (no free-form dict) so the JSON schema is strict-mode friendly."""

    newcomer: str = ""
    seasonal_worker: str = ""
    student: str = ""
    resident: str = ""


class TranslationOut(BaseModel):
    headline: str
    summary: str
    key_facts: list[str]
    explainer: SituationTexts = Field(default_factory=SituationTexts)
    background: str = ""


class BackTranslationOut(BaseModel):
    back_translation: str = Field(description="The text translated back to Finnish")
    meaning_preserved: bool = Field(description="True if the meaning matches the Finnish original")
    similarity: float = Field(description="0-1 semantic similarity to the Finnish original")
    issues: list[str] = Field(default_factory=list, description="Concrete meaning differences, if any")


# --- Batched outputs: one LLM call covers every target language of a story ---


class LanguageTranslation(TranslationOut):
    language: str = Field(description="Language code this translation is in, e.g. en, sv, uk")


class TranslationsOut(BaseModel):
    translations: list[LanguageTranslation] = Field(description="Exactly one entry per requested language")


class LanguageBackTranslation(BackTranslationOut):
    language: str = Field(description="Language code of the translation that was back-translated")


class BackTranslationsOut(BaseModel):
    checks: list[LanguageBackTranslation] = Field(description="Exactly one entry per translation given")
