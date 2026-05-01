"""
users/serializers.py
Сериализаторы для регистрации, профиля пользователя и подписок.
"""

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from core.models import UserProfile, Subscription


# ──────────────────────────────────────────────
#  AUTH
# ──────────────────────────────────────────────

class RegisterSerializer(serializers.ModelSerializer):
    """Регистрация нового пользователя."""

    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all(), message="Email уже используется.")]
    )
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label="Подтверждение пароля")

    class Meta:
        model  = User
        fields = ('username', 'email', 'password', 'password2', 'first_name', 'last_name')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Пароли не совпадают."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class UserShortSerializer(serializers.ModelSerializer):
    """Краткая инфо о пользователе — для вложенных ответов."""

    class Meta:
        model  = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = fields


# ──────────────────────────────────────────────
#  USER PROFILE
# ──────────────────────────────────────────────

class UserProfileSerializer(serializers.ModelSerializer):
    """Полный профиль пользователя с расчётными полями."""

    user       = UserShortSerializer(read_only=True)
    bmi        = serializers.ReadOnlyField()
    bmr        = serializers.ReadOnlyField()
    tdee       = serializers.ReadOnlyField()

    # Человекочитаемые лейблы
    goal_display            = serializers.CharField(source='get_goal_display',            read_only=True)
    gender_display          = serializers.CharField(source='get_gender_display',          read_only=True)
    activity_level_display  = serializers.CharField(source='get_activity_level_display',  read_only=True)
    equipment_display       = serializers.CharField(source='get_available_equipment_display', read_only=True)

    class Meta:
        model  = UserProfile
        fields = (
            'id', 'user',
            'gender', 'gender_display',
            'age', 'weight_kg', 'height_cm', 'body_fat_percent',
            'goal', 'goal_display',
            'activity_level', 'activity_level_display',
            'target_weight_kg',
            'available_equipment', 'equipment_display',
            'injuries', 'health_notes',
            'bmi', 'bmr', 'tdee', 'daily_calorie_goal',
            'avatar', 'created_at', 'updated_at',
        )
        read_only_fields = ('bmi', 'bmr', 'tdee', 'daily_calorie_goal', 'created_at', 'updated_at')

    def update(self, instance, validated_data):
        # save() автоматически пересчитает BMR/TDEE
        return super().update(instance, validated_data)


class UserProfileCreateSerializer(serializers.ModelSerializer):
    """Создание профиля при онбординге (без user — берём из request)."""

    class Meta:
        model  = UserProfile
        fields = (
            'gender', 'age', 'weight_kg', 'height_cm', 'body_fat_percent',
            'goal', 'activity_level', 'target_weight_kg',
            'available_equipment', 'injuries', 'health_notes', 'influencer',
        )

    def create(self, validated_data):
        user = self.context['request'].user
        return UserProfile.objects.create(user=user, **validated_data)


# ──────────────────────────────────────────────
#  SUBSCRIPTION
# ──────────────────────────────────────────────

class SubscriptionSerializer(serializers.ModelSerializer):
    """Подписка пользователя."""

    is_active          = serializers.ReadOnlyField()
    status_display     = serializers.CharField(source='get_status_display', read_only=True)
    influencer_name    = serializers.CharField(source='influencer.brand_name', read_only=True)

    class Meta:
        model  = Subscription
        fields = (
            'id', 'user', 'influencer', 'influencer_name',
            'status', 'status_display', 'is_active',
            'price_usd', 'stripe_subscription_id',
            'started_at', 'expires_at', 'cancelled_at',
        )
        read_only_fields = (
            'id', 'user', 'status', 'stripe_subscription_id',
            'started_at', 'expires_at', 'cancelled_at',
        )