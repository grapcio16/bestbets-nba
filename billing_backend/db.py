"""Durable account/billing records. No card data, raw JWT or webhook payloads."""
from contextlib import contextmanager
from sqlalchemy import (create_engine, event, String, Integer, BigInteger, Boolean, ForeignKey, UniqueConstraint, Index)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = 'billing_accounts'
    __table_args__ = (UniqueConstraint('issuer', 'subject'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(255))
    customer_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[int] = mapped_column(BigInteger)


class Entitlement(Base):
    __tablename__ = 'billing_entitlements'
    user_id: Mapped[str] = mapped_column(ForeignKey('billing_accounts.id'), primary_key=True)
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(48), default='free')
    paid_until: Mapped[int] = mapped_column(BigInteger, default=0)
    checked_at: Mapped[int] = mapped_column(BigInteger, default=0)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_id: Mapped[str | None] = mapped_column(String(128))


class Subscription(Base):
    __tablename__ = 'billing_subscriptions'
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('billing_accounts.id'), index=True)
    customer_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(48))
    price_id: Mapped[str] = mapped_column(String(128))
    paid_until: Mapped[int] = mapped_column(BigInteger)
    checked_at: Mapped[int] = mapped_column(BigInteger)


class CheckoutAttempt(Base):
    __tablename__ = 'billing_checkouts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('billing_accounts.id'), index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[int] = mapped_column(BigInteger)
    expires_at: Mapped[int] = mapped_column(BigInteger)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    terms_version: Mapped[str] = mapped_column(String(80))
    price_id: Mapped[str] = mapped_column(String(128))
    consent_at: Mapped[int] = mapped_column(BigInteger)


class EventReceipt(Base):
    __tablename__ = 'billing_events'
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(80))
    user_id: Mapped[str | None] = mapped_column(ForeignKey('billing_accounts.id'))
    outcome: Mapped[str] = mapped_column(String(32))
    processed_at: Mapped[int] = mapped_column(BigInteger)


Index('uq_billing_open_checkout', CheckoutAttempt.user_id, unique=True,
    postgresql_where=CheckoutAttempt.closed.is_(False), sqlite_where=CheckoutAttempt.closed.is_(False))


class RateBucket(Base):
    __tablename__ = 'billing_rate_limits'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(BigInteger)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(BigInteger)


class Database:
    def __init__(self, url):
        self.engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
        if self.engine.dialect.name == 'sqlite':
            @event.listens_for(self.engine, 'connect')
            def setup(connection, _):
                connection.isolation_level = None
                connection.execute('PRAGMA foreign_keys=ON')
                connection.execute('PRAGMA busy_timeout=15000')
            @event.listens_for(self.engine, 'begin')
            def begin(connection):
                # SQLite is explicitly local/test only; serialize its writers.
                connection.exec_driver_sql('BEGIN IMMEDIATE')
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def transaction(self):
        with self.sessions.begin() as session:
            yield session
