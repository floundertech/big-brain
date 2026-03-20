from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel
from datetime import datetime
from ..core.database import get_db
from ..core.models import Entry
from ..services.embeddings import embed

router = APIRouter(prefix="/search", tags=["search"])


class SearchResult(BaseModel):
    id: int
    created_at: datetime
    title: str
    source_type: str
    summary: str | None
    tags: list[str]
    score: float

    class Config:
        from_attributes = True


@router.get("/", response_model=list[SearchResult])
async def search(q: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    vec = embed(q)
    # cosine similarity via pgvector operator <=>
    result = await db.execute(
        text(
            """
            SELECT id, created_at, title, source_type, summary, tags,
                   1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM entries
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :limit
            """
        ),
        {"vec": str(vec), "limit": limit},
    )
    rows = result.mappings().all()
    return [SearchResult(**dict(row)) for row in rows]
