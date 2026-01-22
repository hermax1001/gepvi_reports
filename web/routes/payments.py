"""API роуты для работы с платежами"""
from fastapi import APIRouter, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import CreatePaymentRequest, CreatePaymentResponse
from app.services import create_yookassa_payment
from app.database import get_session
from app.utils.error_handler import handle_api_errors

router = APIRouter()


@router.post(
    "/create",
    response_model=CreatePaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Создать платеж для подписки"
)
@handle_api_errors
async def create_payment_endpoint(
    payment_request: CreatePaymentRequest,
    session: AsyncSession = Depends(get_session)
):
    """Создает платеж в ЮKassa для оформления подписки"""
    result = await create_yookassa_payment(
        session=session,
        user_id=str(payment_request.user_id),
        package_type=payment_request.package_type,
        return_url=payment_request.return_url,
        telegram_user_id=payment_request.telegram_user_id
    )

    # Извлекаем URL подтверждения
    confirmation_url = result.get("confirmation", {}).get("confirmation_url", "")

    return CreatePaymentResponse(
        payment_id=result.get("id", ""),
        confirmation_url=confirmation_url,
        amount=float(result.get("amount", {}).get("value", 0)),
        description=result.get("description", "")
    )
