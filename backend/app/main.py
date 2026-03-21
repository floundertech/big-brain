from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.database import init_db
from .core.config import settings
from .services.embeddings import get_model
from .api import entries, search, chat, entities


def _init_tracing():
    if not settings.dt_otlp_endpoint or not settings.dt_api_token:
        return
    from traceloop.sdk import Traceloop
    Traceloop.init(
        app_name="big-brain",
        api_endpoint=settings.dt_otlp_endpoint,
        headers={"Authorization": f"Api-Token {settings.dt_api_token}"},
        disable_batch=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_tracing()
    await init_db()
    get_model()  # pre-load embedding model at startup to avoid OOM spike mid-request
    yield


app = FastAPI(title="Big Brain API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(entries.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(entities.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
