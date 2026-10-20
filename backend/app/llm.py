import logging

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, AuthenticationError, BadRequestError, NotFoundError

from app.config import api_key, base_url, internet_mode, model_name

logger = logging.getLogger(__name__)

PLAN_SYSTEM = (
    "Составь пошаговый план (5-6 шагов) для анализа сайта по ссылке "
    "и генерации SEO-ядра. Верни результат в JSON, каждый шаг — отдельный промпт."
)

STEP_SYSTEM = (
    "Ты SEO-аналитик. Выполни только текущий шаг. "
    "Не придумывай факты о странице, которых нет в ссылке или в переданном тексте. "
    "Если данных не хватает, так и напиши. Отвечай по-русски."
)

FINAL_SYSTEM = (
    "Ты собираешь SEO-ядро сайта по промежуточным результатам анализа. "
    "Пиши по-русски, структурированно, так, чтобы маркетолог мог взять текст в работу. "
    "Не пересказывай ход разбора: отдай готовое ядро."
)

_client: AsyncOpenAI | None = None
_internet: bool | None = None


class MissingKey(RuntimeError):
    pass


class WebSearchUnavailable(RuntimeError):
    pass


def reset_client() -> None:
    global _client, _internet
    _client = None
    _internet = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is not None:
        return _client
    key = api_key()
    if not key:
        raise MissingKey("Не задан OPENAI_API_KEY. Впишите ключ в файл .env и перезапустите контейнеры.")
    kwargs: dict = {"api_key": key, "timeout": 180.0}
    if base_url():
        kwargs["base_url"] = base_url()
    _client = AsyncOpenAI(**kwargs)
    return _client


async def model_has_internet() -> bool:
    global _internet
    mode = internet_mode()
    if mode == "true":
        return True
    if mode == "false":
        return False
    if _internet is not None:
        return _internet

    client = get_client()
    try:
        await client.responses.create(
            model=model_name(),
            tools=[{"type": "web_search"}],
            input="Ответь одним словом: да",
            max_output_tokens=16,
        )
    except (BadRequestError, NotFoundError, AttributeError, TypeError) as exc:
        logger.info("Поиск в интернете недоступен: %s", exc)
        _internet = False
        return False
    except AuthenticationError:
        raise
    except APIStatusError as exc:
        if exc.status_code in {400, 404, 422}:
            logger.info("Поиск в интернете недоступен: %s", exc)
            _internet = False
            return False
        raise
    except APIConnectionError:
        raise
    else:
        _internet = True
        return True


async def complete(messages: list[dict], *, json_mode: bool = False, max_tokens: int = 2000) -> str:
    client = get_client()
    kwargs: dict = {
        "model": model_name(),
        "messages": messages,
        "temperature": 0.4,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await client.chat.completions.create(**kwargs, max_tokens=max_tokens)
    except BadRequestError as exc:
        message = str(exc).lower()
        if "response_format" in message or "json" in message:
            kwargs.pop("response_format", None)
        if "temperature" in message:
            kwargs.pop("temperature", None)
        if "max_tokens" in message or "max_completion_tokens" in message:
            response = await client.chat.completions.create(**kwargs, max_completion_tokens=max_tokens)
        else:
            response = await client.chat.completions.create(**kwargs)
    text = response.choices[0].message.content or ""
    return text.strip()


async def complete_with_web(messages: list[dict]) -> str:
    client = get_client()
    system = "\n\n".join(item["content"] for item in messages if item["role"] == "system")
    user = "\n\n".join(item["content"] for item in messages if item["role"] == "user")
    try:
        response = await client.responses.create(
            model=model_name(),
            instructions=system or None,
            tools=[{"type": "web_search"}],
            input=user,
        )
    except (BadRequestError, NotFoundError) as exc:
        raise WebSearchUnavailable(str(exc)) from exc
    except APIStatusError as exc:
        if exc.status_code in {400, 404, 422}:
            raise WebSearchUnavailable(str(exc)) from exc
        raise
    return _response_text(response)


def explain_openai_error(exc: Exception) -> str:
    if isinstance(exc, MissingKey):
        return str(exc)
    if isinstance(exc, AuthenticationError):
        return "Ключ OpenAI не принят. Проверьте OPENAI_API_KEY в файле .env."
    text = str(exc)
    lowered = text.lower()
    if "429" in text or "rate limit" in lowered:
        return "ChatGPT ограничил частоту запросов. Подождите минуту и запустите разбор снова."
    if isinstance(exc, APIConnectionError):
        return "Нет соединения с API OpenAI. Проверьте сеть и OPENAI_BASE_URL."
    return f"Запрос к ChatGPT не выполнился: {text[:400]}"


def _response_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text).strip()
    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(str(text))
    return "\n".join(parts).strip()
