"""
auth.py — Authentication routes: register, login, and current-user.

ENDPOINTS:
  - POST /api/auth/register  → create account, return token + user
  - POST /api/auth/login     → verify credentials, return token + user
  - GET  /api/auth/me        → current user (protected example endpoint)

WHY RETURN THE TOKEN ON REGISTER/LOGIN:
  Stateless JWT flow: the client logs in once, gets a signed token, and sends
  it with every subsequent request. The server never stores session state.
  The frontend keeps this token (in memory / localStorage) and attaches it to
  the Authorization header — which our get_current_user dependency validates.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, EmailStr

from app.models.db_models import User
from app.services.security import create_access_token, verify_password
from app.services.user_registry import create_user, get_user_by_email, get_user_by_id
from app.services.auth_deps import get_current_user


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Request / Response schemas for the auth flow
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email (unique).")
    password: str = Field(..., min_length=8, description="Password (min 8 chars).")
    name: str | None = Field(default=None, description="Optional display name.")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Public user fields — never send password_hash to the client."""
    user_id: str
    email: str
    name: str | None
    created_at: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _auth_payload(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.user_id),
        token_type="bearer",
        user=UserOut(
            user_id=user.user_id,
            email=user.email,
            name=user.name,
            created_at=user.created_at.isoformat(),
        ),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
async def register(request: RegisterRequest) -> AuthResponse:
    try:
        user = create_user(email=request.email, password=request.password, name=request.name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _auth_payload(user)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in and receive an access token",
)
async def login(request: LoginRequest) -> AuthResponse:
    user = get_user_by_email(request.email)
    # Same error for "no user" and "wrong password" — don't leak which emails exist.
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return _auth_payload(user)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get the currently authenticated user",
)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    refreshed = get_user_by_id(user.user_id) or user
    return UserOut(
        user_id=refreshed.user_id,
        email=refreshed.email,
        name=refreshed.name,
        created_at=refreshed.created_at.isoformat(),
    )