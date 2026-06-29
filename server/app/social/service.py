import uuid
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy import select, desc, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from fastapi import HTTPException, status
from app.social.models import Post, Comment, Like
from app.social.schemas import PostCreate, PostUpdate, CommentCreate
from app.logging_config import logger


class PostService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_post(self, author_id: uuid.UUID, post_in: PostCreate) -> Post:
        """Create a new post."""
        post = Post(
            author_id=author_id,
            title=post_in.title,
            content=post_in.content,
        )
        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        logger.info(f"Post created: {post.id} by author {author_id}")
        return post

    async def get_posts(
        self,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[List[Post], int]:
        """
        Get posts with pagination, search, and filtering.
        Returns tuple of (posts, total_count).
        """
        query = select(Post).options(
            joinedload(Post.comments),
            joinedload(Post.likes),
        )

        # Add search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Post.title.ilike(search_pattern),
                    Post.content.ilike(search_pattern),
                )
            )

        # Add date range filter
        if date_from:
            query = query.where(Post.created_at >= date_from)
        if date_to:
            query = query.where(Post.created_at <= date_to)

        # Get total count
        count_query = select(func.count(Post.id))
        if search:
            count_query = count_query.where(
                or_(
                    Post.title.ilike(search_pattern),
                    Post.content.ilike(search_pattern),
                )
            )
        if date_from:
            count_query = count_query.where(Post.created_at >= date_from)
        if date_to:
            count_query = count_query.where(Post.created_at <= date_to)

        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar() or 0

        # Apply ordering and pagination
        query = query.order_by(desc(Post.created_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.unique().scalars().all()), total_count

    async def get_post_by_id(self, post_id: uuid.UUID) -> Optional[Post]:
        """Get a post by ID with its comments and likes."""
        query = (
            select(Post)
            .where(Post.id == post_id)
            .options(
                joinedload(Post.comments),
                joinedload(Post.likes),
            )
        )
        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def update_post(
        self, post: Post, post_in: PostUpdate, current_user_id: uuid.UUID
    ) -> Post:
        """Update a post (only author can update)."""
        if post.author_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied. Only the post author can update this post.",
            )

        update_data = post_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(post, key, value)

        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        logger.info(f"Post updated: {post.id}")
        return post

    async def delete_post(self, post: Post, current_user_id: uuid.UUID) -> bool:
        """Delete a post (only author can delete)."""
        if post.author_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied. Only the post author can delete this post.",
            )

        await self.db.delete(post)
        await self.db.commit()
        logger.info(f"Post deleted: {post.id}")
        return True


class CommentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_comment(
        self, post_id: uuid.UUID, author_id: uuid.UUID, comment_in: CommentCreate
    ) -> Comment:
        """Create a new comment on a post."""
        # Verify post exists
        post_result = await self.db.execute(select(Post).where(Post.id == post_id))
        if not post_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found.",
            )

        comment = Comment(
            post_id=post_id,
            author_id=author_id,
            content=comment_in.content,
        )
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        logger.info(f"Comment created: {comment.id} on post {post_id}")
        return comment

    async def get_comment_by_id(self, comment_id: uuid.UUID) -> Optional[Comment]:
        """Get a comment by ID."""
        result = await self.db.execute(select(Comment).where(Comment.id == comment_id))
        return result.scalar_one_or_none()

    async def delete_comment(
        self, comment: Comment, current_user_id: uuid.UUID
    ) -> bool:
        """Delete a comment (only author can delete)."""
        if comment.author_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied. Only the comment author can delete this comment.",
            )

        await self.db.delete(comment)
        await self.db.commit()
        logger.info(f"Comment deleted: {comment.id}")
        return True


class LikeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_like(self, user_id: uuid.UUID, post_id: uuid.UUID) -> Like:
        """
        Add a like to a post.
        Rules: user cannot like their own post, one like per user per post.
        """
        # Get post to check author
        post_result = await self.db.execute(select(Post).where(Post.id == post_id))
        post = post_result.scalar_one_or_none()
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found.",
            )

        # Check if user is the author
        if post.author_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot like your own post.",
            )

        # Check if like already exists
        like_result = await self.db.execute(
            select(Like).where(and_(Like.user_id == user_id, Like.post_id == post_id))
        )
        if like_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already liked this post.",
            )

        like = Like(user_id=user_id, post_id=post_id)
        self.db.add(like)
        await self.db.commit()
        await self.db.refresh(like)
        logger.info(f"Like added: user {user_id} liked post {post_id}")
        return like

    async def remove_like(self, user_id: uuid.UUID, post_id: uuid.UUID) -> bool:
        """Remove a like from a post."""
        # Verify post exists
        post_result = await self.db.execute(select(Post).where(Post.id == post_id))
        if not post_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found.",
            )

        like_result = await self.db.execute(
            select(Like).where(and_(Like.user_id == user_id, Like.post_id == post_id))
        )
        like = like_result.scalar_one_or_none()
        if not like:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Like not found.",
            )

        await self.db.delete(like)
        await self.db.commit()
        logger.info(f"Like removed: user {user_id} unliked post {post_id}")
        return True

    async def get_likes_for_post(self, post_id: uuid.UUID) -> List[uuid.UUID]:
        """Get list of user IDs who liked a post."""
        result = await self.db.execute(
            select(Like.user_id).where(Like.post_id == post_id)
        )
        return list(result.scalars().all())
