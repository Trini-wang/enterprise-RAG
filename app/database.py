import os
from pathlib import Path
from typing import Generator

from sqlalchemy import Engine, create_engine, inspect
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
    from app.models import (  # noqa: F401
        AIModel, Conversation, Message, MessageCitation, MessageRun, ModelProvider,
        Prompt, PromptVersion, User,
    )

    # Preserve tables created by the early chat prototype, whose prompt schema
    # predates immutable prompt versions. SQLite create_all cannot alter them.
    if target_engine.dialect.name == "sqlite":
        inspector = inspect(target_engine)
        if "prompts" in inspector.get_table_names():
            prompt_columns = {column["name"] for column in inspector.get_columns("prompts")}
            if "status" not in prompt_columns:
                with target_engine.begin() as connection:
                    existing = set(inspector.get_table_names())
                    for table in ("messages", "conversations", "prompts"):
                        backup = f"{table}_legacy_chat_v0"
                        if table in existing and backup not in existing:
                            connection.exec_driver_sql(f'ALTER TABLE "{table}" RENAME TO "{backup}"')
        inspector = inspect(target_engine)
        if "model_providers" in inspector.get_table_names():
            provider_columns = {column["name"] for column in inspector.get_columns("model_providers")}
            if "api_key_encrypted" not in provider_columns:
                with target_engine.begin() as connection:
                    connection.exec_driver_sql("ALTER TABLE model_providers ADD COLUMN api_key_encrypted TEXT")
        inspector = inspect(target_engine)
        if "messages" in inspector.get_table_names():
            message_columns = {column["name"] for column in inspector.get_columns("messages")}
            if "sequence" not in message_columns:
                with target_engine.begin() as connection:
                    connection.exec_driver_sql("ALTER TABLE messages ADD COLUMN sequence INTEGER")
                    rows = connection.exec_driver_sql(
                        "SELECT rowid, conversation_id FROM messages ORDER BY conversation_id, created_at, rowid"
                    ).fetchall()
                    counters: dict[str, int] = {}
                    for rowid, conversation_id in rows:
                        counters[conversation_id] = counters.get(conversation_id, 0) + 1
                        connection.exec_driver_sql(
                            "UPDATE messages SET sequence = ? WHERE rowid = ?",
                            (counters[conversation_id], rowid),
                        )
        # SQLite keeps index names after a table rename. Remove only indexes
        # from the preserved legacy backups so the new tables can reuse the
        # conventional SQLAlchemy index names.
        with target_engine.begin() as connection:
            legacy_inspector = inspect(connection)
            for table in legacy_inspector.get_table_names():
                if table.endswith("_legacy_chat_v0"):
                    for index in legacy_inspector.get_indexes(table):
                        connection.exec_driver_sql(f'DROP INDEX IF EXISTS "{index["name"]}"')

    Base.metadata.create_all(bind=target_engine)
