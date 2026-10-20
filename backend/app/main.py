import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.agent import run_analysis
from app.config import api_key, model_name

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Разработка SEO-ядра")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeIn(BaseModel):
    url: str


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "model": model_name(), "has_key": bool(api_key())}


@app.post("/api/analyze")
async def analyze(body: AnalyzeIn) -> StreamingResponse:
    async def events():
        try:
            async for event in run_analysis(body.url):
                payload = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: {event['event']}\ndata: {payload}\n\n"
        except Exception:
            logging.getLogger(__name__).exception("Поток анализа оборвался")
            payload = json.dumps(
                {"message": "Разбор прервался на сервере."},
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {payload}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


_frontend = Path(__file__).resolve().parents[2] / "frontend"
if (_frontend / "index.html").exists():
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="site")
