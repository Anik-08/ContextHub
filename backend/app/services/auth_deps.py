"""
auth_deps.py — FastAPI dependency that resolves the authenticated user.

HOW IT WORKS:
  FastAPI dependencies let you declare "this endpoint requires X" and the
  framework resolves it before the handler runs. Here:

      async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security))

  - `security` is FastAPI's HTTPBearer: it parses the `Authorization: Bearer <token>`
    header and returns the credentials (or raises 401 if missing).
  - We decode the JWT, pull out the user_id, load the User row.
  - If the token is expired, tampered, or the user is gone -> HTTP 401.

  Routes then accept `user: User = Depends(get_current_user)` and use
  `user.user_id` to scope every document/repo/query — enforcing multi-tenancy.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.db_models import User
from app.services.security import decode_access_token
from app.services.user_registry import get_user_by_id


_security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> User:
    """
    Resolve the authenticated user from the Bearer token.
    Raises HTTP 401 with a standard WWW-Authenticate header on failure.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide a Bearer token in the Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user