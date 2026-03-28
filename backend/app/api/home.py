from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..core.database import get_db
from ..services.rss import get_latest_digest

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/digest")
async def home_digest():
    """Latest digest (or yesterday's if today's not yet generated)."""
    digest = await get_latest_digest()
    if not digest:
        return {"digest": None, "note": "No digests generated yet."}
    return {"digest": digest}


@router.get("/activity")
async def home_activity(db: AsyncSession = Depends(get_db)):
    """Recent activity feed — last 10 items across all source types."""
    result = await db.execute(
        text("""
            SELECT id, title, source_type, summary, created_at
            FROM entries
            ORDER BY created_at DESC
            LIMIT 10
        """)
    )
    items = []
    for row in result.mappings().all():
        items.append({
            "id": row["id"],
            "title": row["title"],
            "source_type": row["source_type"],
            "summary": row["summary"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        })
    return {"items": items}


@router.get("/suggestions")
async def home_suggestions():
    """Recent chat queries for Quick Ask suggestions.

    Chat is stateless (no server-side session storage), so we return
    placeholder suggestions. The frontend can supplement these with
    locally stored recent queries.
    """
    return {
        "suggestions": [
            "What's new in Dynatrace this week?",
            "Summarize yesterday's digest",
            "Any flagged security articles?",
        ]
    }
