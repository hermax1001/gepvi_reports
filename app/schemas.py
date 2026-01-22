"""Pydantic схемы для API"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator


class GetOrCreateUserRequest(BaseModel):
    """Запрос на получение или создание пользователя"""
    telegram_user_id: str
    timezone: Optional[str] = Field(default="Europe/Moscow", description="User timezone (IANA format)")


class UserResponse(BaseModel):
    """Ответ с данными пользователя"""
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    telegram_user_id: Optional[str]
    timezone: str
    yob: Optional[int]
    weight: Optional[float]
    gender: Optional[str]
    height: Optional[int]
    activity_level: Optional[float]
    subscription_expires_at: Optional[datetime]
    has_active_subscription: bool
    created_at: datetime
    updated_at: datetime


class UpdateUserRequest(BaseModel):
    """Запрос на обновление данных пользователя"""
    timezone: Optional[str] = Field(default=None, description="User timezone (IANA format)")
    yob: Optional[int] = Field(default=None, ge=1900, description="Year of birth (1900-current year)")
    weight: Optional[float] = Field(default=None, ge=20.0, le=500.0, description="Weight in kg (20-500)")
    gender: Optional[str] = Field(default=None, description="Gender (m or f)")
    height: Optional[int] = Field(default=None, ge=70, le=290, description="Height in cm (70-290)")
    activity_level: Optional[float] = Field(default=None, ge=1.0, le=3.0, description="Physical activity level (1.00-3.00)")

    @field_validator('yob')
    @classmethod
    def validate_yob(cls, v: Optional[int]) -> Optional[int]:
        """Validate year of birth is not in the future"""
        if v is not None:
            current_year = datetime.now().year
            if v > current_year:
                raise ValueError(f'Year of birth cannot be greater than current year ({current_year})')
        return v

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        """Validate gender is either m or f"""
        if v is not None and v not in ('m', 'f'):
            raise ValueError('Gender must be either "m" or "f"')
        return v

    @field_validator('weight')
    @classmethod
    def validate_weight_precision(cls, v: Optional[float]) -> Optional[float]:
        """Round weight to 1 decimal place"""
        if v is not None:
            return round(v, 1)
        return v

    @field_validator('activity_level')
    @classmethod
    def validate_activity_level_precision(cls, v: Optional[float]) -> Optional[float]:
        """Round activity_level to 2 decimal places"""
        if v is not None:
            return round(v, 2)
        return v


class WebhookResponse(BaseModel):
    """Ответ на вебхук"""
    success: bool = True


class CreatePaymentRequest(BaseModel):
    """Запрос на создание платежа"""
    user_id: UUID = Field(..., description="User UUID")
    telegram_user_id: Optional[str] = Field(None, description="Telegram user ID (optional)")
    package_type: str = Field(..., description="Тип подписки: monthly, quarterly, yearly")
    return_url: str = Field(..., description="URL для возврата после оплаты")


class CreatePaymentResponse(BaseModel):
    """Ответ на создание платежа"""
    payment_id: str
    confirmation_url: str
    amount: float
    description: str
