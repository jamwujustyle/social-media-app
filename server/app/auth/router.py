from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy import select
from app.user.models import User
from app.user.schemas import UserCreate, UserRead
from app.auth.schemas import LoginRequest, RefreshRequest, Token, VerifyRequest
from app.auth.service import AuthService
from app.auth.dependencies import get_auth_service
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (alias)",
    description="Registers a new user (alias for /register)",
)
@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user with an email and password. Upon successful registration, the user receives an 'unverified' status and a verification code is printed to the console.",
)
async def signup(
    user_in: UserCreate,
    service: AuthService = Depends(get_auth_service),
):
    return await service.register_user(user_in)


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticates user credentials and issues access and refresh JWT tokens.",
)
async def login(
    login_in: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.authenticate_user(login_in)


@router.post(
    "/refresh",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Generates a new access token using a valid refresh token.",
)
async def refresh(
    refresh_in: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.refresh_access_token(refresh_in)


@router.post(
    "/verify-email",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Verify user account (alias)",
    description="Verifies the user account (alias for /verify)",
)
@router.post(
    "/verify",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Verify user account",
    description="Verifies the user account using the 6-digit confirmation code printed to the console.",
)
async def verify(
    verify_in: VerifyRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.verify_user_code(verify_in)


@router.get(
    "/verify-email",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Verify user email via GET request",
    description="Verifies the user account using token/code via URL parameter.",
)
async def verify_email_get(
    token: str = Query(..., description="The 6-digit verification code or token"),
    email: Optional[str] = Query(None, description="The user email (optional if token is unique)"),
    service: AuthService = Depends(get_auth_service),
):
    if not email:
        # Try to find the user by verification code
        user_result = await service.db.execute(
            select(User).where(User.verification_code == token, User.is_verified == False)
        )
        user = user_result.scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code or user already verified.",
            )
        email = user.email

    return await service.verify_user_code(VerifyRequest(email=email, code=token))
