import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.user.models import User
from app.core.security import get_password_hash
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    """Test user registration."""
    payload = {
        "email": "user@example.com",
        "username": "johndoe",
        "full_name": "John Doe",
        "password": "securepassword123",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["email"] == "user@example.com"
    assert data["username"] == "johndoe"
    assert data["full_name"] == "John Doe"
    assert data["is_verified"] is False
    assert "id" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    """Test registration with an email that already exists."""
    payload = {
        "email": "duplicate@example.com",
        "username": "duplicate_user",
        "full_name": "Duplicate User",
        "password": "securepassword123",
    }
    # First signup
    res1 = await client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    # Second signup with same email
    payload_dup_email = {
        "email": "duplicate@example.com",
        "username": "other_user",
        "full_name": "Other User",
        "password": "securepassword123",
    }
    res2 = await client.post("/auth/register", json=payload_dup_email)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_verification_flow(client: AsyncClient):
    """Test user account verification flow using generated verification code."""
    # 1. Sign up user
    payload = {
        "email": "verify@example.com",
        "username": "verify_user",
        "full_name": "Verify User",
        "password": "securepassword123",
    }
    signup_res = await client.post("/auth/register", json=payload)
    assert signup_res.status_code == 201

    # 2. Retrieve the verification code from DB
    async with TestingSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == "verify@example.com")
        )
        user = result.scalar_one()
        code = user.verification_code
        assert code is not None

    # 3. Verify the user
    verify_payload = {
        "email": "verify@example.com",
        "code": code,
    }
    verify_res = await client.post("/auth/verify-email", json=verify_payload)
    assert verify_res.status_code == 200
    assert verify_res.json()["is_verified"] is True


@pytest.mark.asyncio
async def test_login_and_refresh(client: AsyncClient):
    """Test user login and token refresh flows."""
    # 1. Register & verify user
    payload = {
        "email": "auth@example.com",
        "username": "auth_user",
        "full_name": "Auth User",
        "password": "securepassword123",
    }
    await client.post("/auth/register", json=payload)

    async with TestingSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "auth@example.com"))
        user = result.scalar_one()
        user.is_verified = True
        await db.commit()

    # 2. Login
    login_payload = {
        "email": "auth@example.com",
        "password": "securepassword123",
    }
    login_res = await client.post("/auth/login", json=login_payload)
    assert login_res.status_code == 200

    tokens = login_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"

    # 3. Refresh Access Token
    refresh_payload = {
        "refresh_token": tokens["refresh_token"],
    }
    refresh_res = await client.post("/auth/refresh", json=refresh_payload)
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()


@pytest.mark.asyncio
async def test_unverified_users_cleanup():
    """Test automatic cleanup of unverified users created > 2 days ago."""
    from datetime import datetime, timezone, timedelta
    from app.tasks import async_cleanup_unverified_users

    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")

        # 1. Unverified user created 3 days ago (Should be deleted)
        old_unverified = User(
            email="old_unverified@example.com",
            username="old_unverified",
            full_name="Old Unverified",
            password_hash=user_pw,
            is_verified=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
        )

        # 2. Unverified user created recently (Should NOT be deleted)
        recent_unverified = User(
            email="recent_unverified@example.com",
            username="recent_unverified",
            full_name="Recent Unverified",
            password_hash=user_pw,
            is_verified=False,
            created_at=datetime.now(timezone.utc),
        )

        # 3. Verified user created 3 days ago (Should NOT be deleted)
        old_verified = User(
            email="old_verified@example.com",
            username="old_verified",
            full_name="Old Verified",
            password_hash=user_pw,
            is_verified=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
        )

        db.add_all([old_unverified, recent_unverified, old_verified])
        await db.commit()

    # Run the cleanup logic passing our testing db session
    async with TestingSessionLocal() as db:
        deleted_count = await async_cleanup_unverified_users(db)
        assert deleted_count == 1

    # Verify database state
    async with TestingSessionLocal() as db:
        # Check old_unverified is deleted
        result = await db.execute(
            select(User).where(User.email == "old_unverified@example.com")
        )
        assert result.scalar_one_or_none() is None

        # Check recent_unverified exists
        result = await db.execute(
            select(User).where(User.email == "recent_unverified@example.com")
        )
        assert result.scalar_one_or_none() is not None

        # Check old_verified exists
        result = await db.execute(
            select(User).where(User.email == "old_verified@example.com")
        )
        assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_login_with_username(client: AsyncClient):
    """Test user login using username instead of email."""
    # 1. Register & verify user
    payload = {
        "email": "user_user@example.com",
        "username": "user_user",
        "full_name": "User User",
        "password": "securepassword123",
    }
    await client.post("/auth/register", json=payload)

    async with TestingSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "user_user@example.com"))
        user = result.scalar_one()
        user.is_verified = True
        await db.commit()

    # 2. Login with username (using key "username")
    login_payload_username = {
        "username": "user_user",
        "password": "securepassword123",
    }
    login_res = await client.post("/auth/login", json=login_payload_username)
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
