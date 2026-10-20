import pytest

from app.plan import PlanError, parse_plan


PLAN = """
{
  "steps": [
    {"id": 1, "title": "Смысл страницы", "prompt": "Определи тему и интент страницы."},
    {"id": 2, "title": "Семантика", "prompt": "Собери кластеры поисковых запросов."},
    {"id": 3, "title": "Сниппет", "prompt": "Предложи title и description."},
    {"id": 4, "title": "Структура", "prompt": "Оцени заголовки H1-H3."},
    {"id": 5, "title": "Пробелы", "prompt": "Найди, каких блоков не хватает."}
  ]
}
"""


def test_parses_json_plan():
    steps = parse_plan(PLAN)
    assert len(steps) == 5
    assert steps[0].title == "Смысл страницы"
    assert "интент" in steps[0].prompt


def test_parses_fenced_json():
    raw = "```json\n" + PLAN + "\n```"
    assert len(parse_plan(raw)) == 5


def test_rejects_short_plan():
    raw = '{"steps":[{"title":"Один","prompt":"Сделай полный разбор страницы."}]}'
    with pytest.raises(PlanError):
        parse_plan(raw)
