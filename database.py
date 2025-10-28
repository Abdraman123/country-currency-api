"""
Database configuration and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Create database engine for MySQL
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,  # Changed from settings.DEBUG
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,  # Added
    max_overflow=20,  # Added
    connect_args={  # Added entire section
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30
    }
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for SQLAlchemy models
Base = declarative_base()


# Dependency to get database session
def get_db():
    """
    Database session dependency for FastAPI.
    Yields a session and closes it after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()