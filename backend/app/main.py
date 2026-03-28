import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.database import init_db
from .core.config import settings
from .services.embeddings import get_model
from .api import entries, search, chat, entities

logger = logging.getLogger("big-brain.telemetry")


def _init_tracing():
    if not settings.dt_otlp_endpoint or not settings.dt_api_token:
        return None
    auth_headers = {"Authorization": f"Api-Token {settings.dt_api_token}"}

    from traceloop.sdk import Traceloop
    Traceloop.init(
        app_name="big-brain",
        api_endpoint=settings.dt_otlp_endpoint,
        headers=auth_headers,
        disable_batch=False,
    )

    from opentelemetry.sdk.metrics import (
        MeterProvider,
        Counter,
        UpDownCounter,
        Histogram,
        ObservableCounter,
        ObservableUpDownCounter,
        ObservableGauge,
    )
    from opentelemetry.sdk.metrics.export import (
        AggregationTemporality,
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    # Enable OTel SDK logging so export errors are visible in container logs
    logging.getLogger("opentelemetry").setLevel(logging.DEBUG)

    metrics_endpoint = f"{settings.dt_otlp_endpoint.rstrip('/')}/v1/metrics"
    logger.warning("OTLP metrics endpoint: %s", metrics_endpoint)

    resource = Resource.create({SERVICE_NAME: "big-brain"})
    # Dynatrace requires DELTA temporality — it rejects CUMULATIVE (the OTel default) with 400.
    # Keys must be instrument classes, not strings.
    _delta = {
        Counter: AggregationTemporality.DELTA,
        UpDownCounter: AggregationTemporality.CUMULATIVE,
        Histogram: AggregationTemporality.DELTA,
        ObservableCounter: AggregationTemporality.DELTA,
        ObservableUpDownCounter: AggregationTemporality.CUMULATIVE,
        ObservableGauge: AggregationTemporality.CUMULATIVE,
    }
    otlp_exporter = OTLPMetricExporter(
        endpoint=metrics_endpoint,
        headers=auth_headers,
        preferred_temporality=_delta,
    )
    otlp_reader = PeriodicExportingMetricReader(otlp_exporter, export_interval_millis=15_000)
    # Console exporter dumps metric data to stdout — visible in `docker compose logs backend`
    console_reader = PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=15_000)
    provider = MeterProvider(resource=resource, metric_readers=[otlp_reader, console_reader])
    # Create the histogram directly from our owned provider — do NOT use the
    # global set_meter_provider() API, which Traceloop may override on first request.
    hist = provider.get_meter("big-brain.claude").create_histogram(
        "gen_ai.client.token.usage",
        unit="{token}",
        description="Number of tokens used in gen_ai API calls",
    )
    from .core.telemetry import set_token_usage_histogram, set_operation_duration_histogram, set_pii_scrub_counter
    set_token_usage_histogram(hist)
    dur_hist = provider.get_meter("big-brain.claude").create_histogram(
        "gen_ai.client.operation.duration",
        unit="s",
        description="Duration of gen_ai API calls in seconds",
    )
    set_operation_duration_histogram(dur_hist)
    pii_counter = provider.get_meter("big-brain.security").create_counter(
        "security.pii.scrub.detections",
        unit="{detection}",
        description="Number of PII entities scrubbed before outbound API calls, by entity type and operation",
    )
    set_pii_scrub_counter(pii_counter)
    logger.warning("MeterProvider initialized, histograms and counters registered")
    return provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    meter_provider = _init_tracing()
    await init_db()
    get_model()  # pre-load embedding model at startup to avoid OOM spike mid-request
    from .services.gmail import run_poller
    gmail_task = asyncio.create_task(run_poller())
    yield
    gmail_task.cancel()
    if meter_provider is not None:
        meter_provider.force_flush()
        meter_provider.shutdown()


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
