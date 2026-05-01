"""
workouts/serializers.py
"""

from rest_framework import serializers
from core.models import Exercise, WorkoutPlan, WorkoutDay, WorkoutSet


class ExerciseSerializer(serializers.ModelSerializer):

    category_display   = serializers.CharField(source='get_category_display',          read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display',         read_only=True)
    equipment_display  = serializers.CharField(source='get_equipment_required_display', read_only=True)
    influencer_name    = serializers.CharField(source='influencer.brand_name',          read_only=True)

    class Meta:
        model  = Exercise
        fields = (
            'id', 'influencer', 'influencer_name', 'name', 'description',
            'category', 'category_display',
            'difficulty', 'difficulty_display',
            'equipment_required', 'equipment_display',
            'video_url', 'thumbnail_url', 'duration_seconds',
            'primary_muscles', 'secondary_muscles', 'joints_used',
            'contraindications', 'calories_per_minute', 'is_active',
        )
        read_only_fields = ('influencer',)

    def create(self, validated_data):
        influencer = self.context['request'].user.influencer_profile
        return Exercise.objects.create(influencer=influencer, **validated_data)


class WorkoutSetSerializer(serializers.ModelSerializer):

    exercise_name      = serializers.CharField(source='exercise.name',      read_only=True)
    exercise_video_url = serializers.CharField(source='exercise.video_url', read_only=True)
    exercise_thumbnail = serializers.CharField(source='exercise.thumbnail_url', read_only=True)

    class Meta:
        model  = WorkoutSet
        fields = (
            'id', 'exercise', 'exercise_name', 'exercise_video_url', 'exercise_thumbnail',
            'order', 'sets_count', 'reps_count', 'duration_seconds',
            'rest_seconds', 'weight_kg', 'ai_tip',
            'is_completed', 'actual_sets', 'actual_reps', 'actual_weight_kg',
        )


class WorkoutDaySerializer(serializers.ModelSerializer):

    day_of_week_display = serializers.CharField(source='get_day_of_week_display', read_only=True)
    sets                = WorkoutSetSerializer(many=True, read_only=True)
    sets_count          = serializers.SerializerMethodField()

    class Meta:
        model  = WorkoutDay
        fields = (
            'id', 'week_number', 'day_of_week', 'day_of_week_display',
            'title', 'is_rest_day', 'is_completed', 'completed_at',
            'notes', 'sets', 'sets_count',
        )

    def get_sets_count(self, obj):
        return obj.sets.count()


class WorkoutDayListSerializer(serializers.ModelSerializer):
    """Краткая версия дня — без упражнений, для списков."""

    day_of_week_display = serializers.CharField(source='get_day_of_week_display', read_only=True)
    sets_count          = serializers.SerializerMethodField()

    class Meta:
        model  = WorkoutDay
        fields = (
            'id', 'week_number', 'day_of_week', 'day_of_week_display',
            'title', 'is_rest_day', 'is_completed', 'sets_count',
        )

    def get_sets_count(self, obj):
        return obj.sets.count()


class WorkoutPlanSerializer(serializers.ModelSerializer):

    progress_percent = serializers.ReadOnlyField()
    total_days       = serializers.ReadOnlyField()
    completed_days   = serializers.ReadOnlyField()
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    influencer_name  = serializers.CharField(source='influencer.brand_name', read_only=True)
    workout_days     = WorkoutDayListSerializer(many=True, read_only=True)

    class Meta:
        model  = WorkoutPlan
        fields = (
            'id', 'user', 'influencer', 'influencer_name',
            'name', 'status', 'status_display',
            'duration_weeks', 'ai_generated', 'ai_notes',
            'start_date', 'end_date',
            'progress_percent', 'total_days', 'completed_days',
            'workout_days', 'created_at',
        )
        read_only_fields = ('id', 'user', 'ai_generated', 'ai_notes', 'created_at')


class WorkoutPlanDetailSerializer(WorkoutPlanSerializer):
    """Полный план с детальными днями и упражнениями."""

    workout_days = WorkoutDaySerializer(many=True, read_only=True)