import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


@dataclass(frozen=True)
class Config:
    database_path: Path = field(default_factory=lambda: Path("data/quiet-feed.db"))
    secret: str = ""
    encryption_key: str = ""
    origin: str = "http://localhost:3000"
    secure_cookies: bool = False
    scheduler: bool = False
    cron_secret: str = ""
    version: str = VERSION
    commit: str = ""

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env")
        return cls(
            database_path=Path(os.getenv("DATABASE_PATH", "data/quiet-feed.db")),
            secret=os.getenv("BETTER_AUTH_SECRET", ""),
            encryption_key=os.getenv("ENCRYPTION_KEY", ""),
            origin=os.getenv("ORIGIN") or os.getenv("BETTER_AUTH_URL", "http://localhost:3000"),
            secure_cookies=os.getenv("SECURE_COOKIES", "false").lower() == "true",
            scheduler=os.getenv("ENABLE_INTERNAL_SCHEDULER", "false").lower() == "true",
            cron_secret=os.getenv("CRON_SECRET", ""),
            version=(os.getenv("APP_VERSION") or VERSION).removeprefix("v"),
            commit=os.getenv("COMMIT_HASH", "")[:12],
        )

    def validate(self):
        if (
            len(self.secret) < 32
            or self.secret == "quiet-feed-build-dummy-secret-at-least-32-chars"
        ):
            raise ValueError(
                "BETTER_AUTH_SECRET must be a stable random secret of at least 32 characters."
            )
        parsed = urlsplit(self.origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("ORIGIN (or BETTER_AUTH_URL) must be the public http(s) origin.")

    @property
    def public_origin(self):
        return self.origin.rstrip("/")
