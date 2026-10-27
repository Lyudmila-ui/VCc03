"""Фабрика LLM для RouterAI (https://routerai.ru).

RouterAI — OpenAI-совместимый агрегатор: используем стандартный класс crewai.LLM
с параметрами model / base_url / api_key. Префикс "openai/" в поле model обязателен:
он переключает LiteLLM (внутренний движок CrewAI) на OpenAI-совместимый протокол.

Других провайдеров здесь нет и быть не может — только RouterAI.
"""

from crewai import LLM

from review_crew.config import (
    ROUTERAI_BASE_URL,
    get_routerai_api_key,
    get_text_model,
    get_vision_model,
)


def _routerai_llm(model: str, temperature: float = 0.2) -> LLM:
    """Собрать LLM, указывающий на RouterAI.

    Ключ читается через config.get_routerai_api_key(): если он не задан —
    приложение падает сразу с понятным сообщением (fail-fast).
    """
    # Если в .env модель уже указана с префиксом "openai/", не дублируем его.
    final_model = model if model.startswith("openai/") else f"openai/{model}"
    return LLM(
        model=final_model,
        base_url=ROUTERAI_BASE_URL,
        api_key=get_routerai_api_key(),
        temperature=temperature,
    )


def get_text_llm() -> LLM:
    """LLM для классификации тональности и генерации контента."""
    return _routerai_llm(get_text_model())


def get_vision_llm() -> LLM:
    """LLM для OCR-агента (мультимодальная модель, низкая температура)."""
    return _routerai_llm(get_vision_model(), temperature=0.1)
