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
    auth_headers = {"Authorization": f"Api-Token {settings.dt_api_token}"}

    from traceloop.sdk import Traceloop
    Traceloop.init(
        app_name="big-brain",
        api_endpoint=settings.dt_otlp_endpoint,
        headers=auth_headers,
        disable_batch=False,
    )

    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry import metrics as _metrics

    exporter = OTLPMetricExporter(
        endpoint=f"{settings.dt_otlp_endpoint.rstrip('/')}/v1/metrics",
        headers=auth_headers,
    )
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60_000)
    _metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))


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
