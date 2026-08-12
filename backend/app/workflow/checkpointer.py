from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import settings

_pool = None


def get_conn_string() -> str:
    return settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=get_conn_string(),
            max_size=10,
            kwargs={"autocommit": True, "row_factory": dict_row},
        )
    return _pool


def create_checkpointer() -> PostgresSaver:
    return PostgresSaver(get_pool())