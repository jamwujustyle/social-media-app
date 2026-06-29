import uuid
from typing import Optional, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_password_hash
from app.user.models import User
from app.user.schemas import UserUpdate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_id(self, user_id: Union[uuid.UUID, str]) -> Optional[User]:
        """Retrieve a user by their UUID."""
        if isinstance(user_id, str):
            try:
                user_id = uuid.UUID(user_id)
            except ValueError:
                return None
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieve a user by their email address."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update_user(self, db_user: User, user_in: UserUpdate) -> User:
        """Partially update user details, hashing the password if it is provided."""
        update_data = user_in.model_dump(exclude_unset=True)
        if "password" in update_data:
            update_data["password_hash"] = get_password_hash(
                update_data.pop("password")
            )

        for key, value in update_data.items():
            setattr(db_user, key, value)

        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user
