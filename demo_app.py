"""ДЕМО-режим интерфейса (без реального ключа RouterAI).

Полностью повторяет app.py, но вместо вызова LLM через CrewAI подставляет
функцию fake_run_review() — так можно посмотреть и проверить работу сайта
в браузере до покупки ключа. Настоящий запуск: streamlit run app.py.

Запуск демо:  streamlit run demo_app.py
"""

import os
import sys
import tempfile
import time

import streamlit as st

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from review_crew.models import (  # noqa: E402
    LandingCard,
    MiniCase,
    NegativeResponse,
    OcrResult,
    PositiveContent,
    ReviewClassification,
    ReviewPipelineResult,
    StorySlide,
)


def fake_run_review(image_path: str) -> ReviewPipelineResult:
    """Имитация пайплайна OCR → классификация → ветка.

    Имя файла с содержимым 'neg' или 'bad' даёт негативную ветку,
    иначе — позитивную. Эмулирует задержку работы агентов.
    """
    time.sleep(2)
    hint = (os.path.basename(image_path) or "").lower()
    negative = ("neg" in hint) or ("bad" in hint)

    ocr = OcrResult(
        review_text=(
            "Заказывал доставку в пятницу, привезли только во вторник, причём заказ "
            "перепутали. Менеджер решила вопрос за полчаса, но осадок остался."
            if negative
            else "Пользуюсь сервисом полгода — ни одной задержки! Консультант помог "
            "подобрать идеальный тариф, стало удобно в разы. Спасибо!"
        ),
        customer_name="Мария" if negative else "Дмитрий",
        rating=2 if negative else 5,
    )
    classification = ReviewClassification(
        sentiment="negative" if negative else "positive",
        confidence=0.87,
        key_emotion="раздражение" if negative else "восхищение",
    )

    if negative:
        response = NegativeResponse(
            acknowledgment=(
                "Мария, здравствуйте! Обещали пятницу — привезли во вторник, да ещё "
                "и заказ перепутали. Это наша ошибка, и мы её признаём без оправданий."
            ),
            solution_offer=(
                "Вернём стоимость доставки и начислим 1000 бонусов на счёт в течение "
                "24 часов. Если закажете снова — отправим приоритетной доставкой в тот же день."
            ),
            gratitude=(
                "Спасибо, что рассказали подробно: такие истории помогают нам чинить "
                "логистику до того, как она подведёт кого-то ещё."
            ),
            full_text=(
                "Мария, здравствуйте!\n\n"
                "Обещали пятницу — привезли во вторник, да ещё и заказ перепутали. "
                "Это наша ошибка, и мы её признаём без оправданий.\n\n"
                "Что делаем: вернём стоимость доставки и начислим 1000 бонусов на счёт "
                "в течение 24 часов. Если закажете снова — отправим приоритетной "
                "доставкой в тот же день.\n\n"
                "Спасибо, что рассказали подробно: такие истории помогают нам чинить "
                "логистику до того, как она подведёт кого-то ещё."
            ),
        )
        return ReviewPipelineResult(
            classification=classification, ocr=ocr, positive=None, negative=response
        )

    positive = PositiveContent(
        landing_card=LandingCard(
            headline="Полгода — ни одной задержки",
            quote="Пользуюсь сервисом полгода — ни одной задержки!",
            customer_name="Дмитрий",
        ),
        story_slides=[
            StorySlide(slide_number=1, text="6 месяцев. 0 задержек. Как это возможно? 👀"),
            StorySlide(
                slide_number=2,
                text="«Пользуюсь сервисом полгода — ни одной задержки!» — Дмитрий",
            ),
            StorySlide(
                slide_number=3,
                text="Хотите так же? Подключите тариф как у Дмитрия → ссылка в профиле",
            ),
        ],
        mini_case=MiniCase(
            who="Дмитрий, постоянный клиент (6 месяцев)",
            problem="Нужен был сервис без сбоев и понятный тариф",
            solution="Подобрали тариф на бесплатной консультации, подключили за 5 минут",
            result="Ни одной задержки за полгода. Попробуйте и вы — первый месяц бесплатно!",
        ),
    )
    return ReviewPipelineResult(
        classification=classification, ocr=ocr, positive=positive, negative=None
    )


# ---------------------------------------------------------------------------
# Ниже — тот же UI, что в app.py (рендеринг и скачивание результата)
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Анализ отзыва клиента (ДЕМО)", page_icon="📣", layout="centered")


def result_to_text(result: ReviewPipelineResult) -> str:
    """Собрать человекочитаемый текстовый отчёт по результату пайплайна."""
    lines = ["АНАЛИЗ ОТЗЫВА КЛИЕНТА (ДЕМО)", "=" * 40]
    c = result.classification
    lines.append(f"Тональность: {c.sentiment}")
    lines.append(f"Уверенность: {c.confidence:.2f}")
    lines.append(f"Главная эмоция: {c.key_emotion}")
    lines.append("")
    if result.ocr and result.ocr.review_text.strip():
        lines += ["РАСПОЗНАННЫЙ ТЕКСТ ОТЗЫВА", "-" * 40, result.ocr.review_text.strip(), ""]
    content = result.content
    if isinstance(content, PositiveContent):
        card = content.landing_card
        lines += [
            "КАРТОЧКА ДЛЯ ЛЕНДИНГА", "-" * 40,
            f"Заголовок: {card.headline}", f"Цитата: «{card.quote}»",
            f"Имя клиента: {card.customer_name}", "",
            "СТОРИС (3 СЛАЙДА)", "-" * 40,
        ]
        for s in content.story_slides:
            lines.append(f"Слайд {s.slide_number}: {s.text}")
        mc = content.mini_case
        lines += ["", "МИНИ-КЕЙС", "-" * 40, f"Who: {mc.who}", f"Problem: {mc.problem}",
                  f"Solution: {mc.solution}", f"Result: {mc.result}"]
    elif isinstance(content, NegativeResponse):
        lines += [
            "ОТВЕТ НА ОТРИЦАТЕЛЬНЫЙ ОТЗЫВ", "-" * 40,
            "1. Признание ситуации:", content.acknowledgment, "",
            "2. Предложение решения/компенсации:", content.solution_offer, "",
            "3. Благодарность:", content.gratitude, "",
            "ПОЛНЫЙ ТЕКСТ ОТВЕТА", "-" * 40, content.full_text,
        ]
    return "\n".join(lines)


def render_positive(content: PositiveContent) -> None:
    card = content.landing_card
    st.subheader("✅ Карточка для лендинга")
    st.markdown(f"**{card.headline}**\n\n> «{card.quote}»\n>\n> — **{card.customer_name}**")
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
        f"**Who:** {mc.who}\n\n**Problem:** {mc.problem}\n\n"
        f"**Solution:** {mc.solution}\n\n**Result:** {mc.result}"
    )


def render_negative(resp: NegativeResponse) -> None:
    st.subheader("💬 Ответ на отзыв")
    st.markdown(resp.full_text)
    with st.expander("Разбивка по трём частям"):
        st.markdown(f"**1. Признание ситуации**\n\n{resp.acknowledgment}")
        st.markdown(f"**2. Решение / компенсация**\n\n{resp.solution_offer}")
        st.markdown(f"**3. Благодарность**\n\n{resp.gratitude}")


def main() -> None:
    st.title("📣 Анализ отзыва клиента")
    st.warning(
        "Это ДЕМО-режим: ответы сгенерированы заглушкой без обращения к RouterAI. "
        "Для боевого запуска с реальными агентами используйте `streamlit run app.py` "
        "с заполненным `.env`.",
        icon="🧪",
    )
    st.caption(
        "Загрузите изображение отзыва (JPEG/PNG). Совет для проверки обеих веток: "
        "если в имени файла есть «neg» или «bad» (например, negativnyy_otzyv.png) — "
        "демо покажет негативную ветку, иначе — позитивную."
    )

    uploaded = st.file_uploader("Загрузите отзыв (JPEG/PNG)", type=["jpg", "jpeg", "png"])
    run_button = st.button("Обработать отзыв", type="primary", disabled=uploaded is None)

    if run_button and uploaded is not None:
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(uploaded.name)[1] or ".jpg"
        )
        tmp_path = tmp.name
        try:
            tmp.write(uploaded.getbuffer())
            tmp.close()
            with st.spinner("Агенты работают…"):
                st.session_state["result"] = fake_run_review(tmp_path)
            st.session_state["error"] = None
        except Exception as exc:
            st.session_state["result"] = None
            st.session_state["error"] = str(exc)
        finally:
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
