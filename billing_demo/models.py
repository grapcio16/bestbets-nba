"""Only opaque session hashes and encrypted short-lived login transactions."""
from sqlalchemy import String, BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from billing_backend.db import Base


class WebSession(Base):
    __tablename__ = 'demo_web_sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey('billing_accounts.id'), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)


class LoginFlow(Base):
    __tablename__ = 'demo_login_flows'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('demo_web_sessions.id', ondelete='CASCADE'))
    encrypted: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)
