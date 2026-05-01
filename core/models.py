"""
RiseFit.ai — Django models.py
==============================
B2B2C платформа: AI-генерация фитнес-программ через инфлюенсеров
Стек: Django 4.x + PostgreSQL

Приложения:
  - users        → UserProfile, Subscription
  - influencers  → Influencer, InfluencerRule
  - workouts     → Exercise, WorkoutPlan, WorkoutDay, WorkoutSet
  - nutrition    → CalorieLog, NutritionGoal

Установи зависимости:
  pip install django djangorestframework djangorestframework-simplejwt psycopg2-binary pillow stripe
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


# ─────────────────────────────────────────────
#  БЛОК 1: ИНФЛЮЕНСЕРЫ (B2B часть)
# ─────────────────────────────────────────────

class Influencer(models.Model):
    """
    B2B: Фитнес-блогер/инфлюенсер.
    Имеет свой бренд, методологию тренировок и базу упражнений.
    Получает 50% от подписок своих пользователей.
    """

    NICHE_CHOICES = [
        ('weight_loss',   'Похудение'),
        ('muscle_gain',   'Набор массы'),
        ('calisthenics',  'Калистеника'),
        ('yoga',          'Йога'),
        ('hiit',          'HIIT'),
        ('powerlifting',  'Пауэрлифтинг'),
        ('general',       'Общий фитнес'),
    ]

    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name='influencer_profile')
    brand_name      = models.CharField(max_length=100, unique=True, help_text='Название бренда, напр. "FitByMike"')
    slug            = models.SlugField(max_length=100, unique=True, help_text='URL-идентификатор, напр. fitbymike')
    niche           = models.CharField(max_length=30, choices=NICHE_CHOICES, default='general')
    bio             = models.TextField(blank=True)
    profile_photo   = models.ImageField(upload_to='influencers/photos/', blank=True, null=True)
    methodology     = models.TextField(help_text='Описание философии тренировок инфлюенсера')
    revenue_share   = models.DecimalField(max_digits=5, decimal_places=2, default=50.00,
                                          help_text='Процент дохода инфлюенсера (обычно 50%)')
    stripe_account_id = models.CharField(max_length=100, blank=True,
                                         help_text='Stripe Connect ID для выплат')
    is_active       = models.BooleanField(default=True)
    subscribers_count = models.PositiveIntegerField(default=0, help_text='Кэш: кол-во активных подписчиков')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Инфлюенсер'
        verbose_name_plural = 'Инфлюенсеры'
        ordering            = ['-subscribers_count']

    def __str__(self):
        return f"{self.brand_name} (@{self.user.username})"

    @property
    def monthly_revenue(self):
        """Примерный месячный доход инфлюенсера (50% от подписок)."""
        active_subs = self.subscriptions.filter(status='active').count()
        return active_subs * 15 * (self.revenue_share / 100)


class InfluencerRule(models.Model):
    """
    B2B: Правила генерации программ от инфлюенсера.
    Инфлюенсер задаёт логику: если цель — масса, то 4 подхода и т.д.
    AI модуль использует эти правила при генерации плана.
    """

    GOAL_CHOICES = [
        ('weight_loss',  'Похудение'),
        ('muscle_gain',  'Набор массы'),
        ('maintenance',  'Поддержание формы'),
        ('endurance',    'Выносливость'),
        ('flexibility',  'Гибкость'),
    ]

    influencer      = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name='rules')
    goal            = models.CharField(max_length=30, choices=GOAL_CHOICES)
    sets_count      = models.PositiveSmallIntegerField(default=3, help_text='Кол-во подходов')
    reps_count      = models.PositiveSmallIntegerField(default=12, help_text='Кол-во повторений')
    rest_seconds    = models.PositiveSmallIntegerField(default=60, help_text='Отдых между подходами (сек)')
    workouts_per_week = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(7)])
    intensity_notes = models.TextField(blank=True, help_text='Дополнительные инструкции для AI')

    class Meta:
        verbose_name        = 'Правило инфлюенсера'
        verbose_name_plural = 'Правила инфлюенсеров'
        unique_together     = ('influencer', 'goal')

    def __str__(self):
        return f"{self.influencer.brand_name} → {self.get_goal_display()}"


# ─────────────────────────────────────────────
#  БЛОК 2: ПОЛЬЗОВАТЕЛИ (B2C часть)
# ─────────────────────────────────────────────

class UserProfile(models.Model):
    """
    B2C: Профиль пользователя приложения.
    Хранит физические параметры, цели и ограничения.
    AI модуль использует эти данные для генерации персональной программы.
    """

    GOAL_CHOICES = [
        ('weight_loss',  'Похудение'),
        ('muscle_gain',  'Набор массы'),
        ('maintenance',  'Поддержание формы'),
        ('endurance',    'Выносливость'),
        ('flexibility',  'Гибкость'),
    ]

    GENDER_CHOICES = [
        ('male',   'Мужской'),
        ('female', 'Женский'),
        ('other',  'Другой'),
    ]

    ACTIVITY_CHOICES = [
        ('sedentary',    'Сидячий образ жизни'),
        ('light',        'Лёгкая активность (1-3 дня/нед)'),
        ('moderate',     'Умеренная (3-5 дней/нед)'),
        ('active',       'Высокая (6-7 дней/нед)'),
        ('very_active',  'Очень высокая (проф. спорт)'),
    ]

    EQUIPMENT_CHOICES = [
        ('none',        'Без оборудования'),
        ('dumbbells',   'Гантели'),
        ('barbell',     'Штанга'),
        ('gym',         'Полноценный зал'),
        ('resistance',  'Эспандеры'),
        ('home_gym',    'Домашний зал'),
    ]

    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    influencer      = models.ForeignKey(Influencer, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='followers', help_text='К какому инфлюенсеру привязан пользователь')

    # Физические параметры
    gender          = models.CharField(max_length=10, choices=GENDER_CHOICES, default='male')
    age             = models.PositiveSmallIntegerField(validators=[MinValueValidator(14), MaxValueValidator(100)])
    weight_kg       = models.DecimalField(max_digits=5, decimal_places=1,
                                          validators=[MinValueValidator(30), MaxValueValidator(300)])
    height_cm       = models.PositiveSmallIntegerField(validators=[MinValueValidator(100), MaxValueValidator(250)])
    body_fat_percent = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    # Цели и активность
    goal            = models.CharField(max_length=30, choices=GOAL_CHOICES, default='maintenance')
    activity_level  = models.CharField(max_length=20, choices=ACTIVITY_CHOICES, default='moderate')
    target_weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    # Оборудование и ограничения
    available_equipment = models.CharField(max_length=20, choices=EQUIPMENT_CHOICES, default='none')
    injuries        = models.TextField(blank=True, help_text='Описание травм/ограничений для AI, напр. "боль в правом колене"')
    health_notes    = models.TextField(blank=True, help_text='Доп. заметки о здоровье')

    # Кэшированные расчёты (обновляются при изменении профиля)
    bmr             = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True,
                                          help_text='Базальный метаболизм (Mifflin-St Jeor), ккал')
    tdee            = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True,
                                          help_text='Общий расход энергии, ккал')
    daily_calorie_goal = models.PositiveIntegerField(null=True, blank=True,
                                                     help_text='Целевое потребление калорий/день')

    avatar          = models.ImageField(upload_to='users/avatars/', blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f"{self.user.username} | {self.get_goal_display()} | {self.weight_kg}кг"

    @property
    def bmi(self):
        """Индекс массы тела."""
        if self.height_cm and self.weight_kg:
            h = float(self.height_cm) / 100
            return round(float(self.weight_kg) / (h * h), 1)
        return None

    def calculate_bmr(self):
        """
        Формула Mifflin-St Jeor:
          Мужчины: 10*вес + 6.25*рост - 5*возраст + 5
          Женщины: 10*вес + 6.25*рост - 5*возраст - 161
        Возвращает BMR в ккал/день.
        """
        w = float(self.weight_kg)
        h = float(self.height_cm)
        a = self.age
        if self.gender == 'male':
            return round(10 * w + 6.25 * h - 5 * a + 5, 1)
        elif self.gender == 'female':
            return round(10 * w + 6.25 * h - 5 * a - 161, 1)
        else:
            # Среднее для "other"
            male   = 10 * w + 6.25 * h - 5 * a + 5
            female = 10 * w + 6.25 * h - 5 * a - 161
            return round((male + female) / 2, 1)

    def calculate_tdee(self):
        """TDEE = BMR × коэффициент активности."""
        ACTIVITY_MULTIPLIERS = {
            'sedentary':   1.2,
            'light':       1.375,
            'moderate':    1.55,
            'active':      1.725,
            'very_active': 1.9,
        }
        bmr = self.calculate_bmr()
        multiplier = ACTIVITY_MULTIPLIERS.get(self.activity_level, 1.55)
        return round(bmr * multiplier, 1)

    def save(self, *args, **kwargs):
        """Автоматически пересчитывает BMR и TDEE при сохранении профиля."""
        self.bmr  = self.calculate_bmr()
        self.tdee = self.calculate_tdee()

        # Целевые калории: дефицит -500 для похудения, профицит +300 для массы
        tdee = float(self.tdee)
        if self.goal == 'weight_loss':
            self.daily_calorie_goal = int(tdee - 500)
        elif self.goal == 'muscle_gain':
            self.daily_calorie_goal = int(tdee + 300)
        else:
            self.daily_calorie_goal = int(tdee)

        super().save(*args, **kwargs)


class Subscription(models.Model):
    """
    B2C: Подписка пользователя ($15/месяц).
    Привязана к конкретному инфлюенсеру.
    Stripe обрабатывает платёж, мы храним статус.
    """

    STATUS_CHOICES = [
        ('active',    'Активна'),
        ('cancelled', 'Отменена'),
        ('expired',   'Истекла'),
        ('trialing',  'Пробный период'),
        ('past_due',  'Просрочена'),
    ]

    id                      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user                    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    influencer              = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name='subscriptions')
    status                  = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trialing')
    price_usd               = models.DecimalField(max_digits=6, decimal_places=2, default=15.00)
    stripe_subscription_id  = models.CharField(max_length=100, unique=True, blank=True, null=True)
    stripe_customer_id      = models.CharField(max_length=100, blank=True, null=True)
    started_at              = models.DateTimeField(auto_now_add=True)
    expires_at              = models.DateTimeField(null=True, blank=True)
    cancelled_at            = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Подписка'
        verbose_name_plural = 'Подписки'
        ordering            = ['-started_at']

    def __str__(self):
        return f"{self.user.username} → {self.influencer.brand_name} [{self.get_status_display()}]"

    @property
    def is_active(self):
        return self.status in ('active', 'trialing')


# ─────────────────────────────────────────────
#  БЛОК 3: УПРАЖНЕНИЯ И ТРЕНИРОВКИ
# ─────────────────────────────────────────────

class Exercise(models.Model):
    """
    Библиотека упражнений инфлюенсера.
    Каждый блогер загружает свои видео — это его контент.
    AI выбирает упражнения из этой базы при генерации программы.
    """

    CATEGORY_CHOICES = [
        ('chest',     'Грудь'),
        ('back',      'Спина'),
        ('legs',      'Ноги'),
        ('shoulders', 'Плечи'),
        ('arms',      'Руки'),
        ('core',      'Пресс/Кор'),
        ('glutes',    'Ягодицы'),
        ('cardio',    'Кардио'),
        ('full_body', 'Всё тело'),
        ('mobility',  'Мобильность'),
    ]

    DIFFICULTY_CHOICES = [
        ('beginner',      'Новичок'),
        ('intermediate',  'Средний'),
        ('advanced',      'Продвинутый'),
    ]

    EQUIPMENT_REQUIRED_CHOICES = [
        ('none',        'Без оборудования'),
        ('dumbbells',   'Гантели'),
        ('barbell',     'Штанга'),
        ('gym',         'Тренажёр'),
        ('resistance',  'Эспандер'),
        ('any',         'Любое'),
    ]

    influencer          = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name='exercises')
    name                = models.CharField(max_length=150)
    description         = models.TextField(blank=True)
    category            = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    difficulty          = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='beginner')
    equipment_required  = models.CharField(max_length=20, choices=EQUIPMENT_REQUIRED_CHOICES, default='none')
    video_url           = models.URLField(help_text='Ссылка на видео упражнения (YouTube, S3 и т.д.)')
    thumbnail_url       = models.URLField(blank=True, help_text='Превью видео')
    duration_seconds    = models.PositiveSmallIntegerField(null=True, blank=True,
                                                           help_text='Длительность видео в секундах')
    # Мышцы (для AI фильтрации при травмах)
    primary_muscles     = models.CharField(max_length=200, blank=True,
                                           help_text='Основные мышцы через запятую, напр. "квадрицепсы,ягодицы"')
    secondary_muscles   = models.CharField(max_length=200, blank=True)
    joints_used         = models.CharField(max_length=200, blank=True,
                                           help_text='Задействованные суставы, напр. "колено,бедро"')
    # Для фильтрации при травмах
    contraindications   = models.TextField(blank=True,
                                           help_text='Кому нельзя: "травма колена, беременность" и т.д.')
    calories_per_minute = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                              help_text='Примерный расход калорий/мин')
    is_active           = models.BooleanField(default=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Упражнение'
        verbose_name_plural = 'Упражнения'
        ordering            = ['category', 'name']

    def __str__(self):
        return f"[{self.influencer.brand_name}] {self.name} ({self.get_category_display()})"


class WorkoutPlan(models.Model):
    """
    AI-сгенерированная программа тренировок для конкретного пользователя.
    Создаётся AI модулем на основе профиля пользователя и правил инфлюенсера.
    Пересоздаётся при изменении профиля или по запросу пользователя.
    """

    STATUS_CHOICES = [
        ('active',    'Активная'),
        ('completed', 'Завершена'),
        ('archived',  'В архиве'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workout_plans')
    influencer      = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name='plans')
    name            = models.CharField(max_length=200, help_text='Напр. "8-недельная программа похудения"')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    duration_weeks  = models.PositiveSmallIntegerField(default=8)
    ai_generated    = models.BooleanField(default=True, help_text='True = создано AI, False = ручное')
    ai_prompt_used  = models.TextField(blank=True, help_text='Промпт, который был отправлен в OpenAI')
    ai_notes        = models.TextField(blank=True, help_text='Пояснения AI к программе')
    start_date      = models.DateField()
    end_date        = models.DateField()
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Программа тренировок'
        verbose_name_plural = 'Программы тренировок'
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.name}"

    @property
    def total_days(self):
        return self.workout_days.count()

    @property
    def completed_days(self):
        return self.workout_days.filter(is_completed=True).count()

    @property
    def progress_percent(self):
        total = self.total_days
        return round((self.completed_days / total) * 100, 1) if total > 0 else 0


class WorkoutDay(models.Model):
    """
    Один день тренировочного плана.
    Содержит список упражнений (через WorkoutSet).
    """

    WEEKDAY_CHOICES = [
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье'),
    ]

    plan            = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name='workout_days')
    week_number     = models.PositiveSmallIntegerField(default=1, help_text='Номер недели в программе')
    day_of_week     = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    title           = models.CharField(max_length=150, help_text='Напр. "День груди и трицепса"')
    is_rest_day     = models.BooleanField(default=False, help_text='Если True — день отдыха, упражнений нет')
    is_completed    = models.BooleanField(default=False)
    completed_at    = models.DateTimeField(null=True, blank=True)
    notes           = models.TextField(blank=True, help_text='Заметки пользователя после тренировки')

    class Meta:
        verbose_name        = 'День тренировки'
        verbose_name_plural = 'Дни тренировок'
        ordering            = ['week_number', 'day_of_week']

    def __str__(self):
        return f"Неделя {self.week_number} / {self.get_day_of_week_display()} — {self.title}"


class WorkoutSet(models.Model):
    """
    Конкретное упражнение в дне тренировки.
    Хранит подходы, повторения и вес (если применимо).
    """

    workout_day     = models.ForeignKey(WorkoutDay, on_delete=models.CASCADE, related_name='sets')
    exercise        = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name='workout_sets')
    order           = models.PositiveSmallIntegerField(default=1, help_text='Порядковый номер упражнения в тренировке')
    sets_count      = models.PositiveSmallIntegerField(default=3)
    reps_count      = models.PositiveSmallIntegerField(null=True, blank=True,
                                                       help_text='Повторения (null для временных упражнений)')
    duration_seconds = models.PositiveSmallIntegerField(null=True, blank=True,
                                                        help_text='Длительность (для планки, кардио)')
    rest_seconds    = models.PositiveSmallIntegerField(default=60)
    weight_kg       = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True,
                                          help_text='Рекомендуемый вес (если применимо)')
    ai_tip          = models.CharField(max_length=300, blank=True,
                                       help_text='Персональный совет AI для этого упражнения')
    # Факт выполнения
    is_completed    = models.BooleanField(default=False)
    actual_sets     = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Реально выполнено подходов')
    actual_reps     = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Реально выполнено повторений')
    actual_weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    class Meta:
        verbose_name        = 'Упражнение в тренировке'
        verbose_name_plural = 'Упражнения в тренировках'
        ordering            = ['order']

    def __str__(self):
        return f"{self.exercise.name} × {self.sets_count}×{self.reps_count}"


# ─────────────────────────────────────────────
#  БЛОК 4: ПИТАНИЕ И КАЛОРИИ
# ─────────────────────────────────────────────

class NutritionGoal(models.Model):
    """
    Цели по питанию пользователя (КБЖУ).
    Рассчитываются AI на основе профиля и цели.
    """

    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name='nutrition_goal')
    calories        = models.PositiveIntegerField(help_text='Целевые калории/день')
    protein_g       = models.PositiveSmallIntegerField(help_text='Белки, г/день')
    carbs_g         = models.PositiveSmallIntegerField(help_text='Углеводы, г/день')
    fat_g           = models.PositiveSmallIntegerField(help_text='Жиры, г/день')
    water_ml        = models.PositiveSmallIntegerField(default=2000, help_text='Вода, мл/день')
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Цель по питанию'
        verbose_name_plural = 'Цели по питанию'

    def __str__(self):
        return f"{self.user.username}: {self.calories} ккал | Б{self.protein_g}/У{self.carbs_g}/Ж{self.fat_g}"


class CalorieLog(models.Model):
    """
    Дневник питания пользователя.
    Пользователь записывает что съел, мы считаем КБЖУ.
    """

    MEAL_TYPE_CHOICES = [
        ('breakfast', 'Завтрак'),
        ('lunch',     'Обед'),
        ('dinner',    'Ужин'),
        ('snack',     'Перекус'),
    ]

    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calorie_logs')
    date            = models.DateField()
    meal_type       = models.CharField(max_length=15, choices=MEAL_TYPE_CHOICES)
    food_name       = models.CharField(max_length=200, help_text='Название продукта/блюда')
    amount_grams    = models.PositiveSmallIntegerField(help_text='Количество в граммах')
    calories        = models.PositiveSmallIntegerField(help_text='Калории этой порции')
    protein_g       = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    carbs_g         = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    fat_g           = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    notes           = models.CharField(max_length=300, blank=True)
    logged_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Запись в дневнике питания'
        verbose_name_plural = 'Записи в дневнике питания'
        ordering            = ['-date', 'meal_type']

    def __str__(self):
        return f"{self.user.username} | {self.date} | {self.meal_type}: {self.food_name} ({self.calories} ккал)"


# ─────────────────────────────────────────────
#  БЛОК 5: АНАЛИТИКА И ПРОГРЕСС
# ─────────────────────────────────────────────

class ProgressEntry(models.Model):
    """
    Запись прогресса пользователя (замеры тела).
    Используется для графиков в приложении и мотивации.
    """

    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress_entries')
    date            = models.DateField()
    weight_kg       = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    body_fat_percent = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    chest_cm        = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    waist_cm        = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    hips_cm         = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    bicep_cm        = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    photo           = models.ImageField(upload_to='progress/photos/', blank=True, null=True,
                                        help_text='Фото прогресса (опционально)')
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Запись прогресса'
        verbose_name_plural = 'Записи прогресса'
        ordering            = ['-date']
        unique_together     = ('user', 'date')

    def __str__(self):
        return f"{self.user.username} | {self.date} | {self.weight_kg}кг"