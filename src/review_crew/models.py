"""Pydantic-модели — схемы вывода всех задач CrewAI (output_pydantic)."""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Промежуточные результаты
# ---------------------------------------------------------------------------

class OcrResult(BaseModel):
    """Результат распознавания текста с изображения отзыва."""

    review_text: str = Field(
        description="Полный распознанный текст отзыва. Если текст нечитаем — пустая строка."
    )
    customer_name: Optional[str] = Field(
        default=None,
        description="Имя клиента, если оно указано в отзыве; иначе null.",
    )
    rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Оценка в звёздах (1–5), если она видна на изображении; иначе null.",
    )


class ReviewClassification(BaseModel):
    """Классификация тональности отзыва."""

    sentiment: Literal["positive", "negative"] = Field(
        description="Тональность отзыва: 'positive' или 'negative'."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Уверенность классификации от 0.0 до 1.0.",
    )
    key_emotion: str = Field(
        description="Главная эмоция клиента одной фразой, например: 'восхищение сервисом', "
        "'раздражение из-за ожидания', 'спокойное разочарование'."
    )


# ---------------------------------------------------------------------------
# Ветка POSITIVE: три формата контента
# ---------------------------------------------------------------------------

class LandingCard(BaseModel):
    """Карточка отзыва для лендинга."""

    headline: str = Field(description="Короткий цепляющий заголовок карточки (до 60 символов).")
    quote: str = Field(description="Точная цитата из отзыва — 1–2 предложения.")
    customer_name: str = Field(description="Имя клиента (из отзыва; если имени нет — «клиент»).")


class StorySlide(BaseModel):
    """Один слайд сторис."""

    slide_number: int = Field(ge=1, le=3, description="Номер слайда: 1, 2 или 3.")
    text: str = Field(description="Текст слайда: коротко, эмоционально, не более ~180 символов.")


class MiniCase(BaseModel):
    """Мини-кейс по мотивам отзыва (целевая длина — до 500 символов)."""

    who: str = Field(description="КТО клиент: короткий портрет (кто он, что за задача/ситуация).")
    problem: str = Field(description="ПРОБЛЕМА, с которой клиент пришёл.")
    solution: str = Field(description="РЕШЕНИЕ: что именно сделали продукт/сервис/команда.")
    result: str = Field(description="РЕЗУЛЬТАТ в терминах клиента + призыв к действию.")


class PositiveContent(BaseModel):
    """Итоговый положительный контент: карточка + сторис + мини-кейс."""

    landing_card: LandingCard = Field(description="Карточка для лендинга.")
    story_slides: List[StorySlide] = Field(
        description="Ровно три слайда сторис (slide_number 1, 2, 3)."
    )
    mini_case: MiniCase = Field(description="Мини-кейс до 500 символов (who/problem/solution/result).")


# ---------------------------------------------------------------------------
# Ветка NEGATIVE: ответ на отзыв
# ---------------------------------------------------------------------------

class NegativeResponse(BaseModel):
    """Корректный ответ на негативный отзыв из трёх частей."""

    acknowledgment: str = Field(
        description="Признание ситуации своими словами, без канцелярских шаблонов "
        "вроде «приносим извинения за доставленные неудобства»."
    )
    solution_offer: str = Field(
        description="Конкретное предложение решения или компенсации (что и в какие сроки сделаем)."
    )
    gratitude: str = Field(
        description="Искренняя благодарность за обратную связь — 1 предложение."
    )
    full_text: str = Field(
        description="Собранный полный ответ из трёх частей, готовый к отправке клиенту."
    )


# ---------------------------------------------------------------------------
# Итоговый результат прогона crew
# ---------------------------------------------------------------------------

class ReviewPipelineResult(BaseModel):
    """Обёртка результата: тональность + контент одной из двух веток."""

    classification: ReviewClassification = Field(description="Классификация отзыва.")
    ocr: Optional[OcrResult] = Field(default=None, description="Распознанный текст отзыва.")
    positive: Optional[PositiveContent] = Field(
        default=None, description="Заполнено, если sentiment == 'positive'."
    )
    negative: Optional[NegativeResponse] = Field(
        default=None, description="Заполнено, если sentiment == 'negative'."
    )

    @property
    def content(self) -> Union[PositiveContent, NegativeResponse, None]:
        """Контент активной ветки."""
        return self.positive if self.classification.sentiment == "positive" else self.negative
