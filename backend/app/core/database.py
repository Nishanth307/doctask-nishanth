from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# pool_pre_ping=True
# If PostgreSQL disconnects after being idle, SQLAlchemy checks the connection before using it.
# Without it:connection already closed
# With it:SQLAlchemy reconnects automatically.

# expire_on_commit=False
# After db.commit() - you can still do user.id - without SQLAlchemy reloading the object.
# Almost every FastAPI project uses this.

# autoflush=False
# Flush only when necessary.
# This avoids lots of unexpected SQL queries.

# autocommit=False
# You decide when to commit.
# db.add(run)
# db.commit()
# instead of SQLAlchemy committing unexpectedly.
