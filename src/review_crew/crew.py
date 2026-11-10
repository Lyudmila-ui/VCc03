"""Сборка Crew и точка входа пайплайна: run_review(image_path).

Порядок задач в Crew (Process.sequential):
    1. ocr_task            — распознавание текста с изображения;
    2. classification_task — тональность (positive/negative);
    3. positive_ct         — ConditionalTask: выполняется только при sentiment == 'positive';
    4. negative_ct         — ConditionalTask: выполняется только при sentiment == 'negative'.

Итоговый результат собирается вручную из output_pydantic каждой задачи,
поэтому ветвление полностью детерминировано на уровне данных.
"""

from typing import Optional

from crewai import Crew, Process

from review_crew.models import (
    NegativeResponse,
    OcrResult,
    PositiveContent,
    ReviewClassification,
    ReviewPipelineResult,
)
from review_crew.tasks import build_tasks


def _get_pydantic(task_output_holder, model_cls, task_name: str):
    """Достать структурированный вывод задачи; если задача была пропущена — None."""
    output = getattr(task_output_holder, "output", None)
    if output is None:
        return None
    data = getattr(output, "pydantic", None)
    if data is None:
        return None
    # CrewAI уже валидирует вывод по output_pydantic; дополнительно проверяем тип.
    if isinstance(data, model_cls):
        return data
    try:
        return model_cls.model_validate(data)
    except Exception as exc:  # pragma: no cover - защитный путь
        raise RuntimeError(
            f"Задача «{task_name}» вернула данные, не соответствующие схеме {model_cls.__name__}: {exc}"
        ) from exc


def run_review(image_path: str) -> ReviewPipelineResult:
    """Прогнать полный пайплайн по изображению отзыва и вернуть типизированный результат.

    Args:
        image_path: локальный путь к JPEG/PNG с отзывом клиента.

    Returns:
        ReviewPipelineResult с классификацией и контентом активной ветки
        (PositiveContent или NegativeResponse).

    Raises:
        RuntimeError: если crew не смог распознать отзыв или классифицировать его.
    """
    tasks = build_tasks(image_path)

    crew = Crew(
        agents=[t.agent for t in tasks.base + tasks.conditional],
        tasks=tasks.base + tasks.conditional,
        process=Process.sequential,
        verbose=True,
    )

    crew.kickoff()

    ocr: Optional[OcrResult] = _get_pydantic(tasks.ocr, OcrResult, "OCR")
    classification: Optional[ReviewClassification] = _get_pydantic(
        tasks.classification, ReviewClassification, "Классификация"
    )
    positive: Optional[PositiveContent] = _get_pydantic(
        tasks.positive, PositiveContent, "Позитивный контент"
    )
    negative: Optional[NegativeResponse] = _get_pydantic(
        tasks.negative, NegativeResponse, "Ответ на негатив"
    )

    if classification is None:
        raise RuntimeError(
            "Не удалось классифицировать отзыв. Проверьте читаемость изображения, "
            "ключ и баланс RouterAI."
        )

    active_branch_result = positive if classification.sentiment == "positive" else negative
    if active_branch_result is None:
        raise RuntimeError(
            "Условная задача активной ветки не выполнилась (ConditionalTask не сработал). "
            "Обновите CrewAI до версии с поддержкой ConditionalTask (>= 0.51)."
        )

    return ReviewPipelineResult(
        classification=classification,
        ocr=ocr,
        positive=positive,
        negative=negative,
    )
