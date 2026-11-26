"""Réglages Django du projet Passage (SchoolLogs - module badges)."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# Les secrets viennent de l'environnement (fichier .env local, jamais commité).
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
        'accounts',
    'school',
    'passages'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Base de données : SQLite par défaut, PostgreSQL possible via DATABASE_URL.
DATABASES = {
    'default': env.db_url('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
}

# --- Sécurité des mots de passe ---
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    
]
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Sessions : durée de vie limitée, cookies durcis ---
SESSION_COOKIE_AGE = 3600          # 1 heure
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# --- Internationalisation ---
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# --- Connexion ---
LOGIN_URL = "connexion"
LOGIN_MAX_ATTEMPTS = env.int("LOGIN_MAX_ATTEMPTS", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=900)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}

# --- Badges à code tournant ---
BADGE_PAS_SECONDES = env.int("BADGE_PAS_SECONDES", default=30)
BADGE_TOLERANCE_SECONDES = env.int("BADGE_TOLERANCE_SECONDES", default=60)

# --- Synchronisation des scans ---
HORLOGE_ECART_MAX_S = env.int("HORLOGE_ECART_MAX_S", default=86400)  # 24 h

# --- Détection d'absence ---
# Délai après la fin d'une fenêtre avant de déclarer une absence (laisse le temps aux
# scans faits hors ligne d'arriver). Mettre 0 pour une démonstration.
ABSENCE_DELAI_GRACE_S = env.int("ABSENCE_DELAI_GRACE_S", default=600)
# --- Messages aux parents ---
MESSAGES_MAX_PAR_ELEVE_PAR_JOUR = env.int("MESSAGES_MAX_PAR_ELEVE_PAR_JOUR", default=3)
SMS_FOURNISSEUR = env("SMS_FOURNISSEUR", default="passages.notifications.FournisseurConsole")

# --- IA dans le produit ---
def _nombre(nom, defaut):
    brut = env.str(nom, default="").strip()
    return float(brut) if brut else defaut


ANTHROPIC_API_KEY = env.str("ANTHROPIC_API_KEY", default="").strip()
AI_MODEL = env.str("AI_MODEL", default="claude-haiku-5-5")
AI_TIMEOUT_S = _nombre("AI_TIMEOUT_S", 20.0)
AI_PLAFOND_JOUR_FCFA = _nombre("AI_DAILY_BUDGET_FCFA", 500.0)
# Tarifs en FCFA par million de tokens : des ordres de grandeur à régler selon le tarif réel.
AI_PRIX_ENTREE_FCFA_MTOK = _nombre("AI_PRIX_ENTREE_FCFA_MTOK", 600.0)
AI_PRIX_SORTIE_FCFA_MTOK = _nombre("AI_PRIX_SORTIE_FCFA_MTOK", 3000.0)
AI_MAX_TOKENS_SORTIE = 300