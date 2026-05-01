"""
influencers/views.py
B2B: управление профилем инфлюенсера, правилами и статистикой.
"""

from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Influencer, InfluencerRule
from core.serializers.influencer_serializers import (
    InfluencerSerializer,
    InfluencerPublicSerializer,
    InfluencerCreateUpdateSerializer,
    InfluencerRuleSerializer,
)
from core.models import Subscription


# ──────────────────────────────────────────────
#  PERMISSIONS
# ──────────────────────────────────────────────

class IsInfluencer(permissions.BasePermission):
    """Доступ только для пользователей с профилем инфлюенсера."""

    def has_permission(self, request, view):
        return hasattr(request.user, 'influencer_profile')

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


# ──────────────────────────────────────────────
#  ПУБЛИЧНЫЙ КАТАЛОГ
# ──────────────────────────────────────────────

class InfluencerListView(generics.ListAPIView):
    """
    GET /api/influencers/
    Каталог всех активных инфлюенсеров.
    Поддерживает фильтр по нише: ?niche=weight_loss
    """
    serializer_class   = InfluencerPublicSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['brand_name', 'bio', 'niche']

    def get_queryset(self):
        qs    = Influencer.objects.filter(is_active=True).prefetch_related('exercises')
        niche = self.request.query_params.get('niche')
        if niche:
            qs = qs.filter(niche=niche)
        return qs


class InfluencerDetailView(generics.RetrieveAPIView):
    """
    GET /api/influencers/<slug>/
    Публичная страница инфлюенсера.
    """
    serializer_class   = InfluencerPublicSerializer
    permission_classes = [permissions.AllowAny]
    queryset           = Influencer.objects.filter(is_active=True).prefetch_related('exercises', 'rules')
    lookup_field       = 'slug'


# ──────────────────────────────────────────────
#  ДАШБОРД ИНФЛЮЕНСЕРА (B2B)
# ──────────────────────────────────────────────

class InfluencerDashboardView(APIView):
    """
    GET  /api/influencers/dashboard/  — профиль + статистика
    POST /api/influencers/dashboard/  — создать профиль инфлюенсера
    PATCH /api/influencers/dashboard/ — обновить профиль
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'influencer_profile'):
            return Response(
                {"message": "У вас нет профиля инфлюенсера.", "has_profile": False},
                status=status.HTTP_404_NOT_FOUND,
            )
        influencer = request.user.influencer_profile
        active_subs = Subscription.objects.filter(
            influencer=influencer, status__in=['active', 'trialing']
        ).count()
        total_subs = Subscription.objects.filter(influencer=influencer).count()

        return Response({
            "profile":         InfluencerSerializer(influencer).data,
            "stats": {
                "active_subscribers": active_subs,
                "total_subscribers":  total_subs,
                "exercise_count":     influencer.exercises.filter(is_active=True).count(),
                "monthly_revenue_usd": float(influencer.monthly_revenue),
                "total_plans_generated": influencer.plans.count(),
            }
        })

    def post(self, request):
        if hasattr(request.user, 'influencer_profile'):
            return Response(
                {"error": "Профиль инфлюенсера уже существует."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = InfluencerCreateUpdateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        influencer = serializer.save()
        return Response(InfluencerSerializer(influencer).data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        if not hasattr(request.user, 'influencer_profile'):
            return Response({"error": "Профиль не найден."}, status=status.HTTP_404_NOT_FOUND)
        influencer = request.user.influencer_profile
        serializer = InfluencerCreateUpdateSerializer(
            influencer, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(InfluencerSerializer(influencer).data)


# ──────────────────────────────────────────────
#  ПРАВИЛА ГЕНЕРАЦИИ (InfluencerRule)
# ──────────────────────────────────────────────

class InfluencerRuleListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/influencers/rules/  — список правил инфлюенсера
    POST /api/influencers/rules/  — создать новое правило
    """
    serializer_class   = InfluencerRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsInfluencer]

    def get_queryset(self):
        return InfluencerRule.objects.filter(influencer=self.request.user.influencer_profile)

    def perform_create(self, serializer):
        serializer.save(influencer=self.request.user.influencer_profile)


class InfluencerRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/influencers/rules/<id>/
    """
    serializer_class   = InfluencerRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsInfluencer]

    def get_queryset(self):
        return InfluencerRule.objects.filter(influencer=self.request.user.influencer_profile)


# ──────────────────────────────────────────────
#  СТАТИСТИКА ПОДПИСЧИКОВ
# ──────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsInfluencer])
def influencer_subscribers(request):
    """
    GET /api/influencers/subscribers/
    Список активных подписчиков инфлюенсера.
    """
    influencer = request.user.influencer_profile
    subs = Subscription.objects.filter(
        influencer=influencer
    ).select_related('user', 'user__profile').order_by('-started_at')

    data = []
    for sub in subs:
        profile = getattr(sub.user, 'profile', None)
        data.append({
            "username":   sub.user.username,
            "status":     sub.status,
            "started_at": sub.started_at,
            "goal":       profile.goal if profile else None,
            "plan_count": sub.user.workout_plans.filter(influencer=influencer).count(),
        })

    return Response({
        "total":       subs.count(),
        "active":      subs.filter(status__in=['active', 'trialing']).count(),
        "subscribers": data,
    })