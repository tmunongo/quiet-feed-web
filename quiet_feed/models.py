import time
from uuid import uuid4

from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

DEFAULT_MODEL = "gemini-3.6-flash"
FALLBACK_MODELS = (DEFAULT_MODEL, "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-4-hydrogen")
PAID_MODELS = ("gemini-4-neon", "gemini-4-carbon", "gemini-4-argon")
MODELS = (*FALLBACK_MODELS, *PAID_MODELS)


def now():
    return int(time.time())


def identifier():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class SQLiteBoolean(TypeDecorator):
    """Keep Drizzle's INTEGER storage while exposing booleans to Python."""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else int(bool(value))

    def process_result_value(self, value, dialect):
        return None if value is None else bool(value)


class User(Base):
    __tablename__ = "user"
    __table_args__ = (Index("user_email_unique", "email", unique=True),)
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    email_verified: Mapped[bool] = mapped_column(
        SQLiteBoolean, default=False, server_default=text("0")
    )
    image: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    updated_at: Mapped[int] = mapped_column(Integer, default=now)


class LoginSession(Base):
    __tablename__ = "session"
    __table_args__ = (Index("session_token_unique", "token", unique=True),)
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=identifier)
    expires_at: Mapped[int] = mapped_column(Integer)
    token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    updated_at: Mapped[int] = mapped_column(Integer, default=now)
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))


class Account(Base):
    __tablename__ = "account"
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=identifier)
    account_id: Mapped[str] = mapped_column(Text)
    provider_id: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    access_token: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    id_token: Mapped[str | None] = mapped_column(Text)
    access_token_expires_at: Mapped[int | None] = mapped_column(Integer)
    refresh_token_expires_at: Mapped[int | None] = mapped_column(Integer)
    scope: Mapped[str | None] = mapped_column(Text)
    password: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    updated_at: Mapped[int] = mapped_column(Integer, default=now)


class Verification(Base):
    __tablename__ = "verification"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    identifier: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[int | None] = mapped_column(Integer)


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    edition_time: Mapped[str] = mapped_column(Text, default="07:00", server_default="07:00")
    timezone: Mapped[str] = mapped_column(Text, default="UTC", server_default="UTC")
    theme: Mapped[str] = mapped_column(Text, default="system", server_default="system")
    habits_mode: Mapped[bool] = mapped_column(
        SQLiteBoolean, default=False, server_default=text("0")
    )
    default_article_cap: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    edition_article_cap: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    last_edition_date: Mapped[str | None] = mapped_column(Text)
    collapsed_categories: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    gemini_api_key: Mapped[str | None] = mapped_column(Text)
    ai_model: Mapped[str] = mapped_column(Text, default=DEFAULT_MODEL, server_default=DEFAULT_MODEL)
    ai_digest_enabled: Mapped[bool] = mapped_column(
        SQLiteBoolean, default=False, server_default=text("0")
    )
    ai_digest_trigger: Mapped[str] = mapped_column(Text, default="manual", server_default="manual")


class Feed(Base):
    __tablename__ = "feeds"
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, default="General", server_default="General")
    article_cap: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_fetched_at: Mapped[int | None] = mapped_column(Integer)
    last_fetch_error: Mapped[str | None] = mapped_column(Text)
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, default=now)


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (Index("articles_feed_guid_unique", "feed_id", "guid", unique=True),)
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=identifier)
    feed_id: Mapped[str] = mapped_column(ForeignKey("feeds.id", ondelete="CASCADE"))
    guid: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    content_html: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[int] = mapped_column(Integer, default=now)


class Edition(Base):
    __tablename__ = "editions"
    __table_args__ = (Index("editions_user_date_unique", "user_id", "date", unique=True),)
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    date: Mapped[str] = mapped_column(Text)
    issue_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    closed_at: Mapped[int | None] = mapped_column(Integer)


class EditionArticle(Base):
    __tablename__ = "edition_articles"
    __table_args__ = (Index("edition_articles_unique", "edition_id", "article_id", unique=True),)
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=identifier)
    edition_id: Mapped[str] = mapped_column(ForeignKey("editions.id", ondelete="CASCADE"))
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    read: Mapped[bool] = mapped_column(SQLiteBoolean, default=False, server_default=text("0"))
    scroll_percent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    scroll_offset: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped[int | None] = mapped_column(Integer)


class EditionSummary(Base):
    __tablename__ = "edition_summaries"
    __table_args__ = (Index("edition_summaries_edition_id_unique", "edition_id", unique=True),)
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=identifier)
    edition_id: Mapped[str] = mapped_column(ForeignKey("editions.id", ondelete="CASCADE"))
    content_markdown: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="completed", server_default="completed")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, default=now)
