"""
nutrition/serializers.py
"""

from rest_framework import serializers
from core.models import CalorieLog, NutritionGoal, ProgressEntry


class NutritionGoalSerializer(serializers.ModelSerializer):

    class Meta:
        model  = NutritionGoal
        fields = ('id', 'calories', 'protein_g', 'carbs_g', 'fat_g', 'water_ml', 'updated_at')
        read_only_fields = ('updated_at',)


class CalorieLogSerializer(serializers.ModelSerializer):

    meal_type_display = serializers.CharField(source='get_meal_type_display', read_only=True)

    class Meta:
        model  = CalorieLog
        fields = (
            'id', 'date', 'meal_type', 'meal_type_display',
            'food_name', 'amount_grams',
            'calories', 'protein_g', 'carbs_g', 'fat_g',
            'notes', 'logged_at',
        )
        read_only_fields = ('logged_at',)

    def create(self, validated_data):
        return CalorieLog.objects.create(user=self.context['request'].user, **validated_data)


class ProgressEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model  = ProgressEntry
        fields = (
            'id', 'date',
            'weight_kg', 'body_fat_percent',
            'chest_cm', 'waist_cm', 'hips_cm', 'bicep_cm',
            'photo', 'notes', 'created_at',
        )
        read_only_fields = ('created_at',)

    def create(self, validated_data):
        return ProgressEntry.objects.create(user=self.context['request'].user, **validated_data)