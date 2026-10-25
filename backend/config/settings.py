from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me-to-a-long-random-string")
DEBUG = env("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # third party
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "django_celery_beat",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # local
    "apps.common",
    "apps.accounts",
    "apps.communities",
    "apps.feed",
    "apps.agents",
    "apps.editorial",
    "apps.notes",
    "apps.markets",
    "apps.fantasy",
    "apps.trust",
    "apps.rewards",
    "apps.telegrambot",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # allauth layout override
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.common.context_processors.frontend_url",
            ],
        },
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

SITE_ID = 1
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "none"
LOGIN_REDIRECT_URL = "/accounts/oauth/callback/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID", default=""),
            "secret": env("GOOGLE_CLIENT_SECRET", default=""),
        },
        "SCOPE": ["profile", "email"],
    }
}

LANGUAGE_CODE = "en"
TIME_ZONE = "Europe/Helsinki"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "frontend" / "static"]
# Uploaded files (snippet thumbnails, post images) are stored on local disk in
# backend/media/ and served by Django at /media/ (see config/urls.py).
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.CreatedAtCursorPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Junction Oulu 2026 API",
    "VERSION": "0.1.0",
}

# The React app (frontend/, Vite dev server on :5173) calls the API from another origin.
# Auth is a JWT in the Authorization header (no cookies), so no CORS credentials are needed.
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS", default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]
)
# In development also allow any origin, e.g. the app opened from a phone on the LAN (http://192.168.x.x:5173).
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=DEBUG)

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TIMEZONE = TIME_ZONE

# --- AI newsroom model: set these three in .env (see docs/GUIDE.md §5) ---
# LLM_PROVIDER: groq, gemini (google_genai), openai, anthropic, mistral, ollama, openrouter ...
# Leave LLM_MODEL empty (or "stub") to run the offline stub without any AI provider.
LLM_PROVIDER = env("LLM_PROVIDER", default="")
LLM_MODEL = env("LLM_MODEL", default="")
LLM_API_KEY = env("LLM_API_KEY", default="")
# Optional: any OpenAI-compatible server (vLLM, LM Studio, LiteLLM) with LLM_PROVIDER=openai.
LLM_BASE_URL = env("LLM_BASE_URL", default="")
# "auto" picks per provider (function_calling for Groq, json_schema otherwise).
LLM_STRUCTURED_OUTPUT = env("LLM_STRUCTURED_OUTPUT", default="auto")
# Languages per translation / back-translation call. 1 (default) is reliable even for small
# local models; 0 = every language in one call (fewer calls, only for large models).
LLM_LANGUAGES_PER_CALL = env.int("LLM_LANGUAGES_PER_CALL", default=1)

# Advanced, optional: a different model for one agent, as provider:model
# (e.g. LLM_MODEL_TRANSLATOR=anthropic:claude-haiku-5-5). Its key is read from that
# provider's own variable below (ANTHROPIC_API_KEY ...) unless it's the main provider.
LLM_AGENTS = ("explainer", "translator", "sports")  # LLM_MODEL_EXPLAINER etc. pick a model per desk
LLM_AGENT_MODELS = {agent: env(f"LLM_MODEL_{agent.upper()}", default="") for agent in LLM_AGENTS}
LLM_PROVIDER_KEY_VARS = {
    "google_genai": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "groq": ("GROQ_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "mistralai": ("MISTRAL_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "xai": ("XAI_API_KEY",),
    "together": ("TOGETHER_API_KEY",),
    "fireworks": ("FIREWORKS_API_KEY",),
}
LLM_API_KEYS = {
    provider: next((env(var, default="") for var in names if env(var, default="")), "")
    for provider, names in LLM_PROVIDER_KEY_VARS.items()
}
# How often the newsroom runs on its own (minutes); each run costs about AGENT_MAX_ITEMS x 5 calls.
AGENT_SCHEDULE_MINUTES = env.int("AGENT_SCHEDULE_MINUTES", default=30)
# Stories turned into snippets per run (each story costs ~5 LLM calls).
AGENT_MAX_ITEMS = env.int("AGENT_MAX_ITEMS", default=4)
AGENT_CONFIDENCE_THRESHOLD = env.float("AGENT_CONFIDENCE_THRESHOLD", default=0.7)

# Feed personalisation with Jev (TypeSafe AI). Without a key the heuristic ranker is used.
TYPESAFE_API_KEY = env("TYPESAFE_API_KEY", default="")
FEED_RANKER = env("FEED_RANKER", default="jev")  # "jev" or "heuristic"
JEV_MODEL = env("JEV_MODEL", default="jev-latest")
JEV_TOP_K = env.int("JEV_TOP_K", default=30)  # shortlist size Jev re-ranks per request
JEV_WEIGHT = env.float("JEV_WEIGHT", default=0.6)  # share of Jev in the blended score
JEV_TIMEOUT = env.float("JEV_TIMEOUT", default=2.0)  # seconds per call
JEV_CONCURRENCY = env.int("JEV_CONCURRENCY", default=16)
JEV_CACHE_SECONDS = env.int("JEV_CACHE_SECONDS", default=6 * 3600)

# Telegram news bot (@BotFather token). Empty: the bot is idle and sends nothing.
TELEGRAM_BOT_TOKEN = env("TELEGRAM_API", default="")

# Prediction markets: virtual points only (FR-5.2)
MARKETS_SIGNUP_GRANT = env.int("MARKETS_SIGNUP_GRANT", default=1000)

# Fantasy Liiga: Liiga stats API (https://prod.liiga-backend.liiga.fi/stats/swagger-ui)
LIIGA_API_BASE = env("LIIGA_API_BASE", default="https://prod.liiga-backend.liiga.fi/stats/api/v1")
LIIGA_API_KEY = env("LIIGAFI_API_KEY", default="")
# Lämäri AI wording (agent "sports", model via LLM_MODEL_SPORTS): at most this many model calls per minute,
# shared by all workers, so free tiers (e.g. Gemini's ~5 requests a minute) are never exceeded.
SPORTS_AI_PER_MINUTE = env.int("SPORTS_AI_PER_MINUTE", default=4)
