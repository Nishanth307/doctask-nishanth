from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import settings

_pool = None


def get_conn_string() -> str:
    """Return a libpq-style connection string (postgresql://) for psycopg_pool.

    Render injects DATABASE_URL as postgresql:// or postgres://.
    Locally we use postgresql+psycopg://.  Strip the SQLAlchemy driver suffix
    so psycopg_pool always receives the plain postgresql:// form.
    """
    url = settings.DATABASE_URL
    # Strip SQLAlchemy driver specifier if present (local dev)
    url = url.replace("postgresql+psycopg://", "postgresql://")
    # Normalise postgres:// → postgresql:// (Render sometimes uses the short form)
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=get_conn_string(),
            max_size=10,
            timeout=5.0,
            kwargs={"autocommit": True, "row_factory": dict_row},
        )
    return _pool


def create_checkpointer():
    if (
        "sqlite" in settings.DATABASE_URL
        or getattr(settings, "ENVIRONMENT", "") == "test"
        or "localhost" in settings.DATABASE_URL
        or "127.0.0.1" in settings.DATABASE_URL
    ):
        from langgraph.checkpoint.memory import MemorySaver
        saver = MemorySaver()
        if not hasattr(saver, "setup"):
            saver.setup = lambda: None
        return saver

    try:
        saver = PostgresSaver(get_pool())
        return saver
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver
        saver = MemorySaver()
        if not hasattr(saver, "setup"):
            saver.setup = lambda: None
        return saver