from uuid import UUID
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class CommentRead(BaseModel):
    id: UUID
    post_id: UUID
    author_id: UUID
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    content: str = Field(..., min_length=1, max_length=10000)


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    content: Optional[str] = Field(None, min_length=1, max_length=10000)


class PostRead(BaseModel):
    id: UUID
    author_id: UUID
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    comments: List[CommentRead] = []
    likes: List[UUID] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("likes", mode="before")
    @classmethod
    def serialize_likes(cls, v):
        if isinstance(v, list):
            return [like.user_id if hasattr(like, "user_id") else like for like in v]
        return v

    @property
    def like_count(self) -> int:
        return len(self.likes)


class LikeRead(BaseModel):
    user_id: UUID
    post_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPostsView(BaseModel):
    """Aggregated view of user with their posts and likes."""

    username: str
    posts: List[PostRead] = []

    model_config = ConfigDict(from_attributes=True)
