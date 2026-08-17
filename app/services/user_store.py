import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import (
    SessionLocal,
    create_database_engine,
    database_url_from_path,
    engine as default_engine,
    init_db,
)
from app.models import User


PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (TypeError, ValueError):
        return False


class UserStore:
    """SQLAlchemy-backed user repository.

    Passing a filesystem path creates an isolated SQLite engine, which is useful
    for tests. Without a path, the application-wide engine and session factory
    from ``app.database`` are reused.
    """

    def __init__(self, database_path: Optional[str] = None) -> None:
        if database_path is None:
            self.engine = default_engine
            self.session_factory = SessionLocal
        else:
            if database_path != ":memory:":
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)
            self.engine = create_database_engine(database_url_from_path(database_path))
            self.session_factory = sessionmaker(
                bind=self.engine, autoflush=False, expire_on_commit=False
            )
        self.initialize()

    def initialize(self) -> None:
        init_db(self.engine)

    @staticmethod
    def _public(user: User) -> dict[str, Any]:
        return user.to_dict()

    def create_user(
        self, email: str, password: str, full_name: str, role: Optional[str] = None
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            try:
                # An immediate SQLite transaction serializes the first-user admin decision.
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                if role is None:
                    count = session.scalar(select(func.count()).select_from(User)) or 0
                    role = "admin" if count == 0 else "user"
                user = User(
                    email=email.lower(),
                    full_name=full_name,
                    password_hash=hash_password(password),
                    role=role,
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                return self._public(user)
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("该邮箱已注册") from exc

    def authenticate(self, email: str, password: str) -> Optional[dict[str, Any]]:
        with self.session_factory() as session:
            user = session.scalar(select(User).where(User.email == email.lower()))
            if user is None or not user.is_active or not verify_password(password, user.password_hash):
                return None
            return self._public(user)

    def get_user(self, user_id: str) -> Optional[dict[str, Any]]:
        with self.session_factory() as session:
            user = session.get(User, user_id)
            return self._public(user) if user else None

    def list_users(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            users = session.scalars(select(User).order_by(User.created_at.desc())).all()
            return [self._public(user) for user in users]

    def update_user(self, user_id: str, changes: dict[str, Any]) -> Optional[dict[str, Any]]:
        with self.session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return None
            for field in ("full_name", "role", "is_active"):
                if changes.get(field) is not None:
                    setattr(user, field, changes[field])
            if changes.get("password") is not None:
                user.password_hash = hash_password(changes["password"])
            session.commit()
            session.refresh(user)
            return self._public(user)

    def delete_user(self, user_id: str) -> bool:
        with self.session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return False
            session.delete(user)
            session.commit()
            return True


user_store = UserStore()
