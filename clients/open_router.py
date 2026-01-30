"""OpenRouter клиент для AI запросов"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import httpx

from settings.config import AppConfig

logger = logging.getLogger(__name__)


# AI Prompts for Report Generation
DAILY_REPORT_PROMPT = """You are a nutrition analyst. Generate a brief daily report in Russian.

USER DATA:
- Period: {start_date} to {end_date}
- Goals: {user_goals}

NUTRITION SUMMARY:
{summary}

DAILY BREAKDOWN:
{daily_components}

INSTRUCTIONS:
- Write in Russian, friendly tone
- Start with raw statistics (calories, protein, fats, carbs)
- Provide 1-2 short observations
- Give 1 brief recommendation
- Under 300 words
- NO long-term conclusions (just one day)
"""

WEEKLY_MONTHLY_REPORT_PROMPT = """You are a nutrition analyst. Generate a detailed {period} report in Russian.

USER DATA:
- Period: {start_date} to {end_date}
- Goals: {user_goals}

NUTRITION SUMMARY:
{summary}

DAILY BREAKDOWN:
{daily_components}

INSTRUCTIONS:
- Write in Russian, professional but friendly
- Structure:
  1. RAW DATA (totals and averages)
  2. INTERPRETATION (meeting goals?)
  3. CROSS-ANALYSIS (patterns if enough data)
  4. INSIGHTS (2-4 observations)
  5. RECOMMENDATIONS (1-2 actionable suggestions)
- Under 800 words
- Look for trends and patterns
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

        # Format data for prompt
        user_goals_str = str(user_goals) if user_goals else "Цели не установлены"
        prompt = prompt_template.format(
            period=period,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            user_goals=user_goals_str,
            summary=str(summary),
            daily_components=str(daily_components)
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
