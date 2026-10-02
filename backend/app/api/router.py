from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models import User
from app.schemas.user import MeResponse

router = APIRouter()


@router.get("/me", response_model=MeResponse)
async def get_me(
    user: Annotated[User, Depends(get_current_user)],
) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
    )
