import pytest
from app.core.database import SessionLocal 

@pytest.fixture 
def db_session():
    session = SessionLocal()

    try:
        yield session
        session.rollback()
    finally: 
        session.close()