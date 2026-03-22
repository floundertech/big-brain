"""PII scrubbing for outbound API calls.

Uses Microsoft Presidio to detect and redact structured PII (SSN, driver's
license, credit card, etc.) before text is sent to external services like
the Claude API. Names and general text pass through untouched.

The spaCy model is loaded lazily on first call to avoid slowing startup
when PII scrubbing hasn't been triggered yet.
"""

import logging
from collections import Counter

from opentelemetry import trace as _otel_trace
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

logger = logging.getLogger("big-brain.pii")

# Only detect structured ID numbers — skip names, emails, phone numbers, etc.
_ENTITIES_TO_SCRUB = [
    "US_SSN",
    "US_DRIVER_LICENSE",
    "CREDIT_CARD",
    "US_PASSPORT",
    "US_BANK_NUMBER",
    "US_ITIN",
    "IBAN_CODE",
]

_analyzer: AnalyzerEngine | None = None
_anonymizer: AnonymizerEngine | None = None


def _get_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """Lazy-init Presidio engines (loads spaCy model on first call)."""
    global _analyzer, _anonymizer
    if _analyzer is None:
        logger.info("Initializing Presidio PII engines (first call)")
        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
    return _analyzer, _anonymizer


def scrub_pii(text: str, operation: str = "unknown") -> str:
    """Remove structured PII from text before sending to external APIs.

    Returns the text with detected PII replaced by type placeholders
    (e.g. ``<US_SSN>``, ``<CREDIT_CARD>``). Names are NOT scrubbed.

    Emits a ``security.pii.scrub.detections`` counter increment per entity
    type detected, tagged with ``operation``. Also adds a span event to the
    active OTel span for trace-level visibility in Dynatrace.
    """
    if not text:
        return text
    analyzer, anonymizer = _get_engines()
    results = analyzer.analyze(
        text=text,
        language="en",
        entities=_ENTITIES_TO_SCRUB,
        score_threshold=0.7,
    )
    if not results:
        return text

    scrubbed = anonymizer.anonymize(text=text, analyzer_results=results)

    # Aggregate by entity type so we emit one counter record per type.
    counts_by_type = Counter(r.entity_type for r in results)
    logger.info(
        "Scrubbed PII in operation=%s: %s",
        operation,
        dict(counts_by_type),
    )

    # Emit counter — one .add() per entity type so Dynatrace can split by type in DQL.
    from ..core.telemetry import get_pii_scrub_counter
    counter = get_pii_scrub_counter()
    if counter is not None:
        for entity_type, count in counts_by_type.items():
            counter.add(count, {"entity_type": entity_type, "operation": operation})

    # Span event for trace-level detail (visible in Dynatrace distributed tracing).
    span = _otel_trace.get_current_span()
    if span.is_recording():
        span.add_event(
            "pii.scrubbed",
            {
                "operation": operation,
                "entity_types": ",".join(counts_by_type.keys()),
                "total_detections": len(results),
            },
        )

    return scrubbed.text
