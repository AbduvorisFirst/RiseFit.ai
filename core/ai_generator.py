"""
workouts/ai_generator.py
AI-генератор персональных программ тренировок.
Использует правила инфлюенсера + профиль пользователя.
AI советы: Google Gemini (gemini-2.5-flash-lite).

Установи зависимость:
    pip install google-generativeai
"""

import random
import logging
from datetime import date, timedelta

import google.generativeai as genai
from django.conf import settings

from .models import Exercise, WorkoutPlan, WorkoutDay, WorkoutSet

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  ИНИЦИАЛИЗАЦИЯ GEMINI
# ──────────────────────────────────────────────

def _get_gemini_client():
    """Возвращает сконфигурированную модель Gemini."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError("GEMINI_API_KEY не задан в settings.py / .env")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.5-flash-lite')


# ──────────────────────────────────────────────
#  ФИЛЬТРАЦИЯ УПРАЖНЕНИЙ
# ──────────────────────────────────────────────

def filter_exercises_for_user(influencer, profile):
    """
    Возвращает QuerySet упражнений подходящих пользователю:
    - из библиотеки инфлюенсера
    - подходящих по оборудованию
    - не противопоказанных при травмах
    """
    qs = Exercise.objects.filter(influencer=influencer, is_active=True)

    # Фильтр по оборудованию
    equipment_map = {
        'none':       ['none'],
        'dumbbells':  ['none', 'dumbbells'],
        'barbell':    ['none', 'dumbbells', 'barbell'],
        'resistance': ['none', 'resistance'],
        'home_gym':   ['none', 'dumbbells', 'resistance'],
        'gym':        ['none', 'dumbbells', 'barbell', 'gym', 'resistance'],
    }
    allowed_equipment = equipment_map.get(profile.available_equipment, ['none'])
    qs = qs.filter(equipment_required__in=allowed_equipment)

    # Исключить упражнения при травмах
    if profile.injuries:
        injuries_lower = profile.injuries.lower()
        injury_keywords = {
            'колен':    ['knee'],
            'спин':     ['back', 'spine'],
            'плеч':     ['shoulder'],
            'локот':    ['elbow'],
            'бедр':     ['hip'],
            'голеност': ['ankle'],
        }
        for rus_kw, eng_joints in injury_keywords.items():
            if rus_kw in injuries_lower:
                for joint in eng_joints:
                    qs = qs.exclude(joints_used__icontains=joint)
                    qs = qs.exclude(contraindications__icontains=joint)

    return qs


# ──────────────────────────────────────────────
#  СПЛИТ ПО ДНЯМ
# ──────────────────────────────────────────────

SPLIT_3_DAYS = [
    {'title': 'Грудь и трицепс',  'categories': ['chest', 'arms'],      'day_of_week': 0},
    {'title': 'Спина и бицепс',   'categories': ['back', 'arms'],       'day_of_week': 2},
    {'title': 'Ноги и плечи',     'categories': ['legs', 'shoulders'],  'day_of_week': 4},
]
SPLIT_4_DAYS = [
    {'title': 'Грудь',            'categories': ['chest'],              'day_of_week': 0},
    {'title': 'Спина',            'categories': ['back'],               'day_of_week': 1},
    {'title': 'Ноги',             'categories': ['legs', 'glutes'],     'day_of_week': 3},
    {'title': 'Плечи и руки',     'categories': ['shoulders', 'arms'],  'day_of_week': 4},
]
SPLIT_5_DAYS = [
    {'title': 'Грудь',            'categories': ['chest'],              'day_of_week': 0},
    {'title': 'Спина',            'categories': ['back'],               'day_of_week': 1},
    {'title': 'Ноги',             'categories': ['legs'],               'day_of_week': 2},
    {'title': 'Плечи',            'categories': ['shoulders'],          'day_of_week': 3},
    {'title': 'Руки и пресс',     'categories': ['arms', 'core'],      'day_of_week': 4},
]
SPLIT_FULL_BODY = [
    {'title': 'Всё тело A',       'categories': ['full_body', 'legs'],  'day_of_week': 0},
    {'title': 'Всё тело B',       'categories': ['full_body', 'core'],  'day_of_week': 2},
    {'title': 'Всё тело C',       'categories': ['full_body', 'cardio'],'day_of_week': 4},
]

def get_split(workouts_per_week):
    if workouts_per_week < 3:
        return SPLIT_FULL_BODY
    elif workouts_per_week == 3:
        return SPLIT_3_DAYS
    elif workouts_per_week == 4:
        return SPLIT_4_DAYS
    else:
        return SPLIT_5_DAYS


# ──────────────────────────────────────────────
#  GEMINI: ПЕРСОНАЛЬНЫЙ СОВЕТ К УПРАЖНЕНИЮ
# ──────────────────────────────────────────────

def generate_ai_tip_gemini(exercise, profile, goal) -> str:
    """
    Персональный совет через Gemini 1.5 Flash.
    Если Gemini недоступен — fallback на статичные тексты.

    Возвращает строку до ~120 слов.
    """
    try:
        model = _get_gemini_client()

        goal_labels = {
            'weight_loss': 'fat loss / weight loss',
            'muscle_gain': 'muscle building / hypertrophy',
            'maintenance': 'maintenance and general fitness',
            'endurance':   'cardiovascular endurance',
            'flexibility': 'flexibility and mobility',
        }

        prompt = (
            f"You are a professional personal trainer. Give ONE short, practical tip "
            f"(max 2 sentences, max 30 words) for the following exercise tailored to this user.\n\n"
            f"Exercise: {exercise.name}\n"
            f"Primary muscles: {exercise.primary_muscles or 'not specified'}\n"
            f"User goal: {goal_labels.get(goal, goal)}\n"
            f"User age: {profile.age}, weight: {profile.weight_kg} kg\n"
            f"Injuries/limitations: {profile.injuries or 'none'}\n\n"
            f"Reply ONLY with the tip text. No intro, no label, no quotes."
        )

        response = model.generate_content(prompt)
        tip = response.text.strip()

        # Обрезаем если слишком длинно
        if len(tip) > 300:
            tip = tip[:297] + '...'

        return tip

    except Exception as e:
        logger.warning(f"Gemini tip generation failed for exercise '{exercise.name}': {e}")
        return _fallback_tip(goal)


def _fallback_tip(goal: str) -> str:
    """Статичные советы если Gemini недоступен."""
    tips = {
        'weight_loss': [
            "Keep the tempo high and rest minimal to maximize calorie burn.",
            "Exhale on exertion — it helps engage your core.",
            "Control the movement; avoid momentum.",
        ],
        'muscle_gain': [
            "Progressive overload is key — add weight each week.",
            "Take the last set to failure for maximum growth stimulus.",
            "Slow the eccentric (lowering) phase to 3 seconds.",
        ],
        'maintenance': [
            "Keep a steady pace and focus on perfect form.",
            "Quality reps beat quantity every time.",
        ],
        'endurance': [
            "Maintain a pace you can sustain for the whole set.",
            "Breathe rhythmically — don't hold your breath.",
        ],
        'flexibility': [
            "Move into the stretch slowly; never bounce.",
            "Exhale as you deepen the stretch.",
        ],
    }
    return random.choice(tips.get(goal, tips['maintenance']))


# ──────────────────────────────────────────────
#  GEMINI: AI-ЗАМЕТКИ К ПЛАНУ (общие)
# ──────────────────────────────────────────────

def generate_plan_ai_notes_gemini(profile, influencer, rule) -> str:
    """
    Генерирует краткое вступление к программе тренировок.
    Показывается пользователю в начале плана.
    """
    try:
        model = _get_gemini_client()

        prompt = (
            f"You are a fitness coach. Write a short motivational introduction (3-4 sentences) "
            f"for a personalized workout plan. Mention the user's goal and any limitations.\n\n"
            f"Coach/brand: {influencer.brand_name}\n"
            f"User goal: {profile.get_goal_display()}\n"
            f"Age: {profile.age}, weight: {profile.weight_kg} kg, height: {profile.height_cm} cm\n"
            f"Equipment: {profile.get_available_equipment_display()}\n"
            f"Injuries: {profile.injuries or 'none'}\n"
            f"Workouts per week: {rule.workouts_per_week if rule else 3}\n\n"
            f"Reply ONLY with the introduction text. Keep it under 80 words."
        )

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        logger.warning(f"Gemini plan notes generation failed: {e}")
        influencer_name = influencer.brand_name
        goal_display = profile.get_goal_display()
        return (
            f"Персональная программа от {influencer_name} разработана специально для твоей цели: "
            f"{goal_display}. Следуй плану последовательно, не пропускай дни отдыха. "
            f"Прогрессируй постепенно — результаты придут!"
        )


# ──────────────────────────────────────────────
#  ОСНОВНАЯ ФУНКЦИЯ ГЕНЕРАЦИИ
# ──────────────────────────────────────────────

def generate_workout_plan(user, influencer, duration_weeks=8):
    """
    Главная функция: создаёт WorkoutPlan с WorkoutDay и WorkoutSet.

    Алгоритм:
    1. Загружаем профиль пользователя и правила инфлюенсера
    2. Фильтруем упражнения под пользователя
    3. Определяем сплит (3/4/5 дней)
    4. Для каждой недели создаём WorkoutDay + WorkoutSet
    5. Советы к упражнениям через Gemini (с fallback)
    6. Возвращаем готовый WorkoutPlan

    Возвращает: WorkoutPlan instance
    """
    profile = user.profile
    goal    = profile.goal

    # Правила инфлюенсера
    rule = influencer.rules.filter(goal=goal).first()
    if not rule:
        sets_count        = 3
        reps_count        = 12
        rest_seconds      = 60
        workouts_per_week = 3
    else:
        sets_count        = rule.sets_count
        reps_count        = rule.reps_count
        rest_seconds      = rule.rest_seconds
        workouts_per_week = rule.workouts_per_week

    # AI-заметки к плану через Gemini
    ai_notes_text = generate_plan_ai_notes_gemini(profile, influencer, rule)

    # Фильтруем упражнения
    all_exercises = filter_exercises_for_user(influencer, profile)
    exercises_by_category = {}
    for ex in all_exercises:
        if ex.category not in exercises_by_category:
            exercises_by_category[ex.category] = []
        exercises_by_category[ex.category].append(ex)

    # Сплит
    split = get_split(workouts_per_week)

    # Создаём план
    start = date.today()
    end   = start + timedelta(weeks=duration_weeks)

    plan = WorkoutPlan.objects.create(
        user           = user,
        influencer     = influencer,
        name           = f"{influencer.brand_name}: {_goal_name(goal)} — {duration_weeks} недель",
        duration_weeks = duration_weeks,
        ai_generated   = True,
        ai_notes       = ai_notes_text,
        start_date     = start,
        end_date       = end,
    )

    # Создаём дни для каждой недели
    for week in range(1, duration_weeks + 1):
        for day_template in split:
            day = WorkoutDay.objects.create(
                plan        = plan,
                week_number = week,
                day_of_week = day_template['day_of_week'],
                title       = day_template['title'],
                is_rest_day = False,
            )

            # Выбираем упражнения для дня
            day_exercises = []
            for category in day_template['categories']:
                available = exercises_by_category.get(category, [])
                if available:
                    picked = random.sample(available, min(3, len(available)))
                    day_exercises.extend(picked)

            if len(day_exercises) < 3:
                full_body = exercises_by_category.get('full_body', [])
                day_exercises.extend(random.sample(full_body, min(3, len(full_body))))

            day_exercises = day_exercises[:6]

            for order, exercise in enumerate(day_exercises, start=1):
                # Gemini tip только для первой недели — остальные недели копируют
                # (экономим API-вызовы; можно убрать условие для уникальных советов)
                if week == 1:
                    tip = generate_ai_tip_gemini(exercise, profile, goal)
                else:
                    tip = _fallback_tip(goal)

                WorkoutSet.objects.create(
                    workout_day  = day,
                    exercise     = exercise,
                    order        = order,
                    sets_count   = sets_count,
                    reps_count   = reps_count,
                    rest_seconds = rest_seconds,
                    ai_tip       = tip,
                )

        # День отдыха (воскресенье)
        WorkoutDay.objects.create(
            plan        = plan,
            week_number = week,
            day_of_week = 6,
            title       = 'День отдыха',
            is_rest_day = True,
        )

    return plan


# ──────────────────────────────────────────────
#  ХЕЛПЕРЫ
# ──────────────────────────────────────────────

def _goal_name(goal):
    names = {
        'weight_loss': 'Программа похудения',
        'muscle_gain': 'Программа набора массы',
        'maintenance': 'Программа поддержания',
        'endurance':   'Программа на выносливость',
        'flexibility': 'Программа на гибкость',
    }
    return names.get(goal, 'Фитнес-программа')