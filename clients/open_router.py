"""OpenRouter клиент для AI запросов"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import httpx

from settings.config import AppConfig

logger = logging.getLogger(__name__)


# AI Prompts for Report Generation
DAILY_REPORT_PROMPT = """Ты — аналитик по питанию. Сгенерируй краткий дневной отчёт на русском языке.

ВАЖНО: Отчёт будет отправлен пользователю в Telegram сообщением.

СТРУКТУРА ОТВЕТА (ОБЯЗАТЕЛЬНАЯ):
ВАЖНО: Между каждым разделом должна быть ПУСТАЯ СТРОКА (\n\n) для читаемости!

1. Приветствие: "Ваш {period_ru} отчёт готов!"

2. СТАТИСТИКА С ЦЕЛЯМИ (КОМПАКТНЫЙ ФОРМАТ с эмодзи):
   🔥 Калории: [факт] ккал (цель [цель] ккал, выполнение [X]%)
   💪 Белки: [факт]г (цель [цель]г, выполнение [X]%)
   🥑 Жиры: [факт]г (цель [цель]г, выполнение [X]%)
   🍞 Углеводы: [факт]г (цель [цель]г, выполнение [X]%)
   🌾 Клетчатка: [факт]г (цель [цель]г, выполнение [X]%)
   💧 Жидкость: [факт]мл (цель [цель]мл, выполнение [X]%)

   После всех показателей добавь ПУСТУЮ СТРОКУ, затем ОДИН общий комментарий (2-3 предложения) по выполнению целей с учетом цели пользователя (похудеть/набрать/поддержать вес)
   Если целей у пользователя нет то выводи просто статистику
3. ИНТЕРЕСНЫЕ ДЕТАЛИ (что конкретно ел: выдели необычные продукты, большие объемы конкретных продуктов с комментариями)
4. КРАТКИЙ ВЫВОД (1-2 наблюдения о качестве питания с учетом цели пользователя)

КРИТИЧЕСКИ ВАЖНЫЕ ИНСТРУКЦИИ:
- Пиши на русском языке, дружелюбным тоном
- ОБЯЗАТЕЛЬНО разделяй текст пустыми строкам между разделами - НЕ делай сплошной текст! Добавляй одну пустую строку между абазацами и разделами
- Используй эмодзи для нутриентов (🔥💪🥑🍞🌾💧) и разрешенные эмоциональные эмодзи
- Это ВСЕГО ОДИН ДЕНЬ - НЕ делай долгосрочных выводов или больших рекомендаций
- Ты НЕ врач - НЕ ставь диагнозы и НЕ назначай лечение
- Основывайся на научных данных о питании
- Будь осторожен с рекомендациями - предлагай мягкие корректировки, не радикальные изменения
- Оцени компоненты на предмет содержания витаминов/минералов (например: много овощей = хорошие витамины)
- ОБЯЗАТЕЛЬНО учитывай цель пользователя (похудеть/набрать/поддержать вес) при оценке выполнения целей
- Анализируй конкретные продукты и их количество - давай интересные факты и комментарии
- Не озаглавливай разделы СТАТИСТИКА С ЦЕЛЯМИ, ИНТЕРЕСНЫЕ ДЕТАЛИ РАЦИОНА  и так далее. Сразу пиши по сути этого раздела
- Максимум 250 слов
- В конце проверь текст. Он должен выглядеть цельно и один абзац плавно перетекать в другой

ФОРМАТИРОВАНИЕ И ЧИТАЕМОСТЬ (КРИТИЧЕСКИ ВАЖНО):
ВАЖНО: Отчет должен быть МАКСИМАЛЬНО ЧИТАЕМЫМ в Telegram!
- Каждый раздел отчета должен быть четко отделен от других
- Используй эмодзи для визуального разделения и улучшения читаемости
- Текст должен легко сканироваться глазами

ЭМОДЗИ ДЛЯ НУТРИЕНТОВ (ОБЯЗАТЕЛЬНО используй их в статистике):
- 🔥 - Калории
- 💪 - Белки
- 🥑 - Жиры
- 🍞 - Углеводы
- 🌾 - Клетчатка
- 💧 - Жидкость
- ⚖️ - Вес

РАЗРЕШЕННЫЕ ЭМОДЗИ ДЛЯ ЭМОЦИЙ (можешь использовать ТОЛЬКО эти):
😀, 😲, 😳, 😉, 😋, 👍, 👎, ✊, 🙏, 👏, 🙌

ЗАПРЕЩЕНО использовать любые другие эмодзи!

ФОРМАТ HTML-РАЗМЕТКИ:
ВАЖНО: Используй ТОЛЬКО следующие HTML теги:
- <b>жирный текст</b> или <strong>жирный текст</strong>
- <i>курсив</i> или <em>курсив</em>
- <u>подчёркнутый</u>

ЗАПРЕЩЕНО использовать: <h1>, <h2>, <h3>, <h4>, <h5>, <h6>, <p>, <div>, <span>, <br>, <hr> и любые другие теги!
Если нужно разделить абзацы - используй двойной перенос строки (\n\n)

ДАННЫЕ О ПОЛЬЗОВАТЕЛЕ:
{user_profile}

ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ (на основе данных профиля и целей):
{user_goal_type}

ДАННЫЕ О ПИТАНИИ ЗА ПЕРИОД:
Период: {start_date} до {end_date}
Дней с данными: {days_count}

Цели пользователя (могут отсутствовать):{user_goals}

Сводная статистика (саммари за период):
{summary}

Что пользователь ел по дням:
{daily_components}
"""

WEEKLY_MONTHLY_REPORT_PROMPT = """Ты — аналитик по питанию. Сгенерируй подробный {period_ru} отчёт на русском языке.

ВАЖНО: Отчёт будет отправлен пользователю в Telegram сообщением.

СТРУКТУРА ОТВЕТА (ОБЯЗАТЕЛЬНАЯ):

1. Приветствие: "Ваш {period_ru} отчёт готов!"

2. СТАТИСТИКА С ЦЕЛЯМИ (КОМПАКТНЫЙ ФОРМАТ с эмодзи):
   🔥 Калории: [факт] ккал/день (цель [цель] ккал, выполнение [X]%)
   💪 Белки: [факт]г/день (цель [цель]г, выполнение [X]%)
   🥑 Жиры: [факт]г/день (цель [цель]г, выполнение [X]%)
   🍞 Углеводы: [факт]г/день (цель [цель]г, выполнение [X]%)
   🌾 Клетчатка: [факт]г/день (цель [цель]г, выполнение [X]%)
   💧 Жидкость: [факт]мл/день (цель [цель]мл, выполнение [X]%)

   После всех показателей добавь ПУСТУЮ СТРОКУ, затем ОДИН общий комментарий (2-3 предложения) по выполнению целей с учетом цели пользователя (похудеть/набрать/поддержать вес)
   Если целей у пользователя нет то выводи просто статистику
3. ИНТЕРЕСНЫЕ ДЕТАЛИ РАЦИОНА (анализ конкретных продуктов: что ел чаще всего, необычные продукты, большие объемы конкретных продуктов - давай интересные факты и комментарии о пользе/вреде)
4. АНАЛИЗ ПАТТЕРНОВ (ищи тренды по дням: постоянство питания, разнообразие продуктов, баланс по дням)
5. ИНСАЙТЫ (2-4 наблюдения на основе научных данных о качестве питания, достаточности витаминов/минералов на основе компонентов)
6. РЕКОМЕНДАЦИИ (1-2 мягких, выполнимых совета с учетом цели пользователя - НЕ медицинские назначения)

КРИТИЧЕСКИ ВАЖНЫЕ ИНСТРУКЦИИ:
- Пиши на русском языке, профессиональным но дружелюбным тоном
- ОБЯЗАТЕЛЬНО разделяй текст пустыми строкам между разделами - НЕ делай сплошной текст! Добавляй одну пустую строку между абазацами и разделами
- Используй эмодзи для нутриентов (🔥💪🥑🍞🌾💧) и разрешенные эмоциональные эмодзи
- Ты НЕ врач - НЕ ставь диагнозы, НЕ назначай лечение, НЕ давай медицинских советов
- Ты можешь только анализировать данные о питании и давать общие инсайты
- Основывай все инсайты на научных исследованиях в области питания
- При предложении изменений используй мягкие формулировки: "можно попробовать", "стоит рассмотреть", НЕ "вам необходимо"
- ОБЯЗАТЕЛЬНО учитывай цель пользователя (похудеть/набрать/поддержать вес) при оценке выполнения целей и рекомендациях
- Анализируй компоненты на предмет содержания микронутриентов и разнообразия продуктов
- Оцени компоненты на микронутриенты: овощи→витамины, молочное→кальций, мясо→B12 и т.д.
- ОБЯЗАТЕЛЬНО анализируй конкретные продукты и их объемы - давай интересные факты (например: "Вы съели 1кг тунца за неделю - отличный источник омега-3 и белка!")
- Ищи паттерны: постоянство приёмов пищи, разнообразие продуктов, баланс по дням
- Если данных мало (несколько дней), упомяни ограничения анализа
- Не озаглавливай разделы СТАТИСТИКА С ЦЕЛЯМИ, ИНТЕРЕСНЫЕ ДЕТАЛИ РАЦИОНА  и так далее. Сразу пиши по сути этого раздела
- В конце проверь текст. Он должен выглядеть цельно и один абзац плавно перетекать в другой
- Максимум 700 слов


ФОРМАТИРОВАНИЕ И ЧИТАЕМОСТЬ (КРИТИЧЕСКИ ВАЖНО):
ВАЖНО: Отчет должен быть МАКСИМАЛЬНО ЧИТАЕМЫМ в Telegram!
- Каждый раздел отчета должен быть четко отделен от других
- Используй эмодзи для визуального разделения и улучшения читаемости
- Текст должен легко сканироваться глазами

ЭМОДЗИ ДЛЯ НУТРИЕНТОВ (ОБЯЗАТЕЛЬНО используй их в статистике):
- 🔥 - Калории
- 💪 - Белки
- 🥑 - Жиры
- 🍞 - Углеводы
- 🌾 - Клетчатка
- 💧 - Жидкость
- ⚖️ - Вес

РАЗРЕШЕННЫЕ ЭМОДЗИ ДЛЯ ЭМОЦИЙ (можешь использовать ТОЛЬКО эти):
😀, 😲, 😳, 😉, 😋, 👍, 👎, ✊, 🙏, 👏, 🙌

ЗАПРЕЩЕНО использовать любые другие эмодзи!

ФОРМАТ HTML-РАЗМЕТКИ:
ВАЖНО: Используй ТОЛЬКО следующие HTML теги:
- <b>жирный текст</b> или <strong>жирный текст</strong>
- <i>курсив</i> или <em>курсив</em>
- <u>подчёркнутый</u>

ЗАПРЕЩЕНО использовать: <h1>, <h2>, <h3>, <h4>, <h5>, <h6>, <p>, <div>, <span>, <br>, <hr> и любые другие теги!
Если нужно разделить абзацы - используй двойной перенос строки (\n\n)

ДАННЫЕ О ПОЛЬЗОВАТЕЛЕ:
{user_profile}

ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ (на основе данных профиля и целей):
{user_goal_type}

ДАННЫЕ О ПИТАНИИ ЗА ПЕРИОД:
Период: {start_date} до {end_date}
Дней с данными: {days_count}

Цели пользователя (могут отсутствовать):
{user_goals}

Сводная статистика (саммари за период):
{summary}

Что пользователь ел по дням:
{daily_components}
"""


class OpenRouterClient:
    """Клиент для OpenRouter API с поддержкой fallback моделей"""

    # Fallback модели - попробуем по порядку если основная не сработала
    FALLBACK_MODELS = [
        "google/gemini-2.5-flash",
        "google/gemini-2.5-flash-lite",
        "google/gemini-2.0-flash-001",
    ]

    BASE_TIMEOUT = 5.0  # Базовый таймаут в секундах
    TIMEOUT_INCREMENT = 5.0  # Прибавка к таймауту для каждой следующей модели

    def __init__(self):
        self.api_key = AppConfig.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1"
        self.primary_model = AppConfig.OPENROUTER_MODEL

        if not self.api_key:
            logger.warning("OpenRouter API key not configured")

    def _get_models_to_try(self) -> list[str]:
        """Возвращает список моделей для попытки: [primary_model] + fallback_models"""
        models = [self.primary_model] if self.primary_model else []
        models.extend([m for m in self.FALLBACK_MODELS if m not in models])
        return models

    def _get_timeout_for_attempt(self, attempt: int) -> float:
        """Возвращает таймаут для N-ой попытки (начиная с 0)"""
        return self.BASE_TIMEOUT + (attempt * self.TIMEOUT_INCREMENT)

    async def _make_request_with_fallback(
        self,
        payload_builder,
        max_tokens: int = 500,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        Выполняет запрос к OpenRouter с поддержкой fallback моделей

        Args:
            payload_builder: функция (model, max_tokens, temperature) -> payload
            max_tokens: максимальное количество токенов
            temperature: температура генерации

        Returns:
            Dict с распарсенными данными о питании

        Raises:
            Exception: если ни одна модель не смогла обработать запрос
        """
        models_to_try = self._get_models_to_try()
        last_error = None

        for attempt, model in enumerate(models_to_try):
            timeout = self._get_timeout_for_attempt(attempt)

            try:
                logger.debug(f"Trying model {model} (attempt {attempt + 1}/{len(models_to_try)}, timeout={timeout}s)")

                payload = payload_builder(model, max_tokens, temperature)

                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://gepvi_reports.com",
                            "X-Title": "GepviReports"
                        },
                        json=payload
                    )

                    response.raise_for_status()
                    result = response.json()
                    ai_response = result["choices"][0]["message"]["content"].strip()

                    logger.info(f"Model {model} succeeded")
                    return result

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(f"HTTP error with model {model}: {e.response.status_code} - {e}")
                if attempt < len(models_to_try) - 1:
                    continue

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error with model {model}: {e}")
                if attempt < len(models_to_try) - 1:
                    continue

        # Если ни одна модель не сработала - бросаем исключение
        error_msg = f"All models failed. Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)

    def _format_components_compact(self, daily_components: list) -> str:
        """Format daily components in compact, readable format"""
        if not daily_components:
            return "Нет данных о компонентах"

        result = []
        for day_data in daily_components:
            date = day_data.get("date", "Неизвестная дата")
            components = day_data.get("components", [])

            result.append(f"\n📅 {date}:")
            for comp in components:
                name = comp.get("name", "Неизвестно")
                weight = comp.get("W")
                liquid = comp.get("L")
                comp_line = f'  • {name}:'
                if weight:
                    comp_line += f" {weight}г"
                if liquid:
                    comp_line += f" {liquid}мл"
                result.append(comp_line)

        return "\n".join(result)

    def _format_user_goals(self, user_goals: dict) -> str:
        """Format user goals in readable format"""
        if not user_goals:
            return "Цели не установлены"

        goals = []
        if "calories" in user_goals:
            goals.append(f"Калории: {user_goals['calories']} ккал/день")
        if "protein" in user_goals:
            goals.append(f"Белки: {user_goals['protein']}г/день")
        if "fats" in user_goals:
            goals.append(f"Жиры: {user_goals['fats']}г/день")
        if "carbs" in user_goals:
            goals.append(f"Углеводы: {user_goals['carbs']}г/день")
        if "fiber" in user_goals:
            goals.append(f"Клетчатка: {user_goals['fiber']}г/день")
        if "liquid" in user_goals:
            goals.append(f"Жидкость: {user_goals['liquid']}мл/день")

        return "\n".join(goals) if goals else "Цели не установлены"

    def _format_summary(self, summary: dict) -> str:
        """Format summary statistics in readable format"""
        if not summary:
            return "Нет статистики"

        lines = []

        # Main stats
        if "total_calories" in summary:
            lines.append(f"Всего калорий: {summary['total_calories']} ккал")
        if "average_per_day" in summary:
            lines.append(f"Среднее в день: {summary['average_per_day']:.1f} ккал")
        if "meals_count" in summary:
            lines.append(f"Всего приёмов пищи: {summary['meals_count']}")

        # Macronutrients
        macros = summary.get("macronutrients", {})
        if macros:
            lines.append("\nМакронутриенты:")
            if "total_protein" in macros:
                lines.append(f"  Белки: {macros['total_protein']}г ({macros.get('protein_percent', 0)}%)")
            if "total_fats" in macros:
                lines.append(f"  Жиры: {macros['total_fats']}г ({macros.get('fats_percent', 0)}%)")
            if "total_carbs" in macros:
                lines.append(f"  Углеводы: {macros['total_carbs']}г ({macros.get('carbs_percent', 0)}%)")
            if "total_fiber" in macros:
                lines.append(f"  Клетчатка: {macros['total_fiber']}г")
            if "total_liquid" in macros:
                lines.append(f"  Жидкость: {macros['total_liquid']}мл")

        # Breakdown by meal type
        breakdown = summary.get("breakdown_by_type", {})
        if breakdown:
            lines.append("\nПо типам приёмов пищи:")
            meal_names = {
                "breakfast": "Завтраки",
                "lunch": "Обеды",
                "dinner": "Ужины",
                "snack": "Перекусы"
            }
            for meal_type, meal_name in meal_names.items():
                if meal_type in breakdown:
                    meal_data = breakdown[meal_type]
                    meal_line = f"  {meal_name}: {meal_data.get('calories', 0)} ккал"

                    # Add macros if available
                    macros_parts = []
                    if "protein" in meal_data:
                        macros_parts.append(f"Б: {meal_data['protein']}г")
                    if "fats" in meal_data:
                        macros_parts.append(f"Ж: {meal_data['fats']}г")
                    if "carbs" in meal_data:
                        macros_parts.append(f"У: {meal_data['carbs']}г")

                    if macros_parts:
                        meal_line += f" ({', '.join(macros_parts)})"

                    lines.append(meal_line)

        return "\n".join(lines)

    def _format_user_profile(self, user_info: dict) -> str:
        """Format user profile data in readable format"""
        if not user_info:
            return "Данные профиля не заполнены. Рекомендуем заполнить профиль для более точного анализа."

        lines = []
        has_data = False

        # Age from yob
        if user_info.get("yob"):
            age = datetime.now().year - user_info["yob"]
            lines.append(f"Возраст: {age} лет")
            has_data = True

        # Gender
        if user_info.get("gender"):
            gender_ru = "Мужской" if user_info["gender"] == "m" else "Женский"
            lines.append(f"Пол: {gender_ru}")
            has_data = True

        # Weight
        if user_info.get("weight"):
            lines.append(f"Вес: {user_info['weight']} кг")
            has_data = True

        # Height
        if user_info.get("height"):
            lines.append(f"Рост: {user_info['height']} см")
            has_data = True

        # Activity level
        if user_info.get("activity_level"):
            activity = user_info["activity_level"]
            if activity <= 1.2:
                activity_ru = "Минимальная"
            elif activity <= 1.37:
                activity_ru = "Легкая"
            elif activity <= 1.55:
                activity_ru = "Средняя"
            elif activity <= 1.73:
                activity_ru = "Высокая"
            else:
                activity_ru = "Экстремальная"
            lines.append(f"Активность: {activity_ru}")
            has_data = True

        if not has_data:
            return "Данные профиля не заполнены. Рекомендуем заполнить профиль для более точного анализа."

        return "\n".join(lines)

    def _calculate_bmr(self, weight: float, height: int, yob: int, gender: str) -> int:
        """Calculate Basal Metabolic Rate using Mifflin-St Jeor formula"""
        age = datetime.now().year - yob

        if gender == "m":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        else:
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

        return int(bmr)

    def _determine_user_goal_type(self, user_info: dict, user_goals: dict) -> str:
        """Determine if user wants to lose/gain/maintain weight based on profile and goals"""
        # Check if we have all required data
        required_fields = ["weight", "height", "yob", "gender", "activity_level"]
        if not all(user_info.get(field) for field in required_fields):
            if user_goals.get("calories"):
                return "Цель по калориям установлена, но без данных профиля невозможно определить цель (похудеть/набрать/поддержать вес). Рекомендуем заполнить профиль."
            return "Данные профиля не заполнены, невозможно определить цель. Рекомендуем заполнить профиль для более точного анализа."

        # Check if user has calorie goal
        if not user_goals.get("calories"):
            return "Цель по калориям не установлена, невозможно определить цель (похудеть/набрать/поддержать вес)."

        # Calculate maintenance calories
        bmr = self._calculate_bmr(
            weight=user_info["weight"],
            height=user_info["height"],
            yob=user_info["yob"],
            gender=user_info["gender"]
        )
        maintenance_calories = bmr * user_info["activity_level"]
        calorie_goal = user_goals["calories"]

        # Determine goal with tolerance of 100 kcal
        deficit = maintenance_calories - calorie_goal
        if deficit > 100:
            deficit_percent = (deficit / maintenance_calories) * 100
            return f"Похудеть (дефицит {deficit:.0f} ккал/день или {deficit_percent:.1f}% от нормы поддержания веса)"
        elif deficit < -100:
            surplus = abs(deficit)
            surplus_percent = (surplus / maintenance_calories) * 100
            return f"Набрать вес (профицит {surplus:.0f} ккал/день или {surplus_percent:.1f}% от нормы поддержания веса)"
        else:
            return "Поддержать вес (цель примерно соответствует норме поддержания веса)"

    async def generate_report(
        self,
        period: str,
        start_date: datetime,
        end_date: datetime,
        user_goals: dict,
        summary: dict,
        daily_components: list,
        user_info: dict = None
    ) -> str:
        """Generate AI report in Russian based on gepvi_eat data"""
        # Choose prompt based on period
        prompt_template = DAILY_REPORT_PROMPT if period == "day" else WEEKLY_MONTHLY_REPORT_PROMPT

        # Calculate days count
        days_count = len(daily_components) if daily_components else 0

        # Period name in Russian
        period_names = {
            "day": "дневной",
            "week": "недельный",
            "month": "месячный"
        }
        period_ru = period_names.get(period, period)

        # Format data for prompt
        user_goals_str = self._format_user_goals(user_goals)
        summary_str = self._format_summary(summary)
        components_str = self._format_components_compact(daily_components)
        user_profile_str = self._format_user_profile(user_info or {})
        user_goal_type_str = self._determine_user_goal_type(user_info or {}, user_goals)

        prompt = prompt_template.format(
            period=period,
            period_ru=period_ru,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            days_count=days_count,
            user_goals=user_goals_str,
            summary=summary_str,
            daily_components=components_str,
            user_profile=user_profile_str,
            user_goal_type=user_goal_type_str
        )

        # Make API call
        payload = {
            "model": self.primary_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.5
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://gepvi_eat.com",
                    "X-Title": "GepviEat Bot"
                },
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()

    async def request(self, prompt: str) -> Optional[str]:
        """
        Простой запрос к AI (для совместимости с legacy кодом)

        NOTE: Этот метод НЕ использует fallback модели и НЕ парсит nutrition данные.
        Используйте analyze_food_text/image/audio для анализа питания.
        """
        try:
            payload = {
                "model": self.primary_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.7
            }

            async with httpx.AsyncClient(timeout=self.BASE_TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://gepvi_eat.com",
                        "X-Title": "GepviEat Bot"
                    },
                    json=payload
                )

                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()

        except httpx.HTTPError as e:
            logger.error("OpenRouter API error: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error in request: %s", e)
            raise


# Singleton instance
open_router_client = OpenRouterClient()
