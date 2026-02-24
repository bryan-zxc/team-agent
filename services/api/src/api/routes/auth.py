import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from ..config import settings
from ..database import async_session
from ..models.project import Project
from ..models.project_member import ProjectMember
from ..models.session import Session
from ..models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
_google_metadata: dict | None = None


async def _get_google_metadata() -> dict:
    """Fetch and cache the Google OpenID Connect discovery document."""
    global _google_metadata
    if _google_metadata is None:
        async with httpx.AsyncClient() as http:
            resp = await http.get(GOOGLE_DISCOVERY_URL)
            resp.raise_for_status()
            _google_metadata = resp.json()
    return _google_metadata


def _set_session_cookie(response, session_id: str) -> None:
    response.set_cookie(
        "session_id",
        session_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age_days * 86400,
        path="/",
    )


async def _create_session(user_id: uuid.UUID) -> str:
    session_id = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    db_session_obj = Session(
        id=session_id,
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(days=settings.session_max_age_days),
    )
    async with async_session() as db:
        db.add(db_session_obj)
        await db.commit()
    return session_id


# ─── Google OAuth ────────────────────────────────────────────────


@router.get("/login")
async def login():
    """Redirect to Google's OAuth consent screen."""
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
        scope="openid email profile",
    )
    metadata = await _get_google_metadata()
    uri, state = client.create_authorization_url(metadata["authorization_endpoint"])

    response = RedirectResponse(url=uri)
    response.set_cookie(
        "oauth_state", state, httponly=True, max_age=600,
        samesite="lax", secure=settings.cookie_secure,
    )
    return response


@router.get("/callback")
async def callback(request: Request):
    """Handle Google OAuth callback."""
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    stored_state = request.cookies.get("oauth_state")
    request_state = request.query_params.get("state")
    if not stored_state or stored_state != request_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
        state=stored_state,
    )
    metadata = await _get_google_metadata()
    token = await client.fetch_token(
        metadata["token_endpoint"],
        authorization_response=str(request.url),
    )

    # Get user info
    resp = await client.get(metadata["userinfo_endpoint"])
    userinfo = resp.json()

    email = userinfo["email"]
    name = userinfo.get("name", email.split("@")[0])
    avatar_url = userinfo.get("picture")

    async with async_session() as db:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        is_new = user is None
        if is_new:
            user = User(display_name=name, email=email, avatar_url=avatar_url)
            db.add(user)
            await db.flush()
            logger.info("Created new user: %s (%s)", name, email)
        else:
            user.avatar_url = avatar_url
            await db.flush()

        # Auto-add new users to all existing projects
        if is_new:
            projects = (await db.execute(select(Project))).scalars().all()
            for project in projects:
                member = ProjectMember(
                    project_id=project.id,
                    user_id=user.id,
                    display_name=user.display_name,
                    type="human",
                )
                db.add(member)

        await db.commit()
        user_id = user.id

    session_id = await _create_session(user_id)

    response = RedirectResponse(url=settings.frontend_url, status_code=302)
    _set_session_cookie(response, session_id)
    response.delete_cookie("oauth_state")
    return response


# ─── Session endpoints ───────────────────────────────────────────


@router.get("/me")
async def get_me(request: Request):
    """Return the current authenticated user."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with async_session() as db:
        session = await db.get(Session, session_id)
        if not session or session.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Invalid or expired session")

        user = await db.get(User, session.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return {
            "id": str(user.id),
            "display_name": user.display_name,
            "email": user.email,
            "avatar_url": user.avatar_url,
        }


@router.post("/logout")
async def logout(request: Request):
    """Clear the session cookie and delete the session."""
    session_id = request.cookies.get("session_id")
    if session_id:
        async with async_session() as db:
            session = await db.get(Session, session_id)
            if session:
                await db.delete(session)
                await db.commit()

    response = JSONResponse({"ok": True})
    response.delete_cookie("session_id", path="/")
    return response


# ─── Dev-only endpoints ──────────────────────────────────────────


if settings.team_agent_env == "dev":

    class DevLoginRequest(BaseModel):
        user_id: str

    @router.get("/dev-users")
    async def dev_users():
        """List all users for the dev login picker."""
        async with async_session() as db:
            users = (
                await db.execute(select(User).order_by(User.display_name))
            ).scalars().all()
            return [
                {"id": str(u.id), "display_name": u.display_name}
                for u in users
            ]

    @router.post("/dev-login")
    async def dev_login(req: DevLoginRequest):
        """Create a session for an existing user (dev only)."""
        async with async_session() as db:
            user = await db.get(User, uuid.UUID(req.user_id))
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

        session_id = await _create_session(user.id)

        response = JSONResponse({
            "id": str(user.id),
            "display_name": user.display_name,
            "email": user.email,
            "avatar_url": user.avatar_url,
        })
        _set_session_cookie(response, session_id)
        return response
