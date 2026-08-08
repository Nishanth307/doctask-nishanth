from fastapi import FastAPI

from app.api.routes_runs import router as runs_router
from app.core.logging import configure_logging, logger

configure_logging()

app = FastAPI(
    title="DocTask API",
    version="1.0.0",
)

app.include_router(runs_router, prefix="/api/v1")
logger.info("application_started")


@app.get("/health")
def health():
    return {"status": "healthy"}
