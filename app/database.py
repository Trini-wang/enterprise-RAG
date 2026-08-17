import os
from pathlib import Path
from typing import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def database_url_from_path(database_path: str) -> str:
    if database_path == ":memory:":
        return "sqlite+pysqlite:///:memory:"
    return f"sqlite+pysqlite:///{Path(database_path).resolve().as_posix()}"


def default_database_url() -> str:
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        return configured_url
    default_path = Path(__file__).resolve().parent / "data" / "users.db"
    database_path = os.getenv("RAG_DATABASE_PATH", str(default_path))
    return database_url_from_path(database_path)


def create_database_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    options = {"poolclass": StaticPool} if database_url.endswith(":memory:") else {}
    return create_engine(database_url, connect_args=connect_args, **options)


DATABASE_URL = default_database_url()
if DATABASE_URL.startswith("sqlite") and not DATABASE_URL.endswith(":memory:"):
    database_file = DATABASE_URL.split("///", 1)[-1]
    Path(database_file).parent.mkdir(parents=True, exist_ok=True)

engine = create_database_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def init_db(target_engine: Engine = engine) -> None:
    # Import models before create_all so SQLAlchemy knows all metadata.
    from app.models import User  # noqa: F401

    Base.metadata.create_all(bind=target_engine)
