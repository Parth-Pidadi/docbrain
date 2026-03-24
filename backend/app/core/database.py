from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Apply additive schema changes that create_all() misses on existing tables."""
    migrations = [
        # Add file_hash column for duplicate detection (idempotent)
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='documents' AND column_name='file_hash'
            ) THEN
                ALTER TABLE documents ADD COLUMN file_hash VARCHAR;
                CREATE INDEX IF NOT EXISTS ix_documents_file_hash ON documents (file_hash);
            END IF;
        END$$;
        """,
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            conn.execute(text(stmt))
        conn.commit()
