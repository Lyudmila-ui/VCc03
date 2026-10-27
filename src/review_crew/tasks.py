"""Задачи CrewAI, включая ConditionalTask для ветвления positive / negative.

Схема (Process.sequential):

    ocr_task -> classification_task -> [ positive_ct | negative_ct ]

Важно по ConditionalTask:
- условие (condition) — это функция, которой CrewAI передаёт словарь контекста;
  в ``context["raw"]`` находится строковое представление вывода предыдущей
  (последней выполненной) задачи — то есть JSON классификации;
- задача ветки создаётся как обычный Task, а затем оборачивается в
  ConditionalTask с on_trigger="run", on_false="skip";
- вторая ветка при ложном условии просто пропускается и не тратит токены.
"""

import json
from typing import Callable, List, NamedTuple, Tuple

from crewai import Task
from crewai.task import ConditionalTask

from review_crew.agents import (
    build_classifier_agent,
    build_negative_responder_agent,
    build_ocr_agent,
    build_positive_creator_agent,
)
from review_crew.models import (
    NegativeResponse,
    OcrResult,
    PositiveContent,
    ReviewClassification,
)


class ReviewTasks(NamedTuple):
    """Набор задач для сборки Crew."""

    base: List[Task]                    # [ocr_task, classification_task]
    conditional: List[ConditionalTask]  # [positive_ct, negative_ct]
    ocr: Task
    classification: Task
    positive: Task
    negative: Task


def _extract_sentiment(context: dict) -> str:
    """Достать sentiment из контекста, который CrewAI передаёт в condition().

    context["raw"] — вывод последней выполненной задачи (классификации).
    Он может прийти как объект ReviewClassification, как JSON-строка или как
    произвольный текст — разбираем устойчиво, при неудаче возвращаем "".
    """
    raw = context.get("raw") if isinstance(context, dict) else None
    if raw is None:
        return ""
    if isinstance(raw, ReviewClassification):
        return raw.sentiment
    text = str(raw)
    try:
        data = json.loads(text)
        return str(data.get("sentiment", "")).lower()
    except Exception:
        # Fallback: ищем ключевое слово в тексте напрямую.
        lowered = text.lower()
        if "positive" in lowered and "negative" not in lowered:
            return "positive"
        if "negative" in lowered and "positive" not in lowered:
            return "negative"
        return ""


def build_tasks(image_path: str) -> ReviewTasks:
    """Собрать все задачи пайплайна: OCR → классификация → условные ветки.

    Args:
        image_path: путь к сохранённому во временную директорию изображению отзыва.
    """
    ocr_agent = build_ocr_agent()
    classifier_agent = build_classifier_agent()
    positive_agent = build_positive_creator_agent()
    negative_agent = build_negative_responder_agent()

    # ------------------------------------------------------------------ OCR
    ocr_task = Task(
        agent=ocr_agent,
        description=(
            "Распознай текст отзыва клиента с изображения по пути: {image_path}.\n"
            "Используй инструмент OCR (OCRTool), чтобы извлечь текст с картинки.\n"
            "Верни полный распознанный текст дословно (review_text), имя клиента,\n"
            "если оно видно (customer_name), и оценку в звёздах, если она видна (rating).\n"
            "Ничего не додумывай и не исправляй в тексте клиента."
        ).format(image_path=image_path),
        expected_output=(
            "Структура OcrResult: точный распознанный текст отзыва, "
            "имя клиента (или null) и оценка 1–5 (или null)."
        ),
        output_pydantic=OcrResult,
    )

    # --------------------------------------------------------- Классификация
    classification_task = Task(
        agent=classifier_agent,
        description=(
            "Определи тональность отзыва клиента по его распознанному тексту\n"
            "(текст доступен в контексте задачи — результат OCR).\n\n"
            "Правила:\n"
            "- sentiment: строго 'positive' или 'negative' (по преобладающей эмоции);\n"
            "- confidence: уверенность от 0.0 до 1.0;\n"
            "- key_emotion: главная эмоция клиента одной короткой фразой на русском.\n"
            "Если текст пустой или нечитаемый — считай отзыв negative с низкой уверенностью."
        ),
        expected_output=(
            "Структура ReviewClassification: sentiment ('positive'/'negative'), "
            "confidence (0–1), key_emotion."
        ),
        output_pydantic=ReviewClassification,
        context=[ocr_task],
    )

    # ------------------------------------------------------- Ветка POSITIVE
    positive_task = Task(
        agent=positive_agent,
        description=(
            "Клиент оставил ПОЛОЖИТЕЛЬНЫЙ отзыв (тональность, уверенность и главная\n"
            "эмоция — в контексте задачи, там же распознанный текст отзыва).\n\n"
            "Сгенерируй три формата контента по формуле «эмоция → формат → визуализация → призыв»:\n"
            "1) Карточка для лендинга (LandingCard): headline (до 60 символов),\n"
            "   quote — точная цитата из отзыва, customer_name — имя клиента из отзыва,\n"
            "   если имени нет — «клиент».\n"
            "2) Сторис из ровно трёх слайдов (StorySlide, slide_number 1/2/3):\n"
            "   слайд 1 — цепляющая эмоция/интрига, слайд 2 — суть отзыва (цитата),\n"
            "   слайд 3 — результат + призыв к действию. Не более ~180 символов на слайд.\n"
            "3) Мини-кейс (MiniCase) суммарно до 500 символов с блоками:\n"
            "   who — кто клиент; problem — с чем пришёл; solution — что сделали;\n"
            "   result — результат в терминах клиента + призыв к действию.\n\n"
            "Используй только факты из отзыва, ничего не выдумывай."
        ),
        expected_output=(
            "Структура PositiveContent: landing_card (headline/quote/customer_name), "
            "story_slides (ровно 3 слайда), mini_case (who/problem/solution/result, до 500 симв.)."
        ),
        output_pydantic=PositiveContent,
        context=[ocr_task, classification_task],
    )

    # -------------------------------------------------------- Ветка NEGATIVE
    negative_task = Task(
        agent=negative_agent,
        description=(
            "Клиент оставил НЕГАТИВНЫЙ отзыв (тональность, уверенность и главная\n"
            "эмоция — в контексте задачи, там же распознанный текст отзыва).\n\n"
            "Напиши корректный ответ клиенту из трёх частей:\n"
            "1) acknowledgment — признание ситуации своими словами, БЕЗ шаблонов вроде\n"
            "   «приносим извинения за доставленные неудобства», без оправданий;\n"
            "2) solution_offer — конкретное предложение решения или компенсации со сроком;\n"
            "3) gratitude — искренняя благодарность за обратную связь, одно предложение;\n"
            "4) full_text — собранный готовый ответ (все три части связно, с обращением к клиенту).\n\n"
            "Стиль: вежливый, неформальный, живой; упомяни 1–2 конкретные детали из отзыва,\n"
            "чтобы клиент видел: его текст действительно прочитали."
        ),
        expected_output=(
            "Структура NegativeResponse: acknowledgment, solution_offer, gratitude, full_text."
        ),
        output_pydantic=NegativeResponse,
        context=[ocr_task, classification_task],
    )

    # ------------------------------------------------------ Условия ветвления
    def is_positive(context: dict) -> bool:
        """Условие запуска генерации позитивного контента."""
        return _extract_sentiment(context) == "positive"

    def is_negative(context: dict) -> bool:
        """Условие запуска ответа на негативный отзыв."""
        return _extract_sentiment(context) == "negative"

    positive_ct = ConditionalTask(
        task=positive_task,
        condition=is_positive,
        on_trigger="run",   # sentiment == positive → выполняем задачу
        on_false="skip",    # иначе — пропускаем
    )
    negative_ct = ConditionalTask(
        task=negative_task,
        condition=is_negative,
        on_trigger="run",   # sentiment == negative → выполняем задачу
        on_false="skip",    # иначе — пропускаем
    )

    return ReviewTasks(
        base=[ocr_task, classification_task],
        conditional=[positive_ct, negative_ct],
        ocr=ocr_task,
        classification=classification_task,
        positive=positive_task,
        negative=negative_task,
    )
