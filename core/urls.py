"""
users/urls.py
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import user_views, influencer_views, workout_views, nutrition_views


urlpatterns = [

    ######################################### users ############################################################

    # Auth
    path('auth/register/',       user_views.RegisterView.as_view(),         name='register'),
    path('auth/login/',          TokenObtainPairView.as_view(),        name='login'),
    path('auth/refresh/',        TokenRefreshView.as_view(),           name='token_refresh'),
    path('auth/logout/',         user_views.LogoutView.as_view(),           name='logout'),

    # Profile
    path('users/profile/',       user_views.UserProfileView.as_view(),      name='user_profile'),

    # Calculator (публичный)
    path('users/calculator/',    user_views.calorie_calculator,             name='calorie_calculator'),

    # Subscriptions
    path('users/subscriptions/',          user_views.SubscriptionListView.as_view(),   name='subscriptions'),
    path('users/subscriptions/active/',   user_views.ActiveSubscriptionView.as_view(), name='active_subscription'),
    path('users/subscriptions/<uuid:pk>/cancel/', user_views.cancel_subscription,     name='cancel_subscription'),


    ############################################### influencer  ###################################################################

    path('influencers/',            influencer_views.InfluencerListView.as_view(),          name='influencer_list'),
    path('influencers/<slug:slug>/', influencer_views.InfluencerDetailView.as_view(),       name='influencer_detail'),

    # B2B дашборд
    path('influencers/dashboard/',  influencer_views.InfluencerDashboardView.as_view(),     name='influencer_dashboard'),
    path('influencers/subscribers/', influencer_views.influencer_subscribers,               name='influencer_subscribers'),

    # Правила генерации
    path('influencers/rules/',      influencer_views.InfluencerRuleListCreateView.as_view(), name='influencer_rules'),
    path('influencers/rules/<int:pk>/', influencer_views.InfluencerRuleDetailView.as_view(), name='influencer_rule_detail'),

    ################################################   workout    ###############################################################################

    path('workouts/exercises/',           workout_views.ExerciseListCreateView.as_view(), name='exercise_list'),
    path('workouts/exercises/<int:pk>/',  workout_views.ExerciseDetailView.as_view(),     name='exercise_detail'),

    # Планы
    path('workouts/plans/',               workout_views.WorkoutPlanListView.as_view(),    name='plan_list'),
    path('workouts/plans/active/',        workout_views.ActivePlanView.as_view(),         name='active_plan'),
    path('workouts/plans/generate/',      workout_views.GeneratePlanView.as_view(),       name='generate_plan'),
    path('workouts/plans/<uuid:pk>/',     workout_views.WorkoutPlanDetailView.as_view(),  name='plan_detail'),

    # Дни и выполнение
    path('workouts/days/<int:pk>/',               workout_views.WorkoutDayDetailView.as_view(), name='workout_day'),
    path('workouts/days/<int:day_id>/complete/',  workout_views.complete_workout_day,           name='complete_day'),
    path('workouts/sets/<int:set_id>/update/',    workout_views.update_workout_set,             name='update_set'),

    # Статистика
    path('workouts/stats/',              workout_views.workout_stats,                     name='workout_stats'),

    ############################################### nutrition ##############################################################################

    # Цели КБЖУ
    path('nutrition/goal/',                   nutrition_views.NutritionGoalView.as_view(),            name='nutrition_goal'),

    # Дневник питания
    path('nutrition/log/',                    nutrition_views.CalorieLogListCreateView.as_view(),      name='calorie_log'),
    path('nutrition/log/<int:pk>/',           nutrition_views.CalorieLogDetailView.as_view(),          name='calorie_log_detail'),
    path('nutrition/summary/',                nutrition_views.daily_summary,                           name='daily_summary'),
    path('nutrition/stats/weekly/',           nutrition_views.weekly_nutrition_stats,                  name='weekly_nutrition'),

    # Прогресс / замеры
    path('nutrition/progress/',               nutrition_views.ProgressEntryListCreateView.as_view(),   name='progress_list'),
    path('nutrition/progress/<int:pk>/',      nutrition_views.ProgressEntryDetailView.as_view(),       name='progress_detail'),
    path('nutrition/progress/weight/',        nutrition_views.weight_chart,                            name='weight_chart'),

    ################################################  payment  #########################################################################


]