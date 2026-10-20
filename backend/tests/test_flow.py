from fastapi.testclient import TestClient

from app.main import app

PLAN = """
{
  "steps": [
    {"id": 1, "title": "Смысл", "prompt": "Определи тему и интент страницы."},
    {"id": 2, "title": "Семантика", "prompt": "Собери кластеры поисковых запросов."},
    {"id": 3, "title": "Сниппет", "prompt": "Предложи title и description."},
    {"id": 4, "title": "Структура", "prompt": "Оцени заголовки H1-H3."},
    {"id": 5, "title": "Пробелы", "prompt": "Найди, каких блоков на странице не хватает."}
  ]
}
"""


def test_analyze_stream_without_internet(monkeypatch):
    seen = []

    async def no_internet():
        return False

    async def page(_url):
        return "URL: https://example.com\nTitle: Кухни\n" + ("текст страницы. " * 20)

    async def complete(messages, **kwargs):
        user = messages[-1]["content"]
        seen.append(user)
        if kwargs.get("json_mode"):
            return PLAN
        if "Промежуточные результаты" in user:
            return "## Тематика\nКухни на заказ"
        assert "текст страницы" in user
        return "Промежуточный вывод."

    monkeypatch.setattr("app.agent.assert_public_url", lambda url: url.strip())
    monkeypatch.setattr("app.agent.model_has_internet", no_internet)
    monkeypatch.setattr("app.agent.fetch_page_text", page)
    monkeypatch.setattr("app.agent.complete", complete)

    with TestClient(app) as client:
        response = client.post("/api/analyze", json={"url": "https://example.com/kuhni"})

    body = response.text
    assert response.status_code == 200
    assert "event: plan" in body
    assert "event: result" in body
    assert "Кухни на заказ" in body
    assert body.count("event: step") == 10
    assert "текст страницы" in seen[1]


def test_private_url_stops_before_model(monkeypatch):
    async def explode():
        raise AssertionError("модель не должна вызываться")

    monkeypatch.setattr("app.agent.model_has_internet", explode)

    with TestClient(app) as client:
        response = client.post("/api/analyze", json={"url": "http://127.0.0.1/admin"})

    assert "внутренний адрес" in response.text or "Локальные" in response.text
    assert "event: error" in response.text


def test_health():
    with TestClient(app) as client:
        payload = client.get("/api/health").json()
    assert payload["status"] == "ok"
    assert "has_key" in payload
