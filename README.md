# 📣 Анализ отзыва клиента (CrewAI + RouterAI + Streamlit)

Локальное веб-приложение: вы загружаете **изображение отзыва клиента** (скриншот или фото, JPEG/PNG),
а мультиагентная система на CrewAI распознаёт текст, определяет тональность и:

- **позитивный отзыв** → генерирует три формата контента для соцсетей:
  карточку для лендинга, сторис из трёх слайдов и мини-кейс (до 500 символов);
- **негативный отзыв** → пишет корректный живой ответ: признание ситуации →
  конкретное решение/компенсация → благодарность.

Результат отображается на странице и скачивается в **JSON** и **TXT**.

## Как работает (схема)

```
Изображение отзыва (JPEG/PNG)
        │
        ▼
[ocr_agent]  — OCRTool + vision-модель RouterAI → OcrResult (текст, имя, оценка)
        │
        ▼
[classifier_agent] → ReviewClassification (sentiment, confidence, key_emotion)
        │
        ▼  ConditionalTask (Process.sequential)
   ┌────┴─────────────────────┐
   │ sentiment == positive    │ sentiment == negative
   ▼                          ▼
[positive_creator_agent]   [negative_responder_agent]
PositiveContent            NegativeResponse
(карточка + сторис +       (признание + решение +
 мини-кейс)                 благодарность + full_text)
        │                          │
        └───────────┬──────────────┘
                    ▼
        Streamlit-страница: блоки результата
        + кнопки скачивания JSON / TXT
```

Всё выполняется локально на вашей машине; единственная внешняя зависимость —
API RouterAI. Веб-фронтенда нет: интерфейс — один файл `app.py` на Streamlit.

## Структура проекта

```
review_crew/
├── .env.example              # шаблон переменных окружения (коммитится)
├── .gitignore                # .env исключён из Git
├── requirements.txt
├── README.md
├── app.py                    # Streamlit-приложение (точка входа)
├── src/
│   └── review_crew/
│       ├── __init__.py
│       ├── config.py         # загрузка .env + fail-fast проверка ключа
│       ├── llm_factory.py    # RouterAI-фабрика: get_text_llm / get_vision_llm
│       ├── models.py         # Pydantic-модели выходов (output_pydantic)
│       ├── agents.py         # ocr_agent, classifier_agent, positive_creator_agent, negative_responder_agent
│       ├── tasks.py          # задачи + условия для ConditionalTask
│       └── crew.py           # сборка Crew и run_review(image_path)
└── examples/                 # сюда положите файл отзыва для теста
```

## Быстрый старт

Нужен **Python 3.10–3.13**.

```bash
# 1. Виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Зависимости
pip install -r requirements.txt

# 3. Настройка ключа
cp .env.example .env
# откройте .env и вставьте реальный ROUTERAI_API_KEY

# 4. Запуск сайта
streamlit run app.py
```

Откройте адрес из вывода Streamlit — обычно **http://localhost:8501**.
Положите изображение отзыва в `examples/` или загрузите его прямо через интерфейс.

## Настройка RouterAI

Проект работает **только через RouterAI** (https://routerai.ru) — OpenAI-совместимый
агрегатор моделей с оплатой в рублях и стабильным доступом из РФ. Прямых интеграций
с OpenAI, Gemini, Groq, OpenRouter или Ollama здесь нет.

1. **Регистрация**: создайте аккаунт на https://routerai.ru.
2. **API-ключ**: сгенерируйте ключ в разделе настроек личного кабинета.
3. **Баланс**: RouterAI работает по предоплате (оплата в рублях), бесплатного тарифа нет —
   пополните баланс перед первым запуском.
4. **Модели** (задаются в `.env`, без префикса `openai/` — фабрика добавит его сама):

   | Переменная             | Назначение                     | Пример значения              |
   |------------------------|--------------------------------|------------------------------|
   | `ROUTERAI_VISION_MODEL`| OCR (нужно зрение)             | `google/gemma-3-27b-it`      |
   |                        | дешёвая альтернатива для OCR   | `qwen/qwen3.7-flash`         |
   | `ROUTERAI_TEXT_MODEL`  | классификация и генерация      | `openai/gpt-6.1-sol`         |
   |                        | бюджетный текстовый вариант    | `deepseek/deepseek-v4-pro`   |

Технические детали подключения: `base_url` строго `https://routerai.ru/api/v1`,
в поле `model` обязателен префикс `openai/` — он переключает LiteLLM (внутренний
движок CrewAI) на OpenAI-совместимый протокол. Всё это делает `src/review_crew/llm_factory.py`.

### Самопроверка ключа (без приложения)

```python
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_API_KEY",              # только для проверки в консоли, не сохраняйте ключ в файлах проекта
    base_url="https://routerai.ru/api/v1",
)
response = client.chat.completions.create(
    model="openai/openai/gpt-6.1-sol",
    messages=[{"role": "user", "content": "Привет!"}],
)
print(response.choices[0].message.content)
```

Если ответ получен — ключ и баланс рабочие.

## 🔐 Безопасность ключа

- Ключ хранится **только** в файле `.env` в корне проекта (локально).
- `.env` и все `.env.*` исключены из Git (см. `.gitignore`); в репозиторий попадает
  только шаблон `.env.example` без секретов.
- Ключ читается исключительно через `python-dotenv` в `config.py` / `llm_factory.py`
  (`os.getenv("ROUTERAI_API_KEY")`). **Никакого хардкода и значений по умолчанию.**
- Fail-fast: если ключ не задан, приложение падает при старте с понятным сообщением,
  а не пытается работать с пустым ключом.
- В Streamlit ключ **никогда** не передаётся во фронтенд, не отображается в интерфейсе
  и не пишется в логи.
- ⚠️ **При утечке ключа немедленно отзовите его в личном кабинете RouterAI и выпустите новый.**

## Почему Process.sequential + ConditionalTask

Развилка в задаче **бинарная** (positive / negative) и определяется одним полем одной
предыдущей задачи. Иерархический процесс (`Process.hierarchical`) требует агента-менеджера,
который бы «планировал» и выбирал ветку — это лишние вызовы LLM, дополнительные стоимость
и задержка, плюс недетерминированность. `ConditionalTask` внутри sequential-процесса
выбирает ветку кодом (по `sentiment` из вывода классификатора): вторая ветка просто
пропускается и не расходует токены. Результат — минимальная цена прогона и предсказуемое
поведение.

## Известные ограничения

- **Качество OCR зависит от vision-модели.** Для плохих фото/скриншотов выберите более
  сильную мультимодальную модель в `ROUTERAI_VISION_MODEL`.
- **У RouterAI нет бесплатного тарифа.** Если стоимость критична, используйте более
  дешёвые модели: `qwen/qwen3.7-flash` (vision) и `deepseek/deepseek-v4-pro` (текст).
- **Мини-кейс иногда превышает 500 символов.** Жёсткую проверку длины можно добавить
  через guardrail CrewAI (`guardrail=` у Task), возвращающий ошибку при переполнении.

## Как расширять

- **Новый агент/формат**: добавьте `build_*_agent()` в `agents.py`, задачу в `tasks.py`
  (при необходимости ещё один `ConditionalTask`) и Pydantic-модель в `models.py`.
- **Смена формата вывода**: правьте модели в `models.py` и их Field-описания — промпты
  задач подхватят схему автоматически через `output_pydantic`.
- **Guardrail для мини-кейса**: функция-валидатор, проверяющая суммарную длину
  who/problem/solution/result ≤ 500 символов, подключается параметром `guardrail` задачи.
- **Другой фронтенд**: `run_review(image_path)` — чистая функция-граница
  (единственная точка входа в crew); её можно вызвать
  из FastAPI-эндпоинта и отдать результат React-приложению, не трогая crew.

## Как проверить

```bash
# 1. Окружение активно, зависимости установлены
source .venv/bin/activate && pip install -r requirements.txt

# 2. .env создан и содержит РЕАЛЬНЫЙ ключ (не плейсхолдер)
grep ROUTERAI_API_KEY .env

# 3. Самопроверка ключа RouterAI (код из раздела «Настройка RouterAI» выше):
python - <<'PY'
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ["ROUTERAI_API_KEY"],
                base_url="https://routerai.ru/api/v1")
r = client.chat.completions.create(
    model="openai/openai/gpt-6.1-sol",
    messages=[{"role": "user", "content": "Привет!"}],
)
print(r.choices[0].message.content)
PY

# 4. Проверка импортов приложения (без запуска crew)
python -c "import sys; sys.path.insert(0,'src'); import review_crew.crew, review_crew.tasks, review_crew.agents; print('OK')"

# 5. Запуск сайта
streamlit run app.py
# → откройте http://localhost:8501, загрузите JPEG/PNG с отзывом,
#   нажмите «Обработать отзыв», дождитесь результата и проверьте
#   кнопки скачивания JSON/TXT.
```

Ожидаемое поведение при ошибочном ключе: приложение сразу выдаёт понятную ошибку
(`st.error`) с подсказкой проверить `.env` и баланс RouterAI.
