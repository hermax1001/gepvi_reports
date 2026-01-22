"""SQLModel для уведомлений"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, JSON
from sqlmodel import Field, SQLModel, Column


class Notification(SQLModel, table=True):
    """Уведомления для пользователей"""
    __tablename__ = "notifications"
    __table_args__ = (
        {"schema": "gepvi_reports"}
    )

    # Primary key
    id: int = Field(
        default=None,
        primary_key=True,
        description="Уникальный идентификатор уведомления"
    )

    # User reference
    user_id: UUID = Field(
        nullable=False,
        description="UUID пользователя"
    )

    # Notification details
    text: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Текст уведомления (опционально)"
    )

    sender_method: str = Field(
        nullable=False,
        description="Метод отправки (telegram/email/push)"
    )

    meta: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default='{}'),
        description="Дополнительные метаданные (JSONB)"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),
        description="Время создания записи"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)},
        description="Время последнего обновления"
    )
