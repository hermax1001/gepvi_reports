"""Модель истории изменения веса пользователя"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Index, Numeric
from sqlmodel import SQLModel, Field, Column


class WeightHistory(SQLModel, table=True):
    """История изменений веса пользователя"""
    __tablename__ = "weight_history"

    __table_args__ = (
        Index("idx_weight_history_user_id", "user_id"),
        Index("idx_weight_history_created_at", "created_at"),
        {"schema": "gepvi_users"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(nullable=False, description="User UUID")
    weight: float = Field(sa_column=Column(Numeric(4, 1)), description="Weight in kg (1 decimal place)")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
