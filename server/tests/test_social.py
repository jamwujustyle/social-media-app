import pytest
from httpx import AsyncClient
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from app.user.models import User
from app.social.models import Post, Comment, Like
from app.core.security import get_password_hash
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_create_post_success(client: AsyncClient):
    """Test creating a post as a verified user."""
    # Setup: Create and verify a user
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        user = User(
            email="poster@example.com",
            username="poster",
            full_name="Poster User",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    # Login to get token
    login_res = await client.post(
        "/auth/login",
        json={"email": "poster@example.com", "password": "password123"},
    )
    access_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Create post
    post_data = {
        "title": "Hello World",
        "content": "This is my first post on the social network!",
    }
    response = await client.post("/posts", json=post_data, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Hello World"
    assert data["content"] == "This is my first post on the social network!"
    assert data["author_id"] == str(user_id)
    assert len(data["comments"]) == 0
    assert len(data["likes"]) == 0


@pytest.mark.asyncio
async def test_create_post_unverified_forbidden(client: AsyncClient):
    """Test that unverified users cannot create posts."""
    # Setup: Create unverified user
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        user = User(
            email="unverified@example.com",
            username="unverified",
            full_name="Unverified User",
            password_hash=user_pw,
            is_verified=False,
        )
        db.add(user)
        await db.commit()

    # Login to get token
    login_res = await client.post(
        "/auth/login",
        json={"email": "unverified@example.com", "password": "password123"},
    )
    access_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Try to create post
    post_data = {"title": "Test", "content": "Test content"}
    response = await client.post("/posts", json=post_data, headers=headers)
    assert response.status_code == 403
    assert "not verified" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_posts_with_pagination(client: AsyncClient):
    """Test listing posts with pagination."""
    # Setup: Create multiple posts
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        user = User(
            email="lister@example.com",
            username="lister",
            full_name="Lister User",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Create 5 posts
        for i in range(5):
            post = Post(
                author_id=user.id,
                title=f"Post {i+1}",
                content=f"Content {i+1}",
            )
            db.add(post)
        await db.commit()

    # List with default pagination
    response = await client.get("/posts?skip=0&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # List with offset
    response = await client.get("/posts?skip=2&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_posts_with_search(client: AsyncClient):
    """Test listing posts with search filtering."""
    # Setup: Create posts with different titles
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        user = User(
            email="searcher@example.com",
            username="searcher",
            full_name="Searcher User",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        post1 = Post(author_id=user.id, title="Rust Programming", content="Learn Rust")
        post2 = Post(author_id=user.id, title="Python Tutorial", content="Learn Python")
        db.add(post1)
        db.add(post2)
        await db.commit()

    # Search for "Rust"
    response = await client.get("/posts?search=Rust")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any("Rust" in p["title"] for p in data)


@pytest.mark.asyncio
async def test_get_post_details(client: AsyncClient):
    """Test getting post details with comments."""
    # Setup: Create post with comment
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        user = User(
            email="detail@example.com",
            username="detail",
            full_name="Detail User",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        post = Post(
            author_id=user.id,
            title="Test Post",
            content="Test content",
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)

        comment = Comment(
            post_id=post.id,
            author_id=user.id,
            content="Great post!",
        )
        db.add(comment)
        await db.commit()

        post_id = post.id

    # Get post details
    response = await client.get(f"/posts/{post_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Post"
    assert len(data["comments"]) == 1
    assert data["comments"][0]["content"] == "Great post!"


@pytest.mark.asyncio
async def test_update_post_author_only(client: AsyncClient):
    """Test that only the post author can update."""
    # Setup: Create two users and a post
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        author = User(
            email="author@example.com",
            username="author",
            full_name="Author User",
            password_hash=user_pw,
            is_verified=True,
        )
        other = User(
            email="other@example.com",
            username="other",
            full_name="Other User",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add_all([author, other])
        await db.commit()
        await db.refresh(author)

        post = Post(author_id=author.id, title="Original", content="Original content")
        db.add(post)
        await db.commit()
        await db.refresh(post)
        post_id = post.id

    # Author updates (should succeed)
    author_login = await client.post(
        "/auth/login", json={"email": "author@example.com", "password": "password123"}
    )
    author_token = author_login.json()["access_token"]
    author_headers = {"Authorization": f"Bearer {author_token}"}

    response = await client.patch(
        f"/posts/{post_id}",
        json={"title": "Updated"},
        headers=author_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"

    # Other user tries to update (should fail)
    other_login = await client.post(
        "/auth/login", json={"email": "other@example.com", "password": "password123"}
    )
    other_token = other_login.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    response = await client.patch(
        f"/posts/{post_id}",
        json={"title": "Hacked"},
        headers=other_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_post_author_only(client: AsyncClient):
    """Test that only the post author can delete."""
    # Setup
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        author = User(
            email="delete_author@example.com",
            username="delete_author",
            full_name="Delete Author",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add(author)
        await db.commit()
        await db.refresh(author)

        post = Post(author_id=author.id, title="To Delete", content="Content")
        db.add(post)
        await db.commit()
        await db.refresh(post)
        post_id = post.id

    # Author deletes
    login_res = await client.post(
        "/auth/login",
        json={"email": "delete_author@example.com", "password": "password123"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/posts/{post_id}", headers=headers)
    assert response.status_code == 204

    # Verify deleted
    response = await client.get(f"/posts/{post_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_comment_verified_only(client: AsyncClient):
    """Test that only verified users can comment."""
    # Setup
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        verified_user = User(
            email="commenter@example.com",
            username="commenter",
            full_name="Commenter",
            password_hash=user_pw,
            is_verified=True,
        )
        post_author = User(
            email="post_author@example.com",
            username="post_author",
            full_name="Post Author",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add_all([verified_user, post_author])
        await db.commit()
        await db.refresh(post_author)

        post = Post(
            author_id=post_author.id,
            title="Comment Test",
            content="This post accepts comments",
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        post_id = post.id

    # Verified user creates comment (should succeed)
    login_res = await client.post(
        "/auth/login",
        json={"email": "commenter@example.com", "password": "password123"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/posts/{post_id}/comments",
        json={"content": "Great post!"},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["content"] == "Great post!"


@pytest.mark.asyncio
async def test_delete_comment_author_only(client: AsyncClient):
    """Test that only comment author can delete."""
    # Setup
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        user1 = User(
            email="commenter1@example.com",
            username="commenter1",
            full_name="Commenter 1",
            password_hash=user_pw,
            is_verified=True,
        )
        user2 = User(
            email="commenter2@example.com",
            username="commenter2",
            full_name="Commenter 2",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add_all([user1, user2])
        await db.commit()
        await db.refresh(user1)

        post = Post(author_id=user1.id, title="Test", content="Test")
        db.add(post)
        await db.commit()
        await db.refresh(post)

        comment = Comment(post_id=post.id, author_id=user1.id, content="My comment")
        db.add(comment)
        await db.commit()
        await db.refresh(comment)

        post_id = post.id
        comment_id = comment.id

    # Author deletes comment
    login_res = await client.post(
        "/auth/login",
        json={"email": "commenter1@example.com", "password": "password123"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(
        f"/posts/{post_id}/comments/{comment_id}",
        headers=headers,
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_like_post_constraints(client: AsyncClient):
    """Test like constraints: no self-like, one like per user."""
    # Setup
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        author = User(
            email="liker_author@example.com",
            username="liker_author",
            full_name="Liker Author",
            password_hash=user_pw,
            is_verified=True,
        )
        liker = User(
            email="liker@example.com",
            username="liker",
            full_name="Liker",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add_all([author, liker])
        await db.commit()
        await db.refresh(author)

        post = Post(author_id=author.id, title="Like Test", content="Content")
        db.add(post)
        await db.commit()
        await db.refresh(post)
        post_id = post.id

    # Liker likes post
    login_res = await client.post(
        "/auth/login",
        json={"email": "liker@example.com", "password": "password123"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/posts/{post_id}/like", headers=headers)
    assert response.status_code == 201

    # Try to like again (should fail)
    response = await client.post(f"/posts/{post_id}/like", headers=headers)
    assert response.status_code == 409
    assert "already liked" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cannot_like_own_post(client: AsyncClient):
    """Test that users cannot like their own posts."""
    # Setup
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        user = User(
            email="self_liker@example.com",
            username="self_liker",
            full_name="Self Liker",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        post = Post(author_id=user.id, title="My Post", content="My content")
        db.add(post)
        await db.commit()
        await db.refresh(post)
        post_id = post.id

    # Try to like own post
    login_res = await client.post(
        "/auth/login",
        json={"email": "self_liker@example.com", "password": "password123"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/posts/{post_id}/like", headers=headers)
    assert response.status_code == 400
    assert "cannot like your own" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unlike_post(client: AsyncClient):
    """Test removing a like from a post."""
    # Setup
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        author = User(
            email="unlike_author@example.com",
            username="unlike_author",
            full_name="Unlike Author",
            password_hash=user_pw,
            is_verified=True,
        )
        liker = User(
            email="unliker@example.com",
            username="unliker",
            full_name="Unliker",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add_all([author, liker])
        await db.commit()
        await db.refresh(author)

        post = Post(author_id=author.id, title="Unlike Test", content="Content")
        db.add(post)
        await db.commit()
        await db.refresh(post)

        like = Like(user_id=liker.id, post_id=post.id)
        db.add(like)
        await db.commit()
        post_id = post.id

    # Unlike
    login_res = await client.post(
        "/auth/login",
        json={"email": "unliker@example.com", "password": "password123"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/posts/{post_id}/like", headers=headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_get_feed_endpoint(client: AsyncClient):
    """Test retrieving the aggregated feed of posts grouped by author."""
    # Setup: Create two users, each with a post, and one liking the other's post
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        user1 = User(
            email="feed_user1@example.com",
            username="feed_user1",
            full_name="Feed User 1",
            password_hash=user_pw,
            is_verified=True,
        )
        user2 = User(
            email="feed_user2@example.com",
            username="feed_user2",
            full_name="Feed User 2",
            password_hash=user_pw,
            is_verified=True,
        )
        db.add_all([user1, user2])
        await db.commit()
        await db.refresh(user1)
        await db.refresh(user2)

        post1 = Post(author_id=user1.id, title="Post 1", content="Content 1")
        post2 = Post(author_id=user2.id, title="Post 2", content="Content 2")
        db.add_all([post1, post2])
        await db.commit()
        await db.refresh(post1)
        await db.refresh(post2)

        like = Like(user_id=user2.id, post_id=post1.id)
        db.add(like)
        await db.commit()

        user2_id = user2.id

    response = await client.get("/posts/all/feed")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2

    # Check structure
    user1_feed = next(item for item in data if item["username"] == "feed_user1")
    assert len(user1_feed["posts"]) == 1
    assert user1_feed["posts"][0]["title"] == "Post 1"
    assert user1_feed["posts"][0]["likes"] == [str(user2_id)]
