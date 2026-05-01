"""
influencers/serializers.py
"""

from rest_framework import serializers
from core.models import Influencer, InfluencerRule


class InfluencerRuleSerializer(serializers.ModelSerializer):

    goal_display = serializers.CharField(source='get_goal_display', read_only=True)

    class Meta:
        model  = InfluencerRule
        fields = (
            'id', 'goal', 'goal_display',
            'sets_count', 'reps_count', 'rest_seconds',
            'workouts_per_week', 'intensity_notes',
        )


class InfluencerSerializer(serializers.ModelSerializer):
    """Публичный профиль инфлюенсера для пользователей приложения."""

    niche_display      = serializers.CharField(source='get_niche_display', read_only=True)
    rules              = InfluencerRuleSerializer(many=True, read_only=True)
    exercise_count     = serializers.SerializerMethodField()
    monthly_revenue    = serializers.ReadOnlyField()

    class Meta:
        model  = Influencer
        fields = (
            'id', 'brand_name', 'slug', 'niche', 'niche_display',
            'bio', 'profile_photo', 'methodology',
            'subscribers_count', 'exercise_count',
            'rules', 'is_active', 'created_at',
            # только для самого инфлюенсера:
            'monthly_revenue',
        )
        read_only_fields = ('slug', 'subscribers_count', 'created_at')

    def get_exercise_count(self, obj):
        return obj.exercises.filter(is_active=True).count()


class InfluencerPublicSerializer(serializers.ModelSerializer):
    """Краткая карточка для каталога инфлюенсеров."""

    niche_display  = serializers.CharField(source='get_niche_display', read_only=True)
    exercise_count = serializers.SerializerMethodField()

    class Meta:
        model  = Influencer
        fields = (
            'id', 'brand_name', 'slug', 'niche', 'niche_display',
            'bio', 'profile_photo', 'subscribers_count', 'exercise_count',
        )

    def get_exercise_count(self, obj):
        return obj.exercises.filter(is_active=True).count()


class InfluencerCreateUpdateSerializer(serializers.ModelSerializer):
    """Для создания/редактирования профиля самим инфлюенсером."""

    class Meta:
        model  = Influencer
        fields = (
            'brand_name', 'slug', 'niche', 'bio',
            'profile_photo', 'methodology', 'revenue_share',
            'stripe_account_id',
        )

    def create(self, validated_data):
        user = self.context['request'].user
        return Influencer.objects.create(user=user, **validated_data)