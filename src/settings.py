"""
risefit/settings.py
Production-ready настройки для RiseFit.ai
Используй .env файл для секретов (python-decouple или django-environ)
"""

import environ
from pathlib import Path
import os

# Инициализируем environ
env = environ.Env(
    # Укажи значения по умолчанию (необязательно)
    DEBUG=(bool, False)
)

# Указываем путь к твоему .env файлу
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))



BASE_DIR = Path(__file__).resolve().parent.parent

# ─── БЕЗОПАСНОСТЬ ─────────────────────────────
# В продакшене: SECRET_KEY из переменной окружения!
SECRET_KEY = os.environ.get('SECRET_KEY', '')
DEBUG      = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# ─── ПРИЛОЖЕНИЯ ───────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Сторонние
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    # Наши приложения
    'core',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',          # CORS — первым!
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'src.urls'
WSGI_APPLICATION = 'src.wsgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS':    [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

# ─── БАЗА ДАННЫХ ──────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# DATABASES = {
#     'default': {
#         'ENGINE':   'django.db.backends.postgresql',
#         'NAME':     os.environ.get('DB_NAME',     'risefit_db'),
#         'USER':     os.environ.get('DB_USER',     'postgres'),
#         'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
#         'HOST':     os.environ.get('DB_HOST',     'localhost'),
#         'PORT':     os.environ.get('DB_PORT',     '5432'),
#     }
# }

# ─── DJANGO REST FRAMEWORK ────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS':  'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ─── JWT НАСТРОЙКИ ────────────────────────────
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ─── CORS (для Flutter / веб-клиента) ─────────
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    # Добавь свой домен в продакшене
]
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Только в режиме разработки!





GEMINI_API_KEY        = env('GEMINI_API_KEY')      # Google AI Studio
STRIPE_SECRET_KEY     = env('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')
SUBSCRIPTION_PRICE_USD = 15.00

# ─── МЕДИАФАЙЛЫ ───────────────────────────────
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ─── ПРОЧЕЕ ───────────────────────────────────
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE     = 'UTC'
USE_I18N      = True
USE_TZ        = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
