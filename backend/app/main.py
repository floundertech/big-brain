from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.database import init_db
from .services.embeddings import get_model


@asynccontextmanager
async def lifespan(app: FastAPI):
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
