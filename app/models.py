"""Relational schema. One session owns a profile, its dependents, the conversation, and every calculation."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    mode: Mapped[str] = mapped_column(String(16), default="quick")
    title: Mapped[str] = mapped_column(String(180), default="New plan")
    last_question_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active_scenario_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")

    profile: Mapped[ProfileRow | None] = relationship(back_populates="session", uselist=False, cascade="all, delete-orphan")
    messages: Mapped[list[MessageRow]] = relationship(back_populates="session", cascade="all, delete-orphan")
    calculations: Mapped[list[CalculationRow]] = relationship(back_populates="session", cascade="all, delete-orphan")
    scenarios: Mapped[list[ScenarioRow]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ProfileRow(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), unique=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    partner: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    annual_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    income_replacement_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    income_replacement_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    mortgage_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    mortgage_years_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    other_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    existing_employer_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    existing_personal_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    savings_allocated: Mapped[float | None] = mapped_column(Float, nullable=True)
    lifelong_legacy_goal: Mapped[float | None] = mapped_column(Float, nullable=True)
    other_needs: Mapped[float | None] = mapped_column(Float, nullable=True)
    include_education: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cash_value_interest: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dependents_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    monthly_budget_preference: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_sources: Mapped[dict] = mapped_column(JSON, default=dict)

    session: Mapped[SessionRow] = relationship(back_populates="profile")
    dependents: Mapped[list[DependentRow]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="DependentRow.position",
    )


class DependentRow(Base):
    __tablename__ = "dependents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(80), default="")
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education_goal: Mapped[float | None] = mapped_column(Float, nullable=True)
    education_is_estimate: Mapped[bool] = mapped_column(Boolean, default=False)

    profile: Mapped[ProfileRow] = relationship(back_populates="dependents")


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[SessionRow] = relationship(back_populates="messages")


class CalculationRow(Base):
    __tablename__ = "calculations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="base")
    label: Mapped[str] = mapped_column(String(160), default="Current plan")
    result: Mapped[dict] = mapped_column(JSON)
    engine_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    knowledge_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    assumption_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[SessionRow] = relationship(back_populates="calculations")


class ScenarioRow(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(160))
    note: Mapped[str] = mapped_column(Text, default="")
    patch: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    base_gap: Mapped[int] = mapped_column(Integer, default=0)
    scenario_gap: Mapped[int] = mapped_column(Integer, default=0)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[SessionRow] = relationship(back_populates="scenarios")


class KnowledgeRow(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("slug"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    slug: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(180))
    source_url: Mapped[str] = mapped_column(String(300))
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)


class MetaRow(Base):
    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
