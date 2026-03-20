from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from ..core.database import get_db
from ..services.embeddings import embed
from ..services.claude import chat as claude_chat

router = APIRouter(prefix="/chat", tags=["chat"])


class Message(BaseModel):
    role: str  # user | assistant
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    # embed the latest user message for retrieval
    last_user = next(
        (m.content for m in reversed(req.messages) if m.role == "user"), ""
    )
    vec = embed(last_user)

    result = await db.execute(
        text(
            """
            SELECT id, title, raw_text, tags,
                   1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM entries
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
            """
        ),
        {"vec": str(vec), "k": req.top_k},
    )
    context_entries = [dict(row) for row in result.mappings().all()]

    answer = claude_chat(
        messages=[m.model_dump() for m in req.messages],
        context_entries=context_entries,
    )

    sources = [{"id": e["id"], "title": e["title"], "score": e["score"]} for e in context_entries]
    return ChatResponse(answer=answer, sources=sources)
