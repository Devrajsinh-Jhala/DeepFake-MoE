from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import JSON, DateTime, String, Text, create_engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), index=True, default="pending")
    input_kind: Mapped[str] = mapped_column(String(16), default="upload")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    blob_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    _ensure_sqlite_parent(settings.database_url)
    Base.metadata.create_all(bind=engine)


def _ensure_sqlite_parent(database_url: str) -> None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def new_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(hours=get_settings().job_ttl_hours)


def cleanup_expired_rows(db: Session) -> list[str]:
    now = datetime.now(UTC)
    expired = db.query(AnalysisJob).filter(AnalysisJob.expires_at < now).all()
    blob_paths = [job.blob_path for job in expired if job.blob_path]
    db.execute(delete(AnalysisJob).where(AnalysisJob.expires_at < now).execution_options(synchronize_session=False))
    db.commit()
    return blob_paths
