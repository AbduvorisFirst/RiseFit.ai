"""
core/admin.py  (или разложи по своим приложениям: users/admin.py, influencers/admin.py и т.д.)
Django Admin — панель управления для всего проекта RiseFit.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from core.models import (
    Influencer, InfluencerRule,
    UserProfile, Subscription,
    Exercise, WorkoutPlan, WorkoutDay, WorkoutSet,
    NutritionGoal, CalorieLog, ProgressEntry,
)


# ──────────────────────────────────────────────
#  USER + PROFILE (inline)
# ──────────────────────────────────────────────

class UserProfileInline(admin.StackedInline):
    model  = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль'
    fields = (
        'gender', 'age', 'weight_kg', 'height_cm',
        'goal', 'activity_level', 'available_equipment',
        'injuries', 'bmr', 'tdee', 'daily_calorie_goal',
        'influencer',
    )
    readonly_fields = ('bmr', 'tdee', 'daily_calorie_goal')


class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display  = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter   = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# ──────────────────────────────────────────────
#  INFLUENCER
# ──────────────────────────────────────────────

class InfluencerRuleInline(admin.TabularInline):
    model  = InfluencerRule
    extra  = 1
    fields = ('goal', 'sets_count', 'reps_count', 'rest_seconds', 'workouts_per_week', 'intensity_notes')


@admin.register(Influencer)
class InfluencerAdmin(admin.ModelAdmin):
    list_display  = ('brand_name', 'slug', 'niche', 'subscribers_count', 'monthly_revenue_display', 'is_active')
    list_filter   = ('niche', 'is_active')
    search_fields = ('brand_name', 'slug', 'user__username')
    prepopulated_fields = {'slug': ('brand_name',)}
    readonly_fields = ('subscribers_count', 'created_at', 'updated_at')
    inlines = [InfluencerRuleInline]

    fieldsets = (
        ('Основное', {
            'fields': ('user', 'brand_name', 'slug', 'niche', 'bio', 'profile_photo', 'methodology')
        }),
        ('Финансы', {
            'fields': ('revenue_share', 'stripe_account_id')
        }),
        ('Статистика', {
            'fields': ('subscribers_count', 'is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def monthly_revenue_display(self, obj):
        revenue = obj.monthly_revenue
        return format_html('<b style="color:green">${:.2f}</b>', revenue)
    monthly_revenue_display.short_description = 'Доход/мес'


# ──────────────────────────────────────────────
#  SUBSCRIPTION
# ──────────────────────────────────────────────

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'influencer', 'status_colored', 'price_usd', 'started_at', 'expires_at')
    list_filter   = ('status', 'influencer')
    search_fields = ('user__username', 'user__email', 'stripe_subscription_id')
    readonly_fields = ('id', 'started_at', 'stripe_subscription_id', 'stripe_customer_id')

    def status_colored(self, obj):
        colors = {
            'active':    'green',
            'trialing':  'blue',
            'cancelled': 'red',
            'expired':   'gray',
            'past_due':  'orange',
        }
        color = colors.get(obj.status, 'black')
        return format_html('<b style="color:{}">{}</b>', color, obj.get_status_display())
    status_colored.short_description = 'Статус'


# ──────────────────────────────────────────────
#  EXERCISE
# ──────────────────────────────────────────────

@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display  = ('name', 'influencer', 'category', 'difficulty', 'equipment_required', 'is_active')
    list_filter   = ('category', 'difficulty', 'equipment_required', 'is_active', 'influencer')
    search_fields = ('name', 'primary_muscles', 'influencer__brand_name')
    list_editable = ('is_active',)

    fieldsets = (
        ('Основное', {
            'fields': ('influencer', 'name', 'description', 'category', 'difficulty', 'equipment_required')
        }),
        ('Видео', {
            'fields': ('video_url', 'thumbnail_url', 'duration_seconds')
        }),
        ('Мышцы и противопоказания', {
            'fields': ('primary_muscles', 'secondary_muscles', 'joints_used', 'contraindications')
        }),
        ('Прочее', {
            'fields': ('calories_per_minute', 'is_active'),
            'classes': ('collapse',),
        }),
    )


# ──────────────────────────────────────────────
#  WORKOUT PLAN
# ──────────────────────────────────────────────

class WorkoutSetInline(admin.TabularInline):
    model  = WorkoutSet
    extra  = 0
    fields = ('exercise', 'order', 'sets_count', 'reps_count', 'rest_seconds', 'ai_tip', 'is_completed')
    readonly_fields = ('ai_tip',)


class WorkoutDayInline(admin.TabularInline):
    model  = WorkoutDay
    extra  = 0
    fields = ('week_number', 'day_of_week', 'title', 'is_rest_day', 'is_completed')
    show_change_link = True


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display  = ('name', 'user', 'influencer', 'status', 'progress_display', 'start_date', 'ai_generated')
    list_filter   = ('status', 'ai_generated', 'influencer')
    search_fields = ('name', 'user__username', 'influencer__brand_name')
    readonly_fields = ('id', 'created_at', 'updated_at', 'progress_percent', 'total_days', 'completed_days')
    inlines = [WorkoutDayInline]

    def progress_display(self, obj):
        p = obj.progress_percent
        color = 'green' if p >= 80 else 'orange' if p >= 40 else 'red'
        return format_html('<b style="color:{}">{:.0f}%</b>', color, p)
    progress_display.short_description = 'Прогресс'


@admin.register(WorkoutDay)
class WorkoutDayAdmin(admin.ModelAdmin):
    list_display  = ('__str__', 'plan', 'is_rest_day', 'is_completed', 'completed_at')
    list_filter   = ('is_rest_day', 'is_completed', 'day_of_week')
    inlines       = [WorkoutSetInline]


# ──────────────────────────────────────────────
#  NUTRITION
# ──────────────────────────────────────────────

@admin.register(NutritionGoal)
class NutritionGoalAdmin(admin.ModelAdmin):
    list_display  = ('user', 'calories', 'protein_g', 'carbs_g', 'fat_g', 'updated_at')
    search_fields = ('user__username',)


@admin.register(CalorieLog)
class CalorieLogAdmin(admin.ModelAdmin):
    list_display  = ('user', 'date', 'meal_type', 'food_name', 'calories', 'logged_at')
    list_filter   = ('meal_type', 'date')
    search_fields = ('user__username', 'food_name')
    date_hierarchy = 'date'


@admin.register(ProgressEntry)
class ProgressEntryAdmin(admin.ModelAdmin):
    list_display  = ('user', 'date', 'weight_kg', 'body_fat_percent', 'waist_cm')
    search_fields = ('user__username',)
    date_hierarchy = 'date'
