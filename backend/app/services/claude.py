import json
import logging
import re
import asyncio
import time
import anthropic
from opentelemetry import trace as _otel_trace
from ..core.config import settings
from ..core.telemetry import get_token_usage_histogram, get_operation_duration_histogram
from .pii import scrub_pii

logger = logging.getLogger("big-brain.claude")

client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=120.0)


def _record_usage(response: anthropic.types.Message, operation: str, elapsed: float) -> None:
    """Attach gen_ai token-usage attributes to the current OTel span and emit
    gen_ai.client.token.usage and gen_ai.client.operation.duration histograms.

    Span attributes are no-op when no span is active. Histograms always emit
    as long as the MeterProvider is configured (the two are independent).
    Anthropic reports cached tokens separately; we sum all three buckets into
    gen_ai.usage.input_tokens per the OTel gen_ai semantic conventions.
    """
    usage = response.usage
    input_tokens = (
        usage.input_tokens
        + getattr(usage, "cache_read_input_tokens", 0)
        + getattr(usage, "cache_creation_input_tokens", 0)
    )
    span = _otel_trace.get_current_span()
    if span.is_recording():
        span.set_attribute("gen_ai.operation.name", operation)
        span.set_attribute("gen_ai.request.model", response.model)
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
        if response.stop_reason:
            span.set_attribute("gen_ai.response.finish_reasons", [response.stop_reason])
    attrs = {"gen_ai.operation.name": operation, "gen_ai.request.model": response.model}
    hist = get_token_usage_histogram()
    if hist is not None:
        hist.record(input_tokens, {**attrs, "gen_ai.token.type": "input"})
        hist.record(usage.output_tokens, {**attrs, "gen_ai.token.type": "output"})
    dur_hist = get_operation_duration_histogram()
    if dur_hist is not None:
        dur_hist.record(elapsed, attrs)
    logger.warning(
        "metrics.record: op=%s input=%d output=%d duration=%.3fs",
        operation, input_tokens, usage.output_tokens, elapsed,
    )


def _parse_json(text: str) -> dict:
    """Parse JSON from Claude response, stripping markdown code fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


_ENRICH_PROMPT = """You are helping organize a personal knowledge base.

Given the following text, return a JSON object with:
- "title": a concise, descriptive title (max 80 chars)
- "summary": a 2-3 sentence summary of the key points
- "tags": an array of 3-6 lowercase topic tags (single words or short phrases)

Return ONLY valid JSON, no markdown, no explanation.

Text:
{text}"""

_EXTRACT_ENTITIES_PROMPT = """You are helping build a personal knowledge graph.

Given the following text, return a JSON object with:
- "people": array of full names of people mentioned (strings)
- "organizations": array of organization/company names mentioned (strings)

Rules:
- Only include names that are clearly identifiable as a specific person or organization.
- Normalize names to title case.
- Return empty arrays if none found.
- Return ONLY valid JSON, no markdown, no explanation.

Text:
{text}"""

TOOLS = [
    {
        "name": "search_notes",
        "description": (
            "Search the user's personal knowledge base using semantic similarity. "
            "Use this for questions about what the user knows, discussed, met, or documented. "
            "Call this first before considering a web search."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_entity",
        "description": "Look up a specific person or organization in the knowledge base and see all entries mentioning them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the person or organization"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for current information not in the knowledge base. "
            "IMPORTANT: Before calling this tool, you MUST send a text message to the user "
            "explaining what you are about to search for and why. Only call this tool after "
            "the user has confirmed (e.g. replied 'yes', 'go ahead', 'sure', etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to fetch (1–5, default 3)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_entry",
        "description": (
            "Save information as a new entry in the knowledge base. "
            "IMPORTANT: Before calling this tool, you MUST send a text message showing the user "
            "the title and a 2-sentence summary of what you plan to save, and wait for their "
            "confirmation before calling this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Full text content to save"},
                "title": {"type": "string", "description": "Descriptive title for the entry"},
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of source URLs (for web research entries)",
                },
            },
            "required": ["text", "title"],
        },
    },
]

_AGENTIC_SYSTEM = """You are a knowledgeable assistant with access to the user's personal knowledge base and the web.

You have four tools:
- **search_notes**: searches the user's personal notes semantically. Use this liberally — it's fast and free.
- **get_entity**: looks up a specific person or organization and their linked notes.
- **web_search**: searches the web. Costs money. ALWAYS tell the user what you're going to search for and wait for their confirmation before calling this.
- **save_entry**: saves content to the knowledge base. ALWAYS show the user the title and a 2-sentence summary of what you'll save and wait for their confirmation before calling this.

For most questions: search_notes first, answer from the results.
For web research: ask for confirmation, then search, then optionally offer to save the results.
Be concise and direct."""


async def enrich_entry(text: str) -> dict:
    """Get title, summary, and tags for a piece of text."""
    truncated = scrub_pii(text[:8000])  # stay well within token limits
    t0 = time.perf_counter()
    response = await asyncio.to_thread(
        client.messages.create,
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": _ENRICH_PROMPT.format(text=truncated)}],
    )
    _record_usage(response, "enrich_entry", time.perf_counter() - t0)
    return _parse_json(response.content[0].text)


async def extract_entities(text: str) -> dict:
    """Return {"people": [...], "organizations": [...]} extracted from text."""
    truncated = scrub_pii(text[:8000])
    t0 = time.perf_counter()
    response = await asyncio.to_thread(
        client.messages.create,
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": _EXTRACT_ENTITIES_PROMPT.format(text=truncated)}],
    )
    _record_usage(response, "extract_entities", time.perf_counter() - t0)
    return _parse_json(response.content[0].text)


def chat_turn(messages: list[dict]) -> anthropic.types.Message:
    """Single Claude turn with tools. Returns the raw Message response."""
    t0 = time.perf_counter()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=_AGENTIC_SYSTEM,
        tools=TOOLS,
        messages=messages,
    )
    _record_usage(response, "chat_turn", time.perf_counter() - t0)
    return response
