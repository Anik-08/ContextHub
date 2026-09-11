"""
security.py — Password hashing and JWT access tokens.

PASSWORD HASHING (PBKDF2-HMAC-SHA256):
  We never store plaintext passwords. Instead we store a one-way hash.
  The hash is computed with PBKDF2 (Password-Based Key Derivation Function 2),
  an OWASP-recommended KDF that applies SHA-256 thousands of times to slow
  down brute-force attacks. Each user gets a unique random salt, so two users
  with the same password produce different hashes.

  Stored format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
  Verification re-runs PBKDF2 with the stored salt/iterations and compares
  digests in constant time (hmac.compare_digest) to avoid timing attacks.

  Alternatives:
    - bcrypt / argon2: purpose-built password KDFs, generally preferred in
      production. argon2 is the OWASP first choice. We use PBKDF2 here to
      avoid native wheel issues without sacrificing security (it's still a
      legitimate, NIST-approved KDF).

ACCESS TOKENS (JWT HS256):
  After login we mint a signed JSON Web Token (RFC 7519). A JWT has three
  dot-separated parts:
    1. header:  {"alg": "HS256", "typ": "JWT"}
    2. payload: claims like sub (user id), iat (issued at), exp (expiry)
    3. signature: HMAC-SHA256(header + "." + payload, SECRET_KEY)
  Because only the server knows SECRET_KEY, an attacker cannot forge a token.
  The client just presents the token on each request; no server-side session
  storage is needed (that's what makes JWTs "stateless").

  Trade-offs (interview question):
    - JWTs can't be revoked early without a token-blacklist/denylist layer.
    - Use short expiries + refresh tokens in production.
    - For a portfolio app, HttpOnly cookies are even safer than localStorage
      because JS can't read them (preventing XSS token theft). We return the
      token in JSON for simplicity; the frontend stores it in memory +
      localStorage. A production build should move to HttpOnly cookies.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


# OWASP recommends >= 600,000 iterations for PBKDF2-HMAC-SHA256.
# 100,000 keeps local dev snappy while remaining a strong baseline.
PBKDF2_ITERATIONS = 100_000
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a plaintext password with PBKDF2-HMAC-SHA256 + per-user salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash."""
    try:
        _algo, iterations, salt, expected_hex = stored_hash.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations),
        )
        # Constant-time comparison prevents timing side channels.
        return hmac.compare_digest(digest.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str) -> str:
    """Mint a signed JWT with sub=user_id and a 24h expiry."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,                              # subject = the user
        "iat": now,                                  # issued-at timestamp
        "exp": now + timedelta(minutes=settings.jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """
    Verify a JWT and return the user_id (sub claim).

    Returns None on any tampering/expiry/invalid signature — the caller
    treats that as an unauthenticated request (HTTP 401).
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        return None