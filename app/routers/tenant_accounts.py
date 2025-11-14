"""Tenant account management API."""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization, User, UserInvite
from app.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    require_role,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.security.auth import get_db_session

router = APIRouter(prefix="/api/tenant/accounts", tags=["tenant-accounts"])

SessionDep = Annotated[Session, Depends(get_db_session)]
UserDep = Annotated[User, Depends(get_current_user)]
AdminRoleDep = Annotated[str, Depends(require_role("admin"))]
AUTH_SCHEME_BEARER: Literal["bearer"] = "bearer"

_ROLE_CHOICES: tuple[Literal["viewer", "operator", "admin"], ...] = (
    "viewer",
    "operator",
    "admin",
)


class OrganizationPayload(BaseModel):
    id: uuid.UUID
    name: str
    subdomain: str
    plan_type: str


class UserPayload(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    role: str


class TokenEnvelope(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = AUTH_SCHEME_BEARER
    expires_in: int = Field(..., description="Seconds until the access token expires")
    refresh_expires_in: int = Field(
        ..., description="Seconds until the refresh token expires"
    )
    roles: list[str]


class AuthenticatedResponse(BaseModel):
    organization: OrganizationPayload
    user: UserPayload
    tokens: TokenEnvelope


class RegisterOrganizationRequest(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=255)
    subdomain: str = Field(..., pattern=r"^[a-z0-9-]{3,63}$")
    admin_name: str = Field(..., min_length=1, max_length=255)
    admin_email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: Literal["viewer", "operator", "admin"] = "viewer"
    expires_in: int = Field(default=60 * 60 * 24 * 7, ge=300, le=60 * 60 * 24 * 30)
    message: str | None = Field(default=None, max_length=2000)


class InviteResponse(BaseModel):
    token: str
    email: EmailStr
    role: str
    expires_at: dt.datetime


class AcceptInviteRequest(BaseModel):
    token: str
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class RotateCredentialsRequest(BaseModel):
    refresh_token: str


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _normalize_subdomain(subdomain: str) -> str:
    return subdomain.lower()


def _normalize_email(email: str) -> str:
    return email.lower()


def _as_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _token_response(
    *,
    user: User,
    access_token: str,
    access_expires_at: dt.datetime,
    refresh_token: str,
    refresh_expires_at: dt.datetime,
) -> TokenEnvelope:
    now = _utcnow()
    access_expires_at = _as_utc(access_expires_at)
    refresh_expires_at = _as_utc(refresh_expires_at)

    return TokenEnvelope(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=max(int((access_expires_at - now).total_seconds()), 0),
        refresh_expires_in=max(int((refresh_expires_at - now).total_seconds()), 0),
        roles=[user.role],
    )


def _user_payload(user: User) -> UserPayload:
    return UserPayload(id=user.id, email=user.email, name=user.name, role=user.role)


def _organization_payload(org: Organization) -> OrganizationPayload:
    return OrganizationPayload(
        id=org.id,
        name=org.name,
        subdomain=org.subdomain,
        plan_type=org.plan_type,
    )


@router.post(
    "/register",
    response_model=AuthenticatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_organization(
    payload: RegisterOrganizationRequest,
    request: Request,
    session: SessionDep,
) -> AuthenticatedResponse:
    """Create a tenant organization with an administrator user."""

    subdomain = _normalize_subdomain(payload.subdomain)
    email = _normalize_email(payload.admin_email)

    existing_org = session.execute(
        select(Organization).where(Organization.subdomain == subdomain)
    ).scalar_one_or_none()
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Subdomain already in use."
        )

    existing_user = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists."
        )

    organization = Organization(name=payload.organization_name, subdomain=subdomain)
    session.add(organization)
    session.flush()

    admin_user = User(
        organization_id=organization.id,
        email=email,
        name=payload.admin_name,
        password_hash=hash_password(payload.password),
        role="admin",
    )
    session.add(admin_user)
    session.flush()

    user_agent = request.headers.get("User-Agent")
    refresh_token, refresh_record = create_refresh_token(
        session, admin_user, user_agent=user_agent
    )
    access_token, access_expires_at = create_access_token(admin_user)

    session.commit()

    return AuthenticatedResponse(
        organization=_organization_payload(organization),
        user=_user_payload(admin_user),
        tokens=_token_response(
            user=admin_user,
            access_token=access_token,
            access_expires_at=access_expires_at,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_record.expires_at,
        ),
    )


@router.post("/login", response_model=AuthenticatedResponse)
def login(
    payload: LoginRequest,
    request: Request,
    session: SessionDep,
) -> AuthenticatedResponse:
    """Authenticate a user via e-mail and password."""

    email = _normalize_email(payload.email)
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive."
        )

    organization = user.organization
    user_agent = request.headers.get("User-Agent")
    refresh_token, refresh_record = create_refresh_token(
        session, user, user_agent=user_agent
    )
    access_token, access_expires_at = create_access_token(user)

    session.commit()

    return AuthenticatedResponse(
        organization=_organization_payload(organization),
        user=_user_payload(user),
        tokens=_token_response(
            user=user,
            access_token=access_token,
            access_expires_at=access_expires_at,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_record.expires_at,
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: LogoutRequest,
    session: SessionDep,
    current_user: UserDep,
) -> Response:
    """Revoke a single refresh token for the authenticated user."""

    token = verify_refresh_token(session, payload.refresh_token)
    if token is None or token.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token."
        )

    revoke_refresh_token(token)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/refresh", response_model=AuthenticatedResponse)
def refresh(
    payload: RefreshRequest,
    request: Request,
    session: SessionDep,
) -> AuthenticatedResponse:
    """Exchange a refresh token for a new access/refresh pair."""

    token = verify_refresh_token(session, payload.refresh_token)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token."
        )

    user = session.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive."
        )

    organization = user.organization
    revoke_refresh_token(token)

    user_agent = request.headers.get("User-Agent")
    refresh_token, refresh_record = create_refresh_token(
        session, user, user_agent=user_agent
    )
    access_token, access_expires_at = create_access_token(user)

    session.commit()

    return AuthenticatedResponse(
        organization=_organization_payload(organization),
        user=_user_payload(user),
        tokens=_token_response(
            user=user,
            access_token=access_token,
            access_expires_at=access_expires_at,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_record.expires_at,
        ),
    )


@router.post(
    "/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED
)
def invite_user(
    payload: InviteUserRequest,
    session: SessionDep,
    current_user: UserDep,
    _: AdminRoleDep,
) -> InviteResponse:
    """Issue an invitation for another user to join the organization."""

    email = _normalize_email(payload.email)
    if payload.role not in _ROLE_CHOICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role."
        )

    existing_user = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists."
        )

    existing_invite = session.execute(
        select(UserInvite).where(
            UserInvite.organization_id == current_user.organization_id,
            UserInvite.email == email,
            UserInvite.accepted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing_invite:
        session.delete(existing_invite)
        session.flush()

    invite_token = secrets.token_urlsafe(32)
    expires_at = _utcnow() + dt.timedelta(seconds=payload.expires_in)
    invite = UserInvite(
        organization_id=current_user.organization_id,
        email=email,
        role=payload.role,
        token=invite_token,
        message=payload.message,
        expires_at=expires_at,
    )
    session.add(invite)
    session.commit()

    return InviteResponse(
        token=invite_token, email=email, role=payload.role, expires_at=expires_at
    )


@router.post("/accept-invite", response_model=AuthenticatedResponse)
def accept_invite(
    payload: AcceptInviteRequest,
    request: Request,
    session: SessionDep,
) -> AuthenticatedResponse:
    """Convert an invitation token into an active user account."""

    invite = session.execute(
        select(UserInvite).where(UserInvite.token == payload.token)
    ).scalar_one_or_none()
    if (
        invite is None
        or invite.accepted_at is not None
        or _as_utc(invite.expires_at) <= _utcnow()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite."
        )

    email = _normalize_email(invite.email)
    existing_user = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists."
        )

    user = User(
        organization_id=invite.organization_id,
        email=email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=invite.role,
    )
    session.add(user)
    invite.accepted_at = _utcnow()
    session.flush()

    organization = session.get(Organization, invite.organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found."
        )

    user_agent = request.headers.get("User-Agent")
    refresh_token, refresh_record = create_refresh_token(
        session, user, user_agent=user_agent
    )
    access_token, access_expires_at = create_access_token(user)

    session.commit()

    return AuthenticatedResponse(
        organization=_organization_payload(organization),
        user=_user_payload(user),
        tokens=_token_response(
            user=user,
            access_token=access_token,
            access_expires_at=access_expires_at,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_record.expires_at,
        ),
    )


@router.post("/rotate-credentials", response_model=AuthenticatedResponse)
def rotate_credentials(
    payload: RotateCredentialsRequest,
    request: Request,
    session: SessionDep,
    current_user: UserDep,
) -> AuthenticatedResponse:
    """Invalidate all existing refresh tokens and issue a fresh pair."""

    token = verify_refresh_token(session, payload.refresh_token)
    if token is None or token.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token."
        )

    revoke_all_refresh_tokens(session, current_user)

    user_agent = request.headers.get("User-Agent")
    refresh_token, refresh_record = create_refresh_token(
        session, current_user, user_agent=user_agent
    )
    access_token, access_expires_at = create_access_token(current_user)

    session.commit()

    organization = current_user.organization

    return AuthenticatedResponse(
        organization=_organization_payload(organization),
        user=_user_payload(current_user),
        tokens=_token_response(
            user=current_user,
            access_token=access_token,
            access_expires_at=access_expires_at,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_record.expires_at,
        ),
    )
