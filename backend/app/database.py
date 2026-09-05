"""
POLAR-AI Database Connection
SQLAlchemy 2.0 with PostGIS support via GeoAlchemy2.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import settings
from loguru import logger


# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Verify database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def check_postgis() -> bool:
    """Verify PostGIS extension is available."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT PostGIS_Version()"))
            version = result.scalar()
            logger.info(f"PostGIS version: {version}")
        return True
    except Exception as e:
        logger.warning(f"PostGIS not available: {e}")
        return False
