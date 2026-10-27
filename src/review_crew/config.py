"""Конфигурация: загрузка .env через python-dotenv и fail-проверка обязательных переменных.

Ключ RouterAI берётся ТОЛЬКО из переменных окружения. Никаких хардкода
и значений по умолчанию для секретов.
"""

import os

from dotenv import load_dotenv

# Загружаем .env из корня проекта (на два уровня выше этого файла).
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

ROUTERAI_BASE_URL = "https://routerai.ru/api/v1"

# Модели по умолчанию (имена хранятся БЕЗ префикса "openai/" — фабрика добавит его сама).
DEFAULT_TEXT_MODEL = "openai/openai/gpt-6.1-sol"
DEFAULT_VISION_MODEL = "google/gemma-3-27b-it"


def get_routerai_api_key() -> str:
    """Вернуть ROUTERAI_API_KEY или упасть с понятным сообщением (fail-fast)."""
    api_key = os.getenv("ROUTERAI_API_KEY", "").strip()
    if not api_key or api_key == "sk-your-routerai-key-here":
        raise RuntimeError(
            "Не задан ROUTERAI_API_KEY. Скопируйте .env.example в .env, "
            "вставьте реальный ключ из личного кабинета https://routerai.ru "
            "и убедитесь, что баланс пополнен."
        )
    return api_key


def get_text_model() -> str:
    """Имя текстовой модели из ROUTERAI_TEXT_MODEL (с дефолтом)."""
    return os.getenv("ROUTERAI_TEXT_MODEL", DEFAULT_TEXT_MODEL).strip() or DEFAULT_TEXT_MODEL


def get_vision_model() -> str:
    """Имя vision-модели из ROUTERAI_VISION_MODEL (с дефолтом)."""
    return os.getenv("ROUTERAI_VISION_MODEL", DEFAULT_VISION_MODEL).strip() or DEFAULT_VISION_MODEL
