from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256


class AuthenticationError(Exception):
    """Raised when bearer token validation fails."""


@dataclass(frozen=True)
class AuthenticatedSubject:
    """Verified identity extracted from an access token.

    Attributes:
        user_id: Database identifier for the authenticated user.
        expires_at: UTC expiration timestamp encoded in the token.
    """

    user_id: int
    expires_at: datetime


class AuthService:
    """Create and verify backend-signed bearer tokens.

    The service uses a server-side HMAC secret so the backend remains the source
    of truth for identity. It does not trust frontend-supplied ownership fields.
    """

    token_version = "v1"

    def __init__(self, token_secret: str | None) -> None:
        """Create an authentication service.

        Args:
            token_secret: Server-side secret used to sign and verify tokens.

        Returns:
            None.

        Side effects:
            Stores the secret for token operations.
        """
        self.token_secret = token_secret

    def create_access_token(
        self,
        user_id: int,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a signed bearer token for a user.

        Args:
            user_id: Authenticated user identifier to encode in the token.
            expires_delta: Optional token lifetime from the current UTC time.

        Returns:
            A signed access token string.

        Side effects:
            Reads the current UTC time.

        Raises:
            RuntimeError: If no token secret is configured.
        """
        secret = self._require_token_secret()
        lifetime = expires_delta or timedelta(hours=1)
        expires_at = int((datetime.now(UTC) + lifetime).timestamp())
        payload = f"{self.token_version}.{user_id}.{expires_at}"
        signature = self._sign(payload, secret)
        return f"{payload}.{signature}"

    def verify_access_token(self, token: str) -> AuthenticatedSubject:
        """Verify a bearer token and return its authenticated subject.

        Args:
            token: Bearer token from the request authorization header.

        Returns:
            The authenticated subject encoded in the token.

        Side effects:
            Reads the current UTC time.

        Raises:
            AuthenticationError: If the token is missing, malformed, expired, or
                signed with the wrong secret.
            RuntimeError: If no token secret is configured.
        """
        secret = self._require_token_secret()
        parts = token.split(".")

        if len(parts) != 4:
            raise AuthenticationError("Invalid authentication token")

        version, raw_user_id, raw_expires_at, signature = parts

        if version != self.token_version:
            raise AuthenticationError("Invalid authentication token")

        payload = f"{version}.{raw_user_id}.{raw_expires_at}"
        expected_signature = self._sign(payload, secret)

        if not hmac.compare_digest(signature, expected_signature):
            raise AuthenticationError("Invalid authentication token")

        try:
            user_id = int(raw_user_id)
            expires_at_timestamp = int(raw_expires_at)
        except ValueError as exc:
            raise AuthenticationError("Invalid authentication token") from exc

        expires_at = datetime.fromtimestamp(expires_at_timestamp, UTC)

        if expires_at <= datetime.now(UTC):
            raise AuthenticationError("Invalid authentication token")

        return AuthenticatedSubject(user_id=user_id, expires_at=expires_at)

    def _require_token_secret(self) -> str:
        """Return the configured token secret.

        Returns:
            The configured token secret.

        Side effects:
            None.

        Raises:
            RuntimeError: If the secret is missing.
        """
        if not self.token_secret:
            raise RuntimeError("AUTH_TOKEN_SECRET is not configured")

        return self.token_secret

    @staticmethod
    def _sign(payload: str, secret: str) -> str:
        """Sign a token payload with HMAC-SHA256.

        Args:
            payload: Token payload to sign.
            secret: Server-side signing secret.

        Returns:
            Hex-encoded HMAC signature.

        Side effects:
            None.
        """
        return hmac.new(secret.encode(), payload.encode(), sha256).hexdigest()
