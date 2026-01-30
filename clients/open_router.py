"""OpenRouter клиент для AI запросов"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import httpx

from settings.config import AppConfig

logger = logging.getLogger(__name__)


# AI Prompts for Report Generation
DAILY_REPORT_PROMPT = """You are a nutrition analyst. Generate a brief daily report in Russian.

STRUCTURE (MANDATORY):
1. Greeting: "Ваш дневной отчет готов!"
2. СТАТИСТИКА (brief summary of calories, protein, fats, carbs, fiber, liquid)
3. ЦЕЛИ (if user_macros_goals exist: compare actual vs goals, mention if goals are met or not)
4. КРАТКИЙ ВЫВОД (1-2 observations about nutrition quality)

CRITICAL INSTRUCTIONS:
- Write in Russian, friendly tone
- This is ONLY ONE DAY - do NOT make long-term conclusions or big recommendations
- You are NOT a doctor - do NOT diagnose or prescribe treatment
- Base insights on scientific nutrition data
- Be careful with recommendations - suggest mild adjustments, not radical changes
- Assess components for likely vitamin/mineral content (e.g., много овощей = хорошие витамины)
- Under 300 words

DATA EXPLANATION:
USER MACROS GOALS (may be missing or partially filled):
- calories: daily calorie goal
- protein: daily protein goal (grams)
- fats: daily fats goal (grams)
- carbs: daily carbs goal (grams)
- fiber: daily fiber goal (grams)
- liquid: daily liquid goal (ml)

SUMMARY STATISTICS:
- total_calories, total_protein, total_fats, total_carbs, total_fiber, total_liquid
- average_per_day (for multi-day periods)
- meals_count
- breakdown_by_type (breakfast, lunch, dinner, snack)

DAILY COMPONENTS:
For each day: date + list of components with:
- name: component name
- W: weight in grams
- L: liquid volume in ml

Period: {start_date} to {end_date}
Days with data: {days_count}

User Goals:
{user_goals}

Summary:
{summary}

Daily Components:
{daily_components}
"""

WEEKLY_MONTHLY_REPORT_PROMPT = """You are a nutrition analyst. Generate a detailed {period} report in Russian.

STRUCTURE (MANDATORY):
1. Greeting: "Ваш {period_ru} отчет готов!"
2. СТАТИСТИКА (raw numbers: totals and averages for calories, protein, fats, carbs, fiber, liquid)
3. ЦЕЛИ (if user_macros_goals exist: detailed comparison actual vs goals, calculate % achievement)
4. АНАЛИЗ ПАТТЕРНОВ (look for trends across days: consistent eating, meal timing, food variety)
5. ИНСАЙТЫ (2-4 evidence-based observations about nutrition quality, vitamin/mineral adequacy based on components)
6. РЕКОМЕНДАЦИИ (1-2 mild, actionable suggestions - NOT medical advice)

CRITICAL INSTRUCTIONS:
- Write in Russian, professional but friendly tone
- You are NOT a doctor - do NOT diagnose, prescribe treatment, or give medical advice
- You can only analyze nutrition data and provide general insights
- Base all insights on scientific nutrition research
- When suggesting changes, use soft language: "можно попробовать", "стоит рассмотреть", NOT "вам необходимо"
- Assess components for micronutrients: vegetables→vitamins, dairy→calcium, meat→B12, etc.
- Look for patterns: meal consistency, food variety, balance across days
- Under 800 words
- If data is incomplete (few days), mention limitations of analysis

DATA EXPLANATION:
USER MACROS GOALS (may be missing or partially filled):
- calories: daily calorie goal
- protein: daily protein goal (grams)
- fats: daily fats goal (grams)
- carbs: daily carbs goal (grams)
- fiber: daily fiber goal (grams)
- liquid: daily liquid goal (ml)

SUMMARY STATISTICS:
- total_calories, total_protein, total_fats, total_carbs, total_fiber, total_liquid
- average_per_day (average daily values)
- meals_count (total meals in period)
- breakdown_by_type (breakfast, lunch, dinner, snack with totals for each)
- macronutrients: totals + protein_percent, fats_percent, carbs_percent

DAILY COMPONENTS:
For each day: date + list of components with:
- name: component name in Russian
- W: weight in grams (solid food)
- L: liquid volume in ml (drinks)

Analyze components for likely micronutrient content and food diversity.

Period: {start_date} to {end_date}
Days with data: {days_count}

User Goals:
{user_goals}

Summary:
{summary}

Daily Components:
{daily_components}
"""


class OpenRouterClient:
    """Клиент для OpenRouter API с поддержкой fallback моделей"""

    # Fallback модели - попробуем по порядку если основная не сработала
    FALLBACK_MODELS = [
        "google/gemini-2.5-flash-lite",
        "google/gemini-3-flash-preview",
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
                            "HTTP-Referer": "https://gepvi_eat.com",
                            "X-Title": "GepviEat Bot"
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
                    lines.append(f"  {meal_name}: {meal_data.get('calories', 0)} ккал")

        return "\n".join(lines)

    async def generate_report(
        self,
        period: str,
        start_date: datetime,
        end_date: datetime,
        user_goals: dict,
        summary: dict,
        daily_components: list
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

        prompt = prompt_template.format(
            period=period,
            period_ru=period_ru,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            days_count=days_count,
            user_goals=user_goals_str,
            summary=summary_str,
            daily_components=components_str
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
