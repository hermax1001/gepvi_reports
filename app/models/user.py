"""SQLModel для пользователей"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Numeric
from sqlmodel import Field, SQLModel, Index, Column


class User(SQLModel, table=True):
    """Пользователь системы. PK: id (UUID)"""
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_telegram_user_id", "telegram_user_id", unique=True),
        Index("idx_users_created_at", "created_at"),
        Index("idx_users_subscription_expires_at", "subscription_expires_at"),
        {"schema": "gepvi_users"}
    )

    # Primary key
    user_id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique user ID (UUID)"
    )

    # Optional Telegram integration
    telegram_user_id: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Telegram user ID (optional)"
    )

    # User preferences
    timezone: str = Field(
        default="Europe/Moscow",
        nullable=False,
        description="User timezone in IANA format (e.g., 'Europe/Moscow', 'UTC')"
    )

    # User profile fields
    yob: Optional[int] = Field(
        default=None,
        nullable=True,
        description="Year of birth (1900-current year)"
    )
    weight: Optional[float] = Field(
        default=None,
        sa_column=Column(Numeric(4, 1), nullable=True),
        description="Weight in kg (20-500, 1 decimal place)"
    )
    gender: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Gender (m or f)"
    )
    height: Optional[int] = Field(
        default=None,
        nullable=True,
        description="Height in cm (70-290)"
    )
    activity_level: Optional[float] = Field(
        default=None,
        sa_column=Column(Numeric(3, 2), nullable=True),
        description="Physical activity level coefficient (1.00-3.00, 2 decimal places)"
    )

    # Subscription fields
    subscription_expires_at: Optional[datetime] = Field(
        default=None,
        nullable=True,
        description="Дата окончания подписки"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        description="Record creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": datetime.utcnow},
        description="Record last update timestamp"
    )
