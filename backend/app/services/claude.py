import json
import anthropic
from ..core.config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_ENRICH_PROMPT = """You are helping organize a personal knowledge base.

Given the following text, return a JSON object with:
- "title": a concise, descriptive title (max 80 chars)
- "summary": a 2-3 sentence summary of the key points
- "tags": an array of 3-6 lowercase topic tags (single words or short phrases)

Return ONLY valid JSON, no markdown, no explanation.

Text:
{text}"""

_CHAT_SYSTEM = """You are a knowledgeable assistant with access to the user's personal notes and transcripts.
Answer questions based on the provided context. Be concise and direct.
If the context doesn't contain enough information, say so clearly.
Always ground your answers in the provided notes."""


def enrich_entry(text: str) -> dict:
    """Get title, summary, and tags for a piece of text."""
    truncated = text[:8000]  # stay well within token limits
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": _ENRICH_PROMPT.format(text=truncated)}],
    )
    return json.loads(response.content[0].text)


def chat(messages: list[dict], context_entries: list[dict]) -> str:
    """RAG chat: answer based on retrieved entries."""
    context_block = "\n\n---\n\n".join(
        f"[{e['title']}]\n{e['raw_text']}" for e in context_entries
    )
    system = _CHAT_SYSTEM + f"\n\n# Your notes:\n\n{context_block}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return response.content[0].text
