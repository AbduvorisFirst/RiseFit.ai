"""
core/email_utils.py
Все email-рассылки RiseFit.ai через Gmail SMTP или SendGrid.

Настройка Gmail в settings.py / .env:
    EMAIL_BACKEND      = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST         = 'smtp.gmail.com'
    EMAIL_PORT         = 587
    EMAIL_USE_TLS      = True
    EMAIL_HOST_USER    = 'your@gmail.com'       ← твой Gmail
    EMAIL_HOST_PASSWORD = 'xxxx xxxx xxxx xxxx' ← App Password (не обычный пароль!)
    DEFAULT_FROM_EMAIL = 'RiseFit <your@gmail.com>'

Как получить Gmail App Password:
    1. Google Account → Security → 2-Step Verification (включи)
    2. Security → App passwords → создай пароль для "Mail"
    3. Скопируй 16-символьный пароль → в .env EMAIL_HOST_PASSWORD
"""

import logging
from django.core.mail import send_mail, send_mass_mail
from django.conf import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  ХЕЛПЕР
# ──────────────────────────────────────────────

def _send(subject: str, body: str, to: str | list[str]) -> bool:
    """Базовый отправщик с логированием."""
    recipients = [to] if isinstance(to, str) else to
    try:
        send_mail(
            subject      = subject,
            message      = body,
            from_email   = settings.DEFAULT_FROM_EMAIL,
            recipient_list = recipients,
            fail_silently  = False,
        )
        logger.info(f"Email sent: '{subject}' → {recipients}")
        return True
    except Exception as e:
        logger.error(f"Email FAILED: '{subject}' → {recipients}: {e}")
        return False


# ──────────────────────────────────────────────
#  ПИСЬМА ПОЛЬЗОВАТЕЛЯМ
# ──────────────────────────────────────────────

def send_welcome_email(user) -> bool:
    """Приветственное письмо после регистрации."""
    name = user.first_name or user.username
    return _send(
        subject = "Welcome to RiseFit.ai 🏋️",
        body    = (
            f"Hi {name}!\n\n"
            f"Welcome to RiseFit.ai — your AI-powered personal trainer.\n\n"
            f"Here's how to get started:\n"
            f"  1. Complete your profile (goal, weight, height)\n"
            f"  2. Pick your favorite fitness influencer\n"
            f"  3. Get your personalized AI workout plan\n\n"
            f"Questions? Reply to this email — we're here to help.\n\n"
            f"Let's crush it,\n"
            f"The RiseFit Team"
        ),
        to = user.email,
    )


def send_subscription_confirmed(user, influencer) -> bool:
    """Подтверждение подписки после успешной оплаты."""
    name = user.first_name or user.username
    return _send(
        subject = f"You're subscribed to {influencer.brand_name}! 🎉",
        body    = (
            f"Hi {name}!\n\n"
            f"Your subscription to {influencer.brand_name} is now active.\n\n"
            f"What happens next:\n"
            f"  • Open the app to generate your personalized AI plan\n"
            f"  • Your plan is tailored to your goal: {user.profile.get_goal_display() if hasattr(user, 'profile') else 'your fitness goal'}\n"
            f"  • New workouts every week, adapted to your progress\n\n"
            f"You're billed $15/month. Cancel anytime from the app.\n\n"
            f"Time to train!\n"
            f"— RiseFit & {influencer.brand_name}"
        ),
        to = user.email,
    )


def send_subscription_cancelled(user, influencer) -> bool:
    """Уведомление об отмене подписки."""
    name = user.first_name or user.username
    return _send(
        subject = f"Your {influencer.brand_name} subscription has been cancelled",
        body    = (
            f"Hi {name},\n\n"
            f"We've cancelled your subscription to {influencer.brand_name}.\n\n"
            f"You'll keep access until the end of your current billing period.\n\n"
            f"Changed your mind? Re-subscribe anytime in the app.\n\n"
            f"— RiseFit Team"
        ),
        to = user.email,
    )


def send_payment_failed(user, influencer) -> bool:
    """Уведомление о неудачном платеже."""
    name = user.first_name or user.username
    return _send(
        subject = "Action required: payment failed for RiseFit",
        body    = (
            f"Hi {name},\n\n"
            f"We couldn't process your payment for {influencer.brand_name}.\n\n"
            f"To keep your access:\n"
            f"  1. Open the app\n"
            f"  2. Go to Settings → Subscription\n"
            f"  3. Update your payment method\n\n"
            f"Your access will remain active for a few more days while we retry.\n\n"
            f"Need help? Reply to this email.\n\n"
            f"— RiseFit Team"
        ),
        to = user.email,
    )


def send_plan_generated(user, plan) -> bool:
    """Уведомление о готовом AI-плане."""
    name = user.first_name or user.username
    return _send(
        subject = f"Your AI plan is ready: {plan.name} 💪",
        body    = (
            f"Hi {name}!\n\n"
            f"Your personalized workout plan is ready:\n\n"
            f"  Plan: {plan.name}\n"
            f"  Duration: {plan.duration_weeks} weeks\n"
            f"  Start: {plan.start_date}\n\n"
            f"Open the app to start your first workout!\n\n"
            f"— RiseFit AI"
        ),
        to = user.email,
    )


# ──────────────────────────────────────────────
#  ПИСЬМА ИНФЛЮЕНСЕРАМ
# ──────────────────────────────────────────────

def send_new_subscriber_notification(influencer, new_user) -> bool:
    """Инфлюенсер получает уведомление о новом подписчике."""
    if not influencer.user.email:
        return False
    return _send(
        subject = f"New subscriber on {influencer.brand_name}! 🎉",
        body    = (
            f"Hey {influencer.user.first_name or influencer.user.username}!\n\n"
            f"You have a new subscriber on RiseFit.ai!\n\n"
            f"Your total active subscribers: {influencer.subscribers_count}\n"
            f"Estimated monthly revenue: ${float(influencer.monthly_revenue):.2f}\n\n"
            f"Log in to your dashboard to see your analytics.\n\n"
            f"— RiseFit Team"
        ),
        to = influencer.user.email,
    )


# ──────────────────────────────────────────────
#  НАСТРОЙКА Gmail в .env
# ──────────────────────────────────────────────

GMAIL_ENV_EXAMPLE = """
# .env — добавь эти строки для Gmail SMTP

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=youremail@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
DEFAULT_FROM_EMAIL=RiseFit <youremail@gmail.com>

# Для разработки (без отправки, всё печатает в консоль):
# EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
"""