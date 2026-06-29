import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.auth.dependencies import get_current_user, get_current_active_user
from app.user.models import User
from app.social.schemas import (
    PostCreate,
    PostRead,
    PostUpdate,
    CommentCreate,
    CommentRead,
    LikeRead,
    UserPostsView,
)
from app.social.service import PostService, CommentService, LikeService
from app.logging_config import logger

router = APIRouter(prefix="/posts", tags=["Posts"])


# Dependency providers
async def get_post_service(db: AsyncSession = Depends(get_db)) -> PostService:
    return PostService(db)


async def get_comment_service(db: AsyncSession = Depends(get_db)) -> CommentService:
    return CommentService(db)


async def get_like_service(db: AsyncSession = Depends(get_db)) -> LikeService:
    return LikeService(db)


# ────────────────────────────────────────────────────────────────
# POST ENDPOINTS
# ────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=List[PostRead],
    status_code=status.HTTP_200_OK,
    summary="List posts",
    description="Returns a paginated list of posts with optional search and date filtering.",
)
async def list_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, max_length=255),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    service: PostService = Depends(get_post_service),
):
    posts, _ = await service.get_posts(
        skip=skip,
        limit=limit,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )
    return posts


@router.post(
    "",
    response_model=PostRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a post",
    description="Creates a new post. Only verified users can create posts.",
)
async def create_post(
    post_in: PostCreate,
    current_user: User = Depends(get_current_active_user),
    service: PostService = Depends(get_post_service),
):
    post = await service.create_post(current_user.id, post_in)
    return post


@router.get(
    "/{post_id}",
    response_model=PostRead,
    status_code=status.HTTP_200_OK,
    summary="Get post details",
    description="Returns a post with all its comments and likes.",
)
async def get_post(
    post_id: uuid.UUID,
    service: PostService = Depends(get_post_service),
):
    post = await service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    return post


@router.patch(
    "/{post_id}",
    response_model=PostRead,
    status_code=status.HTTP_200_OK,
    summary="Update a post",
    description="Updates a post. Only the post author can update.",
)
async def update_post(
    post_id: uuid.UUID,
    post_in: PostUpdate,
    current_user: User = Depends(get_current_active_user),
    service: PostService = Depends(get_post_service),
):
    post = await service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    return await service.update_post(post, post_in, current_user.id)


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a post",
    description="Deletes a post. Only the post author can delete.",
)
async def delete_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    service: PostService = Depends(get_post_service),
):
    post = await service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    await service.delete_post(post, current_user.id)
    return None


# ────────────────────────────────────────────────────────────────
# COMMENT ENDPOINTS
# ────────────────────────────────────────────────────────────────


@router.post(
    "/{post_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment",
    description="Creates a comment on a post. Only verified users can comment.",
)
async def create_comment(
    post_id: uuid.UUID,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    service: CommentService = Depends(get_comment_service),
):
    comment = await service.create_comment(post_id, current_user.id, comment_in)
    return comment


@router.delete(
    "/{post_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
    description="Deletes a comment. Only the comment author can delete.",
)
async def delete_comment(
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    service: CommentService = Depends(get_comment_service),
):
    comment = await service.get_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found.",
        )
    if comment.post_id != post_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found on this post.",
        )
    await service.delete_comment(comment, current_user.id)
    return None


# ────────────────────────────────────────────────────────────────
# LIKE ENDPOINTS
# ────────────────────────────────────────────────────────────────


@router.post(
    "/{post_id}/like",
    response_model=LikeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Like a post",
    description="Likes a post. Users cannot like their own posts and can only like once.",
)
async def like_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: LikeService = Depends(get_like_service),
):
    like = await service.add_like(current_user.id, post_id)
    return like


@router.delete(
    "/{post_id}/like",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlike a post",
    description="Removes a like from a post.",
)
async def unlike_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: LikeService = Depends(get_like_service),
):
    await service.remove_like(current_user.id, post_id)
    return None


# ────────────────────────────────────────────────────────────────
# FEED ENDPOINT (aggregated view)
# ────────────────────────────────────────────────────────────────


@router.get(
    "/all/feed",
    response_model=List[UserPostsView],
    status_code=status.HTTP_200_OK,
    summary="Get feed (all users and posts)",
    description="Returns all users with their posts and likes. Supports pagination, search, and filtering.",
)
async def get_feed(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, max_length=255),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # Get all posts with filtering
    post_service = PostService(db)
    posts, _ = await post_service.get_posts(
        skip=skip,
        limit=limit,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )

    # Group posts by author (user)
    user_posts_map: dict[uuid.UUID, List[Post]] = {}
    for post in posts:
        user_posts_map.setdefault(post.author_id, []).append(post)

    # Fetch user details
    author_ids = list(user_posts_map.keys())
    if author_ids:
        user_result = await db.execute(select(User).where(User.id.in_(author_ids)))
        users = user_result.scalars().all()
        users_by_id = {user.id: user for user in users}
    else:
        users_by_id = {}

    # Build response
    response = []
    seen_authors = set()
    for post in posts:
        author_id = post.author_id
        if author_id in users_by_id and author_id not in seen_authors:
            seen_authors.add(author_id)
            user = users_by_id[author_id]
            response.append(
                UserPostsView(
                    username=user.username,
                    posts=user_posts_map[author_id],
                )
            )

    return response
