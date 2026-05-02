"""
payments/stripe_webhook.py
Stripe вебхук — обработка событий подписок.

Подключи в urls.py:
    path('api/payments/stripe/webhook/', stripe_webhook, name='stripe_webhook'),

Установи:
    pip install stripe

В settings.py добавь:
    STRIPE_SECRET_KEY     = env('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')  # из Stripe Dashboard → Webhooks

В Stripe Dashboard настрой вебхук на:
    https://yourdomain.com/api/payments/stripe/webhook/

Подпишись на события:
    - checkout.session.completed
    - invoice.payment_succeeded
    - invoice.payment_failed
    - customer.subscription.deleted
    - customer.subscription.updated
"""

import logging
import stripe

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import Subscription
from core.models import Influencer

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ──────────────────────────────────────────────

def _get_or_none(model, **kwargs):
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        return None


def _activate_subscription(stripe_sub_id: str, stripe_customer_id: str,
                           user: User, influencer: Influencer,
                           period_end_ts: int):
    """Создаёт или активирует подписку в нашей БД."""
    expires_at = timezone.datetime.fromtimestamp(period_end_ts, tz=timezone.utc)

    sub, created = Subscription.objects.get_or_create(
        stripe_subscription_id=stripe_sub_id,
        defaults={
            'user':       user,
            'influencer': influencer,
            'status':     'active',
            'price_usd':  settings.SUBSCRIPTION_PRICE_USD,
            'stripe_customer_id': stripe_customer_id,
            'expires_at': expires_at,
        }
    )

    if not created:
        sub.status     = 'active'
        sub.expires_at = expires_at
        sub.stripe_customer_id = stripe_customer_id
        sub.save(update_fields=['status', 'expires_at', 'stripe_customer_id'])

    # Обновляем счётчик подписчиков у инфлюенсера
    influencer.subscribers_count = Subscription.objects.filter(
        influencer=influencer, status='active'
    ).count()
    influencer.save(update_fields=['subscribers_count'])

    action = 'создана' if created else 'активирована'
    logger.info(f"Подписка {stripe_sub_id} {action} для {user.username} → {influencer.brand_name}")
    return sub


def _cancel_subscription(stripe_sub_id: str):
    """Отменяет подписку и обновляет счётчик инфлюенсера."""
    sub = _get_or_none(Subscription, stripe_subscription_id=stripe_sub_id)
    if not sub:
        logger.warning(f"Подписка {stripe_sub_id} не найдена в БД при отмене")
        return

    sub.status       = 'cancelled'
    sub.cancelled_at = timezone.now()
    sub.save(update_fields=['status', 'cancelled_at'])

    influencer = sub.influencer
    influencer.subscribers_count = Subscription.objects.filter(
        influencer=influencer, status='active'
    ).count()
    influencer.save(update_fields=['subscribers_count'])

    logger.info(f"Подписка {stripe_sub_id} отменена для {sub.user.username}")


def _mark_past_due(stripe_sub_id: str):
    """Помечает подписку как просроченную (платёж не прошёл)."""
    sub = _get_or_none(Subscription, stripe_subscription_id=stripe_sub_id)
    if sub:
        sub.status = 'past_due'
        sub.save(update_fields=['status'])
        logger.warning(f"Платёж не прошёл, подписка {stripe_sub_id} → past_due")


# ──────────────────────────────────────────────
#  ОБРАБОТЧИКИ СОБЫТИЙ
# ──────────────────────────────────────────────

def handle_checkout_completed(session: dict):
    """
    checkout.session.completed
    Срабатывает когда пользователь успешно прошёл checkout.
    Метаданные должны содержать user_id и influencer_id.
    """
    metadata         = session.get('metadata', {})
    user_id          = metadata.get('user_id')
    influencer_id    = metadata.get('influencer_id')
    stripe_sub_id    = session.get('subscription')
    customer_id      = session.get('customer')

    if not all([user_id, influencer_id, stripe_sub_id]):
        logger.error(
            f"checkout.session.completed: неполные метаданные. "
            f"user_id={user_id}, influencer_id={influencer_id}, sub={stripe_sub_id}"
        )
        return

    user       = _get_or_none(User, id=user_id)
    influencer = _get_or_none(Influencer, id=influencer_id)

    if not user or not influencer:
        logger.error(f"Пользователь {user_id} или инфлюенсер {influencer_id} не найден")
        return

    # Получаем период подписки из Stripe
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe_sub     = stripe.Subscription.retrieve(stripe_sub_id)
        period_end     = stripe_sub['current_period_end']
    except stripe.error.StripeError as e:
        logger.error(f"Ошибка получения подписки из Stripe: {e}")
        period_end = int((timezone.now() + timezone.timedelta(days=30)).timestamp())

    _activate_subscription(stripe_sub_id, customer_id, user, influencer, period_end)


def handle_invoice_payment_succeeded(invoice: dict):
    """
    invoice.payment_succeeded
    Срабатывает при каждом успешном платеже (первый и продление).
    """
    stripe_sub_id = invoice.get('subscription')
    customer_id   = invoice.get('customer')

    if not stripe_sub_id:
        return  # Не подписочный счёт

    # Находим подписку в нашей БД
    sub = _get_or_none(Subscription, stripe_subscription_id=stripe_sub_id)
    if not sub:
        logger.warning(f"invoice.payment_succeeded: подписка {stripe_sub_id} не в БД")
        return

    # Обновляем период
    period_end = invoice.get('lines', {}).get('data', [{}])[0].get('period', {}).get('end')
    if period_end:
        sub.expires_at = timezone.datetime.fromtimestamp(period_end, tz=timezone.utc)

    sub.status = 'active'
    sub.save(update_fields=['status', 'expires_at'])

    logger.info(
        f"Платёж прошёл: {sub.user.username} → {sub.influencer.brand_name}, "
        f"сумма: ${invoice.get('amount_paid', 0) / 100:.2f}"
    )


def handle_invoice_payment_failed(invoice: dict):
    """
    invoice.payment_failed
    Платёж не прошёл — помечаем подписку как просроченную.
    Stripe сам попробует повторить платёж по своей логике.
    """
    stripe_sub_id = invoice.get('subscription')
    if stripe_sub_id:
        _mark_past_due(stripe_sub_id)


def handle_subscription_deleted(subscription: dict):
    """
    customer.subscription.deleted
    Подписка окончательно отменена (пользователь отменил или Stripe после нескольких неудач).
    """
    stripe_sub_id = subscription.get('id')
    if stripe_sub_id:
        _cancel_subscription(stripe_sub_id)


def handle_subscription_updated(subscription: dict):
    """
    customer.subscription.updated
    Изменился статус подписки в Stripe (например, возобновлена после past_due).
    """
    stripe_sub_id  = subscription.get('id')
    stripe_status  = subscription.get('status')  # active, past_due, canceled, trialing ...
    period_end     = subscription.get('current_period_end')

    sub = _get_or_none(Subscription, stripe_subscription_id=stripe_sub_id)
    if not sub:
        return

    # Маппинг статусов Stripe → наши статусы
    status_map = {
        'active':   'active',
        'trialing': 'trialing',
        'past_due': 'past_due',
        'canceled': 'cancelled',
        'unpaid':   'past_due',
        'paused':   'cancelled',
    }
    our_status = status_map.get(stripe_status, sub.status)

    update_fields = ['status']
    sub.status = our_status

    if period_end:
        sub.expires_at = timezone.datetime.fromtimestamp(period_end, tz=timezone.utc)
        update_fields.append('expires_at')

    sub.save(update_fields=update_fields)

    # Обновляем счётчик
    influencer = sub.influencer
    influencer.subscribers_count = Subscription.objects.filter(
        influencer=influencer, status='active'
    ).count()
    influencer.save(update_fields=['subscribers_count'])

    logger.info(f"Подписка {stripe_sub_id} обновлена → {our_status}")


# ──────────────────────────────────────────────
#  ГЛАВНЫЙ ВЕБХУК VIEW
# ──────────────────────────────────────────────

# Роутер событий
EVENT_HANDLERS = {
    'checkout.session.completed':    handle_checkout_completed,
    'invoice.payment_succeeded':     handle_invoice_payment_succeeded,
    'invoice.payment_failed':        handle_invoice_payment_failed,
    'customer.subscription.deleted': handle_subscription_deleted,
    'customer.subscription.updated': handle_subscription_updated,
}


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    POST /api/payments/stripe/webhook/

    Принимает вебхуки от Stripe, верифицирует подпись
    и вызывает нужный обработчик.
    """
    payload    = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
    stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

    # ── Верификация подписи ──────────────────
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        logger.error("Stripe webhook: невалидный payload")
        return HttpResponse("Invalid payload", status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Stripe webhook: неверная подпись")
        return HttpResponse("Invalid signature", status=400)

    event_type = event['type']
    logger.info(f"Stripe webhook получен: {event_type} (id={event['id']})")

    # ── Вызов обработчика ───────────────────
    handler = EVENT_HANDLERS.get(event_type)
    if handler:
        try:
            handler(event['data']['object'])
        except Exception as e:
            logger.exception(f"Ошибка обработки события {event_type}: {e}")
            # Возвращаем 200 чтобы Stripe не повторял событие бесконечно.
            # Ошибки нужно мониторить в логах/Sentry.
    else:
        logger.debug(f"Stripe webhook: событие '{event_type}' не обрабатывается")

    return HttpResponse("OK", status=200)