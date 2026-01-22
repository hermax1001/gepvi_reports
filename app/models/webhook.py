"""Модель для сохранения входящих вебхуков"""
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import Index
from sqlmodel import SQLModel, Field, Column, JSON


class Webhook(SQLModel, table=True):
    """Модель для сохранения входящих вебхуков"""
    __tablename__ = "webhooks"

    __table_args__ = (
        Index("idx_webhooks_created_at", "created_at"),
        {"schema": "gepvi_users"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    provider_name: str = Field()
    webhook_payload: Dict[str, Any] = Field(sa_column=Column(JSON))
    response_code: Optional[int] = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow)
