"""
nutrition/views.py
Дневник питания, калории, замеры тела.
"""

from datetime import date, timedelta

from django.db.models import Sum
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import CalorieLog, NutritionGoal, ProgressEntry
from core.serializers.nutrition_serializers import CalorieLogSerializer, NutritionGoalSerializer, ProgressEntrySerializer


# ──────────────────────────────────────────────
#  NUTRITION GOALS
# ──────────────────────────────────────────────

class NutritionGoalView(APIView):
    """
    GET   /api/nutrition/goal/   — получить цели КБЖУ
    POST  /api/nutrition/goal/   — установить цели
    PATCH /api/nutrition/goal/   — обновить цели
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            goal = request.user.nutrition_goal
            return Response(NutritionGoalSerializer(goal).data)
        except NutritionGoal.DoesNotExist:
            # Пробуем взять из профиля
            if hasattr(request.user, 'profile') and request.user.profile.daily_calorie_goal:
                profile = request.user.profile
                cal     = profile.daily_calorie_goal
                w       = float(profile.weight_kg)
                protein = round(w * 2.0)
                fat     = round(cal * 0.25 / 9)
                carbs   = round((cal - protein * 4 - fat * 9) / 4)
                return Response({
                    "calories":  cal,
                    "protein_g": protein,
                    "carbs_g":   carbs,
                    "fat_g":     fat,
                    "water_ml":  round(w * 35),
                    "note":      "Автоматически рассчитано из профиля. Сохраните для трекинга.",
                })
            return Response({"message": "Цели не установлены."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        if hasattr(request.user, 'nutrition_goal'):
            return Response({"error": "Цели уже установлены. Используйте PATCH."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = NutritionGoalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        goal, _ = NutritionGoal.objects.get_or_create(user=request.user, defaults={
            'calories': 2000, 'protein_g': 150, 'carbs_g': 200, 'fat_g': 65
        })
        serializer = NutritionGoalSerializer(goal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ──────────────────────────────────────────────
#  CALORIE LOG
# ──────────────────────────────────────────────

class CalorieLogListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/nutrition/log/?date=2025-01-15   — записи за день
    POST /api/nutrition/log/                   — добавить приём пищи
    """
    serializer_class   = CalorieLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs        = CalorieLog.objects.filter(user=self.request.user)
        date_str  = self.request.query_params.get('date')
        if date_str:
            try:
                filter_date = date.fromisoformat(date_str)
                qs = qs.filter(date=filter_date)
            except ValueError:
                pass
        else:
            # По умолчанию — сегодня
            qs = qs.filter(date=date.today())
        return qs.order_by('meal_type', 'logged_at')


class CalorieLogDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/nutrition/log/<id>/
    """
    serializer_class   = CalorieLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CalorieLog.objects.filter(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def daily_summary(request):
    """
    GET /api/nutrition/summary/?date=2025-01-15
    Дневной итог по КБЖУ и сравнение с целями.
    """
    date_str = request.query_params.get('date')
    try:
        target_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        target_date = date.today()

    logs = CalorieLog.objects.filter(user=request.user, date=target_date)
    totals = logs.aggregate(
        total_calories = Sum('calories'),
        total_protein  = Sum('protein_g'),
        total_carbs    = Sum('carbs_g'),
        total_fat      = Sum('fat_g'),
    )

    consumed_cal  = totals['total_calories'] or 0
    consumed_prot = float(totals['total_protein'] or 0)
    consumed_carb = float(totals['total_carbs']   or 0)
    consumed_fat  = float(totals['total_fat']     or 0)

    # Цели
    goal_cal  = 2000
    goal_prot = 150
    goal_carb = 200
    goal_fat  = 65

    try:
        nutrition_goal = request.user.nutrition_goal
        goal_cal  = nutrition_goal.calories
        goal_prot = nutrition_goal.protein_g
        goal_carb = nutrition_goal.carbs_g
        goal_fat  = nutrition_goal.fat_g
    except NutritionGoal.DoesNotExist:
        if hasattr(request.user, 'profile') and request.user.profile.daily_calorie_goal:
            goal_cal = request.user.profile.daily_calorie_goal

    # Разбивка по приёмам пищи
    meals_breakdown = {}
    for log in logs:
        meal = log.meal_type
        if meal not in meals_breakdown:
            meals_breakdown[meal] = {'calories': 0, 'items': 0}
        meals_breakdown[meal]['calories'] += log.calories
        meals_breakdown[meal]['items']    += 1

    return Response({
        "date":    target_date.isoformat(),
        "consumed": {
            "calories":  consumed_cal,
            "protein_g": round(consumed_prot, 1),
            "carbs_g":   round(consumed_carb, 1),
            "fat_g":     round(consumed_fat,  1),
        },
        "goals": {
            "calories":  goal_cal,
            "protein_g": goal_prot,
            "carbs_g":   goal_carb,
            "fat_g":     goal_fat,
        },
        "remaining": {
            "calories":  max(0, goal_cal  - consumed_cal),
            "protein_g": max(0, goal_prot - consumed_prot),
            "carbs_g":   max(0, goal_carb - consumed_carb),
            "fat_g":     max(0, goal_fat  - consumed_fat),
        },
        "progress_percent": round((consumed_cal / goal_cal) * 100, 1) if goal_cal > 0 else 0,
        "meals_breakdown":  meals_breakdown,
        "log_entries_count": logs.count(),
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def weekly_nutrition_stats(request):
    """
    GET /api/nutrition/stats/weekly/
    Статистика питания за последние 7 дней.
    """
    today  = date.today()
    week_ago = today - timedelta(days=6)

    days_data = []
    for i in range(7):
        day = week_ago + timedelta(days=i)
        logs = CalorieLog.objects.filter(user=request.user, date=day)
        total = logs.aggregate(cal=Sum('calories'))['cal'] or 0
        days_data.append({
            "date":     day.isoformat(),
            "weekday":  day.strftime('%a'),
            "calories": total,
        })

    avg_calories = sum(d['calories'] for d in days_data) / 7

    return Response({
        "period":       f"{week_ago} – {today}",
        "avg_calories": round(avg_calories, 0),
        "days":         days_data,
    })


# ──────────────────────────────────────────────
#  PROGRESS ENTRIES (замеры тела)
# ──────────────────────────────────────────────

class ProgressEntryListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/nutrition/progress/   — история замеров
    POST /api/nutrition/progress/   — добавить замер
    """
    serializer_class   = ProgressEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProgressEntry.objects.filter(user=self.request.user).order_by('-date')


class ProgressEntryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/nutrition/progress/<id>/
    """
    serializer_class   = ProgressEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProgressEntry.objects.filter(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def weight_chart(request):
    """
    GET /api/nutrition/progress/weight/
    Данные для графика веса (последние 90 дней).
    """
    entries = ProgressEntry.objects.filter(
        user=request.user, weight_kg__isnull=False
    ).order_by('date').values('date', 'weight_kg')[:90]

    data = [{"date": e['date'].isoformat(), "weight_kg": float(e['weight_kg'])} for e in entries]

    if data:
        start_weight = data[0]['weight_kg']
        end_weight   = data[-1]['weight_kg']
        change       = round(end_weight - start_weight, 1)
    else:
        change = 0

    return Response({
        "data":          data,
        "total_change_kg": change,
        "points_count":  len(data),
    })