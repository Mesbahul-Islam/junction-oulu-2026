from django.db import models


class Language(models.TextChoices):
    FINNISH = "fi", "Suomi"
    SWEDISH = "sv", "Svenska"
    ENGLISH = "en", "English"
    NORTHERN_SAMI = "se", "Davvisámegiella"
    INARI_SAMI = "smn", "Anarâškielâ"
    SKOLT_SAMI = "sms", "Sääʹmǩiõll"
    RUSSIAN = "ru", "Русский"
    UKRAINIAN = "uk", "Українська"
    ARABIC = "ar", "العربية"
    SOMALI = "so", "Soomaali"
    ESTONIAN = "et", "Eesti"


# FR-3.9: no machine-translated text is ever published in these languages.
SAMI_LANGUAGES = {Language.NORTHERN_SAMI, Language.INARI_SAMI, Language.SKOLT_SAMI}
SOURCE_LANGUAGE = Language.FINNISH


class RiskTier(models.TextChoices):
    HIGH = "high", "High"  # residence permits, health, employment, legal, safety
    MEDIUM = "medium", "Medium"  # transport, services, events
    LOW = "low", "Low"  # opening hours, weather


class ReaderNeed(models.TextChoices):
    """Kaleva Media user needs model."""

    INFORMATION = "information", "Information"
    UNDERSTANDING = "understanding", "Understanding"
    USEFULNESS = "usefulness", "Usefulness"
    EMOTION = "emotion", "Emotion"
    BREAK = "break", "Break"
    COMMUNITY = "community", "Community"


class ReviewStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_REVIEW = "pending_review", "Pending review"
    CHANGES_REQUESTED = "changes_requested", "Changes requested"
    APPROVED = "approved", "Approved"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"
    EXPIRED = "expired", "Expired"
    REOPENED = "reopened", "Reopened"


class ReaderSituation(models.TextChoices):
    NEWCOMER = "newcomer", "Newcomer"
    SEASONAL_WORKER = "seasonal_worker", "Seasonal worker"
    STUDENT = "student", "Student"
    RESIDENT = "resident", "Resident"
