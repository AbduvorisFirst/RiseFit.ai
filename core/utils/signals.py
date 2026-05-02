"""
core/signals.py
Django сигналы — автоматические действия при событиях в БД.

1. После создания User → отправляем welcome email
2. После изменения UserProfile → пересчитываем КБЖУ
3. После активации Subscription → обновляем счётчик инфлюенсера
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  USER → Welcome email
# ──────────────────────────────────────────────

@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """Отправляет welcome email при регистрации."""
    if not created:
        return
    if not instance.email:
        return

    try:
        send_mail(
            subject='Welcome to RiseFit.ai 🏋️',
            message=(
                f"Hi {instance.first_name or instance.username}!\n\n"
                f"Welcome to RiseFit.ai — your AI-powered personal trainer.\n\n"
                f"Next steps:\n"
                f"1. Complete your profile (height, weight, goal)\n"
                f"2. Choose your favorite fitness influencer\n"
                f"3. Get your personalized AI workout plan\n\n"
                f"Let's get started!\n\n"
                f"— The RiseFit Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.email],
            fail_silently=True,  # не ломаем регистрацию если email упал
        )
        logger.info(f"Welcome email sent to {instance.email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {instance.email}: {e}")


# ──────────────────────────────────────────────
#  SUBSCRIPTION → счётчик инфлюенсера
# ──────────────────────────────────────────────

@receiver(post_save, sender='core.Subscription')
def update_influencer_subscriber_count(sender, instance, **kwargs):
    """Обновляет subscribers_count у инфлюенсера при изменении подписки."""
    try:
        influencer = instance.influencer
        active_count = influencer.subscriptions.filter(
            status__in=['active', 'trialing']
        ).count()
        influencer.subscribers_count = active_count
        influencer.save(update_fields=['subscribers_count'])
    except Exception as e:
        logger.error(f"Failed to update subscriber count: {e}")


@receiver(post_delete, sender='core.Subscription')
def update_influencer_count_on_delete(sender, instance, **kwargs):
    """Обновляет счётчик при удалении подписки."""
    try:
        influencer = instance.influencer
        active_count = influencer.subscriptions.filter(
            status__in=['active', 'trialing']
        ).count()
        influencer.subscribers_count = active_count
        influencer.save(update_fields=['subscribers_count'])
    except Exception as e:
        logger.error(f"Failed to update subscriber count on delete: {e}")