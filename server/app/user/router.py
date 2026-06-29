import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth.dependencies import get_current_user, get_user_service
from app.user.models import User
from app.user.schemas import UserRead, UserUpdate
from app.user.service import UserService

router = APIRouter(tags=["Users"])


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns the profile information of the currently authenticated user.",
)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
    description="Allows the authenticated user to update their own profile data.",
)
async def update_current_user(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    # Check for email conflicts if changing email
    if user_in.email and user_in.email != current_user.email:
        conflict_user = await service.get_user_by_email(user_in.email)
        if conflict_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot update: this email is already in use by another account.",
            )

    return await service.update_user(current_user, user_in)
