import os

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


def api_key() -> str:
    return os.getenv("DEEPSEEK_API_KEY", "").strip()


def base_url() -> str:
    return os.getenv("DEEPSEEK_BASE_URL", "").strip() or DEFAULT_BASE_URL


def model_name() -> str:
    return os.getenv("DEEPSEEK_MODEL", "").strip() or DEFAULT_MODEL


def internet_mode() -> str:
    mode = os.getenv("DEEPSEEK_HAS_INTERNET", "false").strip().lower()
    if mode in {"1", "true", "yes", "on"}:
        return "true"
    if mode in {"auto"}:
        return "auto"
    return "false"
