from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_ingest import router as ingest_router, documents_router as docs_router
from app.api.routes_runs import router as runs_router
from app.core.logging import configure_logging, logger
from app.workflow.checkpointer import create_checkpointer

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cp = create_checkpointer()
    cp.setup()
    # Pre-warm the embedding model so it's in RAM before first request.
    # Without this, Render's 30-second proxy timeout triggers on the first
    # multipart upload while SentenceTransformer loads its weights.
    try:
        from app.services.providers.huggingface_embeddings import HuggingFaceEmbeddingService
        logger.info("pre_warming_embedding_model")
        _svc = HuggingFaceEmbeddingService()
        _svc.embed_text("warmup")
        logger.info("embedding_model_ready")
    except Exception as exc:
        logger.warning(f"embedding_warmup_failed: {exc}")
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


@app.get("/health")
def health():
    return {"status": "healthy"}
