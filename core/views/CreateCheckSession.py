"""
payments/views.py
Создание Stripe Checkout сессии для подписки.

Подключи в urls.py:
    path('api/payments/create-checkout/', CreateCheckoutSessionView.as_view(), name='create_checkout'),
    path('api/payments/stripe/webhook/',  stripe_webhook,                      name='stripe_webhook'),
"""

import stripe
import logging

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Influencer
from core.models import Subscription
from .stripe_webhook import stripe_webhook  # реэкспорт для urls.py

logger = logging.getLogger(__name__)


class CreateCheckoutSessionView(APIView):
    """
    POST /api/payments/create-checkout/

    Создаёт Stripe Checkout сессию и возвращает URL для редиректа.

    Тело запроса:
    {
        "influencer_slug": "fitbymike",
        "success_url": "https://yourapp.com/success",
        "cancel_url":  "https://yourapp.com/cancel"
    }

    Ответ:
    {
        "checkout_url": "https://checkout.stripe.com/pay/cs_..."
    }

    После успешной оплаты Stripe отправляет вебхук → stripe_webhook обрабатывает его
    и создаёт подписку в нашей БД.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY

        influencer_slug = request.data.get('influencer_slug')
        success_url     = request.data.get('success_url', 'https://yourapp.com/success')
        cancel_url      = request.data.get('cancel_url',  'https://yourapp.com/cancel')

        if not influencer_slug:
            return Response({"error": "Укажите influencer_slug."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            influencer = Influencer.objects.get(slug=influencer_slug, is_active=True)
        except Influencer.DoesNotExist:
            return Response({"error": "Инфлюенсер не найден."}, status=status.HTTP_404_NOT_FOUND)

        # Проверяем, нет ли уже активной подписки
        already_subscribed = Subscription.objects.filter(
            user=request.user, influencer=influencer, status__in=['active', 'trialing']
        ).exists()
        if already_subscribed:
            return Response({"error": "У вас уже есть активная подписка."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = stripe.checkout.Session.create(
                mode='subscription',
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency':     'usd',
                        'unit_amount':  int(settings.SUBSCRIPTION_PRICE_USD * 100),  # в центах
                        'recurring':    {'interval': 'month'},
                        'product_data': {
                            'name':        f"{influencer.brand_name} — AI Fitness Subscription",
                            'description': f"Персональные AI-тренировки по методике {influencer.brand_name}",
                        },
                    },
                    'quantity': 1,
                }],
                # Метаданные — вебхук использует их для создания подписки в нашей БД
                metadata={
                    'user_id':       str(request.user.id),
                    'influencer_id': str(influencer.id),
                },
                # Если у инфлюенсера есть Stripe Connect — платим на его аккаунт
                **(
                    {
                        'payment_intent_data': {
                            'application_fee_amount': int(settings.SUBSCRIPTION_PRICE_USD * 100 * 0.50),
                            'transfer_data': {'destination': influencer.stripe_account_id},
                        }
                    }
                    if influencer.stripe_account_id else {}
                ),
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe Checkout создание сессии: {e}")
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"checkout_url": session.url})