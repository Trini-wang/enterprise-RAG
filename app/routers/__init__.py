from .docs import router as docs
from .query import router as query
from .auth import router as auth
from .files import router as files
from .users import router as users

__all__ = ["auth", "docs", "files", "query", "users"]
