"""Streamlit-приложение «Анализ отзыва клиента» — точка входа.

Запуск:  streamlit run app.py

Сценарий: пользователь загружает JPEG/PNG с отзывом, нажимает «Обработать отзыв»,
пайплайн CrewAI (OCR → классификация → ConditionalTask-ветвление) возвращает
результат, который отображается на странице и доступен для скачивания в JSON и TXT.

Ключ RouterAI никогда не попадает в этот слой: он читается только в
src/review_crew/llm_factory.py из переменных окружения.
"""

import os
import sys
import tempfile

import streamlit as st

# Делаем пакет src/review_crew импортируемым при запуске из корня проекта.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from review_crew.crew import run_review  # noqa: E402  (импорт после настройки sys.path)
from review_crew.models import (  # noqa: E402
    NegativeResponse,
    PositiveContent,
    ReviewPipelineResult,
)

st.set_page_config(page_title="Анализ отзыва клиента", page_icon="📣", layout="centered")


# ---------------------------------------------------------------------------
# helpers: текстовое представление результата для скачивания (.txt)
# ---------------------------------------------------------------------------

def result_to_text(result: ReviewPipelineResult) -> str:
    """Собрать человекочитаемый текстовый отчёт по результату пайплайна."""
    lines = []
    c = result.classification
    lines.append("АНАЛИЗ ОТЗЫВА КЛИЕНТА")
    lines.append("=" * 40)
    lines.append(f"Тональность: {c.sentiment}")
    lines.append(f"Уверенность: {c.confidence:.2f}")
    lines.append(f"Главная эмоция: {c.key_emotion}")
    lines.append("")

    if result.ocr and result.ocr.review_text.strip():
        lines.append("РАСПОЗНАННЫЙ ТЕКСТ ОТЗЫВА")
        lines.append("-" * 40)
        lines.append(result.ocr.review_text.strip())
        if result.ocr.customer_name:
            lines.append(f"(имя клиента: {result.ocr.customer_name})")
        if result.ocr.rating:
            lines.append(f"(оценка: {result.ocr.rating}/5)")
        lines.append("")

    content = result.content
    if isinstance(content, PositiveContent):
        card = content.landing_card
        lines.append("КАРТОЧКА ДЛЯ ЛЕНДИНГА")
        lines.append("-" * 40)
        lines.append(f"Заголовок: {card.headline}")
        lines.append(f"Цитата: «{card.quote}»")
        lines.append(f"Имя клиента: {card.customer_name}")
        lines.append("")

        lines.append("СТОРИС (3 СЛАЙДА)")
        lines.append("-" * 40)
        for slide in content.story_slides:
            lines.append(f"Слайд {slide.slide_number}: {slide.text}")
        lines.append("")

        mc = content.mini_case
        lines.append("МИНИ-КЕЙС")
        lines.append("-" * 40)
        lines.append(f"Who: {mc.who}")
        lines.append(f"Problem: {mc.problem}")
        lines.append(f"Solution: {mc.solution}")
        lines.append(f"Result: {mc.result}")
    elif isinstance(content, NegativeResponse):
        lines.append("ОТВЕТ НА ОТРИЦАТЕЛЬНЫЙ ОТЗЫВ")
        lines.append("-" * 40)
        lines.append("1. Признание ситуации:")
        lines.append(content.acknowledgment)
        lines.append("")
        lines.append("2. Предложение решения/компенсации:")
        lines.append(content.solution_offer)
        lines.append("")
        lines.append("3. Благодарность:")
        lines.append(content.gratitude)
        lines.append("")
        lines.append("ПОЛНЫЙ ТЕКСТ ОТВЕТА")
        lines.append("-" * 40)
        lines.append(content.full_text)

    return "\n".join(lines)


def render_positive(content: PositiveContent) -> None:
    """Отрисовать три блока позитивного контента."""
    card = content.landing_card
    st.subheader("✅ Карточка для лендинга")
    st.markdown(
        f"**{card.headline}**\n\n"
        f"> «{card.quote}»\n>\n> — **{card.customer_name}**"
    )

    st.subheader("📱 Сторис (3 слайда)")
    slides = sorted(content.story_slides, key=lambda s: s.slide_number)
    cols = st.columns(max(len(slides), 1))
    for col, slide in zip(cols, slides):
        with col:
            st.markdown(f"**Слайд {slide.slide_number}**")
            st.markdown(slide.text)

    mc = content.mini_case
    st.subheader("📝 Мини-кейс")
    st.markdown(
        f"**Who:** {mc.who}\n\n"
        f"**Problem:** {mc.problem}\n\n"
        f"**Solution:** {mc.solution}\n\n"
        f"**Result:** {mc.result}"
    )


def render_negative(resp: NegativeResponse) -> None:
    """Отрисовать ответ на негативный отзыв."""
    st.subheader("💬 Ответ на отзыв")
    st.markdown(resp.full_text)
    with st.expander("Разбивка по трём частям"):
        st.markdown(f"**1. Признание ситуации**\n\n{resp.acknowledgment}")
        st.markdown(f"**2. Решение / компенсация**\n\n{resp.solution_offer}")
        st.markdown(f"**3. Благодарность**\n\n{resp.gratitude}")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("📣 Анализ отзыва клиента")
    st.caption(
        "Загрузите изображение отзыва (скриншот или фото, JPEG/PNG). "
        "Мультиагентная система распознает текст, оценит тональность и либо "
        "сгенерирует контент для соцсетей, либо напишет корректный ответ."
    )

    uploaded = st.file_uploader(
        "Загрузите отзыв (JPEG/PNG)", type=["jpg", "jpeg", "png"]
    )
    run_button = st.button("Обработать отзыв", type="primary", disabled=uploaded is None)

    # Обработка по клику; результат храним в session_state, чтобы кнопки
    # скачивания не теряли данные при повторных перерисовках страницы.
    if run_button and uploaded is not None:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1] or ".jpg")
        tmp_path = tmp.name
        try:
            tmp.write(uploaded.getbuffer())
            tmp.close()
            with st.spinner("Агенты работают…"):
                st.session_state["result"] = run_review(tmp_path)
            st.session_state["error"] = None
        except Exception as exc:
            st.session_state["result"] = None
            st.session_state["error"] = (
                f"{exc}\n\nПодсказки: проверьте .env (ROUTERAI_API_KEY), баланс RouterAI "
                "и доступность сети. Ключ не должен попадать в логи и интерфейс."
            )
        finally:
            # Удаляем временный файл изображения.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        st.rerun()

    error = st.session_state.get("error")
    if error:
        st.error(f"Не удалось обработать отзыв.\n\n{error}")

    result: ReviewPipelineResult | None = st.session_state.get("result")
    if result is None:
        return

    c = result.classification
    badge = "🟢 Позитивный" if c.sentiment == "positive" else "🔴 Негативный"
    st.success(f"Тональность: {badge} · уверенность {c.confidence:.2f} · эмоция: {c.key_emotion}")

    if result.ocr and result.ocr.review_text.strip():
        with st.expander("Распознанный текст отзыва (OCR)"):
            st.text(result.ocr.review_text.strip())

    content = result.content
    if isinstance(content, PositiveContent):
        render_positive(content)
    elif isinstance(content, NegativeResponse):
        render_negative(resp=content)

    st.divider()
    st.subheader("Скачать результат")
    col_json, col_txt = st.columns(2)
    with col_json:
        st.download_button(
            label="⬇️ Скачать JSON",
            data=result.model_dump_json(indent=2),
            file_name="review_result.json",
            mime="application/json",
        )
    with col_txt:
        st.download_button(
            label="⬇️ Скачать TXT",
            data=result_to_text(result),
            file_name="review_result.txt",
            mime="text/plain",
        )


main()
