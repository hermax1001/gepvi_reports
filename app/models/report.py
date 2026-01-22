"""SQLModel для отчетов"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlmodel import Field, SQLModel, Index, Column


class Report(SQLModel, table=True):
    """Отчеты для пользователей"""
    __tablename__ = "reports"
    __table_args__ = (
        Index("idx_reports_user_id", "user_id"),
        {"schema": "gepvi_reports"}
    )

    # Primary key
    id: int = Field(
        default=None,
        primary_key=True,
        description="Уникальный идентификатор отчета"
    )

    # User reference
    user_id: UUID = Field(
        nullable=False,
        description="UUID пользователя"
    )

    # Report details
    report_type: str = Field(
        nullable=False,
        description="Тип отчета (day/week/month)"
    )

    result: str = Field(
        sa_column=Column(Text, nullable=False),
        description="Результат отчета (большой текст от AI модели)"
    )

    # Task reference
    task_id: int = Field(
        sa_column=Column(ForeignKey("gepvi_reports.tasks.id"), nullable=False),
        description="ID задачи, связанной с этим отчетом"
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
