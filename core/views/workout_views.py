"""
workouts/views.py
Тренировки: упражнения, планы, выполнение тренировок.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Influencer
from core.views.influencer_views import IsInfluencer
from core.models import Subscription

from core.models import Exercise, WorkoutPlan, WorkoutDay, WorkoutSet
from core.serializers.workout_serializers import (
    ExerciseSerializer,
    WorkoutPlanSerializer,
    WorkoutPlanDetailSerializer,
    WorkoutDaySerializer,
    WorkoutSetSerializer,
)
from core.ai_generator import generate_workout_plan


# ──────────────────────────────────────────────
#  УПРАЖНЕНИЯ
# ──────────────────────────────────────────────

class ExerciseListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/workouts/exercises/           — список упражнений (публично)
    POST /api/workouts/exercises/           — добавить упражнение (только инфлюенсер)

    Фильтры: ?influencer=<slug>  ?category=chest  ?difficulty=beginner
    """
    serializer_class = ExerciseSerializer
    filter_backends  = [filters.SearchFilter]
    search_fields    = ['name', 'description', 'primary_muscles']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), IsInfluencer()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Exercise.objects.filter(is_active=True).select_related('influencer')

        influencer_slug = self.request.query_params.get('influencer')
        if influencer_slug:
            qs = qs.filter(influencer__slug=influencer_slug)

        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)

        difficulty = self.request.query_params.get('difficulty')
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        equipment = self.request.query_params.get('equipment')
        if equipment:
            qs = qs.filter(equipment_required=equipment)

        return qs


class ExerciseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/workouts/exercises/<id>/   — детали упражнения
    PATCH  /api/workouts/exercises/<id>/   — редактировать (только владелец-инфлюенсер)
    DELETE /api/workouts/exercises/<id>/   — удалить
    """
    serializer_class = ExerciseSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsInfluencer()]

    def get_queryset(self):
        if self.request.method == 'GET':
            return Exercise.objects.filter(is_active=True)
        return Exercise.objects.filter(influencer=self.request.user.influencer_profile)

    def perform_destroy(self, instance):
        # Мягкое удаление
        instance.is_active = False
        instance.save()


# ──────────────────────────────────────────────
#  WORKOUT PLANS
# ──────────────────────────────────────────────

class WorkoutPlanListView(generics.ListAPIView):
    """
    GET /api/workouts/plans/
    Все планы текущего пользователя.
    """
    serializer_class   = WorkoutPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WorkoutPlan.objects.filter(
            user=self.request.user
        ).select_related('influencer').prefetch_related('workout_days').order_by('-created_at')


class WorkoutPlanDetailView(generics.RetrieveAPIView):
    """
    GET /api/workouts/plans/<uuid>/
    Полный план с днями и упражнениями.
    """
    serializer_class   = WorkoutPlanDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WorkoutPlan.objects.filter(
            user=self.request.user
        ).prefetch_related('workout_days__sets__exercise')


class GeneratePlanView(APIView):
    """
    POST /api/workouts/plans/generate/
    Генерирует AI-программу для пользователя.

    Тело запроса:
    {
        "influencer_slug": "fitbymike",
        "duration_weeks": 8   (опционально, default=8)
    }

    Требует: активного профиля пользователя + подписки на инфлюенсера.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Проверяем профиль
        if not hasattr(request.user, 'profile'):
            return Response(
                {"error": "Сначала заполните профиль (онбординг)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        influencer_slug = request.data.get('influencer_slug')
        if not influencer_slug:
            return Response({"error": "Укажите influencer_slug."}, status=status.HTTP_400_BAD_REQUEST)

        influencer = get_object_or_404(Influencer, slug=influencer_slug, is_active=True)

        # Проверяем подписку
        has_sub = Subscription.objects.filter(
            user=request.user, influencer=influencer, status__in=['active', 'trialing']
        ).exists()
        if not has_sub:
            return Response(
                {"error": "Нет активной подписки на этого инфлюенсера."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Архивируем текущий активный план (если есть)
        WorkoutPlan.objects.filter(
            user=request.user, influencer=influencer, status='active'
        ).update(status='archived')

        # Генерируем новый план
        duration_weeks = int(request.data.get('duration_weeks', 8))
        duration_weeks = max(4, min(16, duration_weeks))  # от 4 до 16 недель

        try:
            plan = generate_workout_plan(request.user, influencer, duration_weeks)
        except Exception as e:
            return Response(
                {"error": f"Ошибка генерации плана: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            WorkoutPlanDetailSerializer(plan).data,
            status=status.HTTP_201_CREATED,
        )


class ActivePlanView(APIView):
    """
    GET /api/workouts/plans/active/
    Текущий активный план пользователя.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        plan = WorkoutPlan.objects.filter(
            user=request.user, status='active'
        ).prefetch_related('workout_days__sets__exercise').first()

        if not plan:
            return Response(
                {"message": "Нет активной программы. Сгенерируйте план.", "has_plan": False},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "has_plan": True,
            "plan":     WorkoutPlanDetailSerializer(plan).data,
        })


# ──────────────────────────────────────────────
#  ВЫПОЛНЕНИЕ ТРЕНИРОВОК
# ──────────────────────────────────────────────

class WorkoutDayDetailView(generics.RetrieveAPIView):
    """
    GET /api/workouts/days/<id>/
    Конкретный день тренировки с упражнениями.
    """
    serializer_class   = WorkoutDaySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WorkoutDay.objects.filter(
            plan__user=self.request.user
        ).prefetch_related('sets__exercise')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def complete_workout_day(request, day_id):
    """
    POST /api/workouts/days/<id>/complete/
    Отмечает день тренировки как выполненный.

    Тело (опционально):
    {
        "notes": "Хорошая тренировка, увеличил вес на жиме",
        "sets": [
            {"set_id": 1, "actual_sets": 3, "actual_reps": 12, "actual_weight_kg": 20.0}
        ]
    }
    """
    day = get_object_or_404(WorkoutDay, id=day_id, plan__user=request.user)

    if day.is_completed:
        return Response({"error": "День уже отмечен как выполненный."}, status=status.HTTP_400_BAD_REQUEST)

    # Обновляем факт выполнения упражнений
    sets_data = request.data.get('sets', [])
    for set_data in sets_data:
        set_id = set_data.get('set_id')
        if set_id:
            try:
                workout_set = WorkoutSet.objects.get(id=set_id, workout_day=day)
                workout_set.is_completed    = True
                workout_set.actual_sets     = set_data.get('actual_sets')
                workout_set.actual_reps     = set_data.get('actual_reps')
                workout_set.actual_weight_kg = set_data.get('actual_weight_kg')
                workout_set.save()
            except WorkoutSet.DoesNotExist:
                pass

    # Отмечаем день
    day.is_completed = True
    day.completed_at = timezone.now()
    day.notes        = request.data.get('notes', '')
    day.save()

    # Проверяем завершение плана
    plan      = day.plan
    all_days  = plan.workout_days.filter(is_rest_day=False).count()
    done_days = plan.workout_days.filter(is_completed=True).count()

    if all_days > 0 and done_days >= all_days:
        plan.status = 'completed'
        plan.save()

    return Response({
        "message":          "Тренировка выполнена! Отличная работа!",
        "day":              WorkoutDaySerializer(day).data,
        "plan_progress":    f"{done_days}/{all_days} дней",
        "plan_completed":   plan.status == 'completed',
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def update_workout_set(request, set_id):
    """
    POST /api/workouts/sets/<id>/update/
    Обновить фактические данные по подходу.
    """
    workout_set = get_object_or_404(WorkoutSet, id=set_id, workout_day__plan__user=request.user)
    serializer  = WorkoutSetSerializer(workout_set, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ──────────────────────────────────────────────
#  СТАТИСТИКА ПРОГРЕССА
# ──────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def workout_stats(request):
    """
    GET /api/workouts/stats/
    Общая статистика тренировок пользователя.
    """
    user  = request.user
    plans = WorkoutPlan.objects.filter(user=user)

    total_days_done = WorkoutDay.objects.filter(
        plan__user=user, is_completed=True, is_rest_day=False
    ).count()

    total_sets_done = WorkoutSet.objects.filter(
        workout_day__plan__user=user, is_completed=True
    ).count()

    active_plan = plans.filter(status='active').first()

    return Response({
        "total_plans":          plans.count(),
        "completed_plans":      plans.filter(status='completed').count(),
        "total_workouts_done":  total_days_done,
        "total_sets_done":      total_sets_done,
        "active_plan": {
            "name":     active_plan.name            if active_plan else None,
            "progress": active_plan.progress_percent if active_plan else None,
        } if active_plan else None,
        "current_streak":       _calculate_streak(user),
    })


def _calculate_streak(user):
    """Считает текущую серию последовательных дней тренировок."""
    from datetime import date, timedelta
    completed_dates = set(
        WorkoutDay.objects.filter(
            plan__user=user, is_completed=True, is_rest_day=False
        ).values_list('completed_at__date', flat=True)
    )

    streak = 0
    check_date = date.today()
    while check_date in completed_dates:
        streak     += 1
        check_date -= timedelta(days=1)
    return streak