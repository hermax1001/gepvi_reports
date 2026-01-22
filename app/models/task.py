"""SQLModel для задач"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel, Index


class Task(SQLModel, table=True):
    """Задачи для периодических джоб"""
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_user_id", "user_id"),
        Index("idx_tasks_next_task_time", "next_task_time"),
        {"schema": "gepvi_reports"}
    )

    # Primary key
    id: int = Field(
        default=None,
        primary_key=True,
        description="Уникальный идентификатор задачи"
    )

    # User reference
    user_id: UUID = Field(
        nullable=False,
        description="UUID пользователя"
    )

    # Task scheduling
    next_task_time: datetime = Field(
        nullable=False,
        sa_type=DateTime(timezone=True),
        description="Время следующего выполнения задачи"
    )

    period: str = Field(
        nullable=False,
        description="Период выполнения (day/week/month)"
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
