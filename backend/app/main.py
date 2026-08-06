from fastapi import FastAPI

from app.core.logging import configure_logging, logger

configure_logging()

app = FastAPI()
logger.info("application_started")
