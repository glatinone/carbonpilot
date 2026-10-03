"""SQLAlchemy models.

Shape follows the hackathon spec: raw activity data is kept separate from
calculations so every emitted number is traceable back to
(activity x emission factor) with a citation.
"""

from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str] = mapped_column(String(8), default="WORLD")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Activity(Base):
    """One row of operational data (electricity, cloud, travel, fleet, ...)."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    date: Mapped[date_cls] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    activity_type: Mapped[str] = mapped_column(String(60), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(120), default="manual")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    calculation: Mapped["Calculation | None"] = relationship(
        back_populates="activity", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_activities_company_type_date", "company_id", "activity_type", "date"),
    )


class EmissionFactor(Base):
    __tablename__ = "emission_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_type: Mapped[str] = mapped_column(String(60), index=True)
    label: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), index=True)
    scope: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(String(30))
    region: Mapped[str] = mapped_column(String(8), default="WORLD")
    kg_co2e: Mapped[float] = mapped_column(Float)
    year: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text)
    uncertainty_pct: Mapped[float] = mapped_column(Float, default=20.0)

    __table_args__ = (
        UniqueConstraint("activity_type", "region", "unit", name="uq_factor_variant"),
    )


class Calculation(Base):
    """Result of activity x emission factor. This is the source of truth."""

    __tablename__ = "calculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), unique=True, index=True
    )
    emission_factor_id: Mapped[int] = mapped_column(ForeignKey("emission_factors.id"))
    co2e_kg: Mapped[float] = mapped_column(Float)
    scope: Mapped[int] = mapped_column(Integer)

    activity: Mapped[Activity] = relationship(back_populates="calculation")
    emission_factor: Mapped[EmissionFactor] = relationship()


class ScenarioRecord(Base):
    """A saved what-if simulation."""

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    interventions: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    constraint_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40))
    activity_type: Mapped[str] = mapped_column(String(60))
    carbon_impact_t: Mapped[float] = mapped_column(Float)
    cost_impact_usd: Mapped[float] = mapped_column(Float)
    effort: Mapped[str] = mapped_column(String(10))
    confidence_pct: Mapped[float] = mapped_column(Float)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ActionItem(Base):
    """An approved recommendation turned into an owner-assigned task."""

    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendations.id"), nullable=True
    )
    owner: Mapped[str] = mapped_column(String(120), default="Unassigned")
    task: Mapped[str] = mapped_column(Text)
    expected_carbon_t: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
