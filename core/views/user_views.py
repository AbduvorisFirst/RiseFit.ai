"""
users/views.py
Регистрация, профиль пользователя, подписки, калькулятор калорий.
"""

from django.contrib.auth.models import User
from django.utils import timezone

from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import UserProfile, Subscription
from core.serializers.user_serializers import (
    RegisterSerializer,
    UserProfileSerializer,
    UserProfileCreateSerializer,
    SubscriptionSerializer,
)


# ──────────────────────────────────────────────
#  AUTH
# ──────────────────────────────────────────────

class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/
    Регистрация нового пользователя.
    Возвращает JWT токены сразу после регистрации.
    """
    queryset         = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Выдаём JWT токены сразу
        refresh = RefreshToken.for_user(user)
        return Response({
            "user": {
                "id":       user.id,
                "username": user.username,
                "email":    user.email,
            },
            "tokens": {
                "refresh": str(refresh),
                "access":  str(refresh.access_token),
            },
            "message": "Регистрация успешна. Заполните профиль."
        }, status=status.HTTP_201_CREATED)


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Инвалидирует refresh token (добавляет в чёрный список).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Выход выполнен."}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"error": "Неверный токен."}, status=status.HTTP_400_BAD_REQUEST)


# ──────────────────────────────────────────────
#  USER PROFILE
# ──────────────────────────────────────────────

class UserProfileView(APIView):
    """
    GET  /api/users/profile/   — получить свой профиль
    POST /api/users/profile/   — создать профиль (онбординг)
    PUT  /api/users/profile/   — полное обновление
    PATCH /api/users/profile/  — частичное обновление
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            profile = request.user.profile
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response(
                {"message": "Профиль не найден. Пройдите онбординг.", "has_profile": False},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        if hasattr(request.user, 'profile'):
            return Response(
                {"error": "Профиль уже существует. Используйте PATCH для обновления."},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = UserProfileCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(UserProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        profile = generics.get_object_or_404(UserProfile, user=request.user)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def put(self, request):
        profile = generics.get_object_or_404(UserProfile, user=request.user)
        serializer = UserProfileSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ──────────────────────────────────────────────
#  CALORIE CALCULATOR
# ──────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def calorie_calculator(request):
    """
    POST /api/users/calculator/
    Калькулятор калорий без регистрации — для лендинга и онбординга.

    Тело запроса:
    {
        "gender": "male",
        "age": 25,
        "weight_kg": 80,
        "height_cm": 180,
        "activity_level": "moderate",
        "goal": "weight_loss"
    }
    """
    required = ['gender', 'age', 'weight_kg', 'height_cm', 'activity_level', 'goal']
    for field in required:
        if field not in request.data:
            return Response({"error": f"Поле '{field}' обязательно."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        gender         = request.data['gender']
        age            = int(request.data['age'])
        weight         = float(request.data['weight_kg'])
        height         = float(request.data['height_cm'])
        activity_level = request.data['activity_level']
        goal           = request.data['goal']
    except (ValueError, TypeError):
        return Response({"error": "Некорректные данные."}, status=status.HTTP_400_BAD_REQUEST)

    # BMR по Mifflin-St Jeor
    if gender == 'male':
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    elif gender == 'female':
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 78  # среднее

    # TDEE
    multipliers = {
        'sedentary':   1.2,
        'light':       1.375,
        'moderate':    1.55,
        'active':      1.725,
        'very_active': 1.9,
    }
    tdee = bmr * multipliers.get(activity_level, 1.55)

    # Целевые калории
    if goal == 'weight_loss':
        target_calories = tdee - 500
        goal_label      = 'Похудение (дефицит -500 ккал)'
    elif goal == 'muscle_gain':
        target_calories = tdee + 300
        goal_label      = 'Набор массы (профицит +300 ккал)'
    else:
        target_calories = tdee
        goal_label      = 'Поддержание формы'

    # BMI
    h_m = height / 100
    bmi = round(weight / (h_m * h_m), 1)
    if bmi < 18.5:
        bmi_category = 'Недостаточный вес'
    elif bmi < 25:
        bmi_category = 'Норма'
    elif bmi < 30:
        bmi_category = 'Избыточный вес'
    else:
        bmi_category = 'Ожирение'

    # КБЖУ на целевые калории
    protein_g = round(weight * 2.0)               # 2г/кг
    fat_g     = round(target_calories * 0.25 / 9) # 25% калорий из жиров
    carbs_g   = round((target_calories - protein_g * 4 - fat_g * 9) / 4)

    return Response({
        "bmr":            round(bmr, 1),
        "tdee":           round(tdee, 1),
        "target_calories": round(target_calories, 1),
        "goal":           goal,
        "goal_label":     goal_label,
        "bmi":            bmi,
        "bmi_category":   bmi_category,
        "macros": {
            "protein_g": protein_g,
            "carbs_g":   carbs_g,
            "fat_g":     fat_g,
            "water_ml":  round(weight * 35),  # 35мл/кг
        },
        "tip": "Зарегистрируйтесь чтобы получить персональную AI-программу тренировок."
    })


# ──────────────────────────────────────────────
#  SUBSCRIPTIONS
# ──────────────────────────────────────────────

class SubscriptionListView(generics.ListAPIView):
    """
    GET /api/users/subscriptions/
    Все подписки текущего пользователя.
    """
    serializer_class   = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).select_related('influencer')


class ActiveSubscriptionView(APIView):
    """
    GET /api/users/subscriptions/active/
    Активная подписка пользователя (если есть).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sub = Subscription.objects.filter(
            user=request.user, status__in=['active', 'trialing']
        ).select_related('influencer').first()

        if not sub:
            return Response(
                {"message": "Нет активной подписки.", "has_subscription": False},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response({
            "has_subscription": True,
            "subscription":     SubscriptionSerializer(sub).data,
        })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def cancel_subscription(request, pk):
    """
    POST /api/users/subscriptions/<uuid>/cancel/
    Отменить подписку.
    """
    sub = generics.get_object_or_404(Subscription, pk=pk, user=request.user)

    if sub.status == 'cancelled':
        return Response({"error": "Подписка уже отменена."}, status=status.HTTP_400_BAD_REQUEST)

    # TODO: вызвать stripe.Subscription.delete(sub.stripe_subscription_id)
    sub.status       = 'cancelled'
    sub.cancelled_at = timezone.now()
    sub.save()

    return Response({"message": "Подписка отменена.", "subscription": SubscriptionSerializer(sub).data})
