import json
import re
from dataclasses import dataclass


class PlanError(ValueError):
    pass


@dataclass
class Step:
    id: int
    title: str
    prompt: str


def parse_plan(raw: str) -> list[Step]:
    data = _load_json(raw)
    rows = _step_rows(data)
    steps: list[Step] = []
    for index, row in enumerate(rows, start=1):
        if isinstance(row, str):
            prompt = row.strip()
            title = _short_title(prompt)
        elif isinstance(row, dict):
            prompt = _first(row, ("prompt", "text", "instruction", "query", "запрос", "промпт"))
            title = _first(row, ("title", "name", "step", "название", "заголовок")) or _short_title(prompt)
        else:
            raise PlanError("В плане встретился шаг без текста.")
        prompt = prompt.strip()
        title = title.strip() or f"Шаг {index}"
        if len(prompt) < 12:
            raise PlanError("Один из шагов плана пустой.")
        step_id = _step_id(row, index)
        steps.append(Step(id=step_id, title=title, prompt=prompt))

    if len(steps) < 5 or len(steps) > 6:
        raise PlanError(f"В плане {len(steps)} шагов, нужно 5 или 6.")
    return steps


def _load_json(raw: str):
    text = (raw or "").strip()
    if not text:
        raise PlanError("Модель вернула пустой план.")
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        list_start = text.find("[")
        list_end = text.rfind("]")
        if list_start != -1 and list_end > list_start:
            try:
                return json.loads(text[list_start : list_end + 1])
            except json.JSONDecodeError:
                pass
        raise PlanError("План пришёл не в JSON.") from exc


def _step_rows(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("steps", "plan", "prompts", "шаги", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    raise PlanError("В JSON нет списка шагов.")


def _first(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _step_id(row, fallback: int) -> int:
    if isinstance(row, dict):
        value = row.get("id", fallback)
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback
    return fallback


def _short_title(prompt: str) -> str:
    line = prompt.strip().splitlines()[0] if prompt.strip() else ""
    line = line.strip(" -—:")
    if len(line) > 90:
        return line[:87].rstrip() + "…"
    return line or "Шаг"
