"""PII scrubbing for outbound API calls.

Uses Microsoft Presidio to detect and redact structured PII (SSN, driver's
license, credit card, etc.) before text is sent to external services like
the Claude API. Names and general text pass through untouched.

The spaCy model is loaded lazily on first call to avoid slowing startup
when PII scrubbing hasn't been triggered yet.
"""

import logging

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


def scrub_pii(text: str) -> str:
    """Remove structured PII from text before sending to external APIs.

    Returns the text with detected PII replaced by type placeholders
    (e.g. ``<US_SSN>``, ``<CREDIT_CARD>``). Names are NOT scrubbed.
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
    logger.info("Scrubbed %d PII entities from outbound text", len(results))
    return scrubbed.text
