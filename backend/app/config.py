import os


def api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def base_url() -> str | None:
    value = os.getenv("OPENAI_BASE_URL", "").strip()
    return value or None


def model_name() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def internet_mode() -> str:
    mode = os.getenv("OPENAI_HAS_INTERNET", "auto").strip().lower()
    if mode not in {"auto", "true", "false", "1", "0", "yes", "no", "on", "off"}:
        return "auto"
    if mode in {"1", "true", "yes", "on"}:
        return "true"
    if mode in {"0", "false", "no", "off"}:
        return "false"
    return "auto"
