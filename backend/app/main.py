from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_ingest import router as ingest_router, documents_router as docs_router
from app.api.routes_runs import router as runs_router
from app.core.logging import configure_logging, logger
from app.workflow.checkpointer import create_checkpointer

import threading


def _warmup_embeddings():
    try:
        import os
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        import torch
        torch.set_num_threads(1)
        from sentence_transformers import SentenceTransformer
        from app.services.providers.huggingface_embeddings import _model_cache
        try:
            model = SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2", device="cpu", local_files_only=True
            )
        except Exception:
            model = SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2", device="cpu"
            )
        _model_cache["sentence-transformers/all-MiniLM-L6-v2"] = model
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    cp = create_checkpointer()
    try:
        cp.setup()
    except Exception:
        pass
    threading.Thread(target=_warmup_embeddings, daemon=True).start()
    yield


from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title="DocTask API",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(docs_router, prefix="/api/v1")
logger.info("application_started")


@app.get("/")
@app.head("/")
def root():
    return {"status": "ok", "message": "DocTask API is running"}


@app.get("/health")
@app.head("/health")
def health():
    return {"status": "healthy"}
