"""
core/permissions.py
Все кастомные Permission классы для RiseFit.ai
"""

from rest_framework import permissions
from core.models import Subscription


class IsInfluencer(permissions.BasePermission):
    """Только пользователи с профилем инфлюенсера."""
    message = "Доступ только для инфлюенсеров."

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                hasattr(request.user, 'influencer_profile')
        )


class IsInfluencerOwner(permissions.BasePermission):
    """Инфлюенсер может редактировать только своё."""
    message = "Вы можете редактировать только свои объекты."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        influencer = getattr(request.user, 'influencer_profile', None)
        if not influencer:
            return False
        # obj может быть Exercise, InfluencerRule, или Influencer
        if hasattr(obj, 'influencer'):
            return obj.influencer == influencer
        return obj == influencer


class IsSubscribed(permissions.BasePermission):
    """
    Пользователь имеет активную подписку на инфлюенсера.
    Используй в WorkoutPlan views.
    View должен передать influencer в kwargs или через query_param.
    """
    message = "Нужна активная подписка для доступа к этому контенту."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        influencer_slug = (
                view.kwargs.get('influencer_slug') or
                request.query_params.get('influencer_slug') or
                request.data.get('influencer_slug')
        )
        if not influencer_slug:
            return True  # проверку делает view сам
        return Subscription.objects.filter(
            user=request.user,
            influencer__slug=influencer_slug,
            status__in=['active', 'trialing'],
        ).exists()


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Владелец объекта — редактирует. Остальные — только читают."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class IsProfileOwner(permissions.BasePermission):
    """Доступ только к своему профилю."""
    message = "Вы можете редактировать только свой профиль."

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """Только админ пишет, все остальные — только читают."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff