from datetime import date
from fastapi import APIRouter, HTTPException
from ..services.rss import poll_once, get_status, generate_daily_digest, get_latest_digest, get_digest_by_date

router = APIRouter(prefix="/rss", tags=["rss"])


@router.get("/status")
async def rss_status():
    """Current RSS polling status, last poll time, article/digest counts."""
    return await get_status()


@router.post("/poll")
async def rss_poll():
    """Manually trigger a Miniflux poll cycle (for testing)."""
    stats = await poll_once()
    return stats


@router.get("/digest/latest")
async def digest_latest():
    """Most recent digest entry."""
    digest = await get_latest_digest()
    if not digest:
        raise HTTPException(status_code=404, detail="No digest found")
    return digest


@router.get("/digest/{date_str}")
async def digest_by_date(date_str: str):
    """Digest for a specific date (YYYY-MM-DD)."""
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
    digest = await get_digest_by_date(target)
    if not digest:
        raise HTTPException(status_code=404, detail=f"No digest for {date_str}")
    return digest


@router.post("/digest/generate")
async def digest_generate(date_str: str | None = None):
    """Manually trigger digest generation (for testing). Defaults to yesterday."""
    target = None
    if date_str:
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
    result = await generate_daily_digest(target)
    if not result:
        return {"status": "skipped", "reason": "No articles for the target date"}
    return result
