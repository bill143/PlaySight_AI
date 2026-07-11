"""YouTube OAuth2 authorization flow and token storage."""

from __future__ import annotations

import logging
import time
from typing import Protocol

from backend.core.config import settings
from backend.integrations.youtube.models import OAuthTokens

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when google-auth-oauthlib is installed
    from google.oauth2.credentials import Credentials  # type: ignore[import-not-found]
    from google_auth_oauthlib.flow import Flow  # type: ignore[import-not-found]

    _GOOGLE_AUTH_AVAILABLE = True
except ImportError:  # pragma: no cover
    Flow = None  # type: ignore[assignment]
    Credentials = None  # type: ignore[assignment]
    _GOOGLE_AUTH_AVAILABLE = False

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class TokenStore(Protocol):
    """Storage interface for persisting per-club/user OAuth tokens."""

    def get(self, account_key: str) -> OAuthTokens | None: ...

    def set(self, account_key: str, tokens: OAuthTokens) -> None: ...


class InMemoryTokenStore:
    """Simple in-memory token store; suitable for tests/dev, swap for a DB-backed store in production."""

    def __init__(self) -> None:
        self._tokens: dict[str, OAuthTokens] = {}

    def get(self, account_key: str) -> OAuthTokens | None:
        return self._tokens.get(account_key)

    def set(self, account_key: str, tokens: OAuthTokens) -> None:
        self._tokens[account_key] = tokens


class YouTubeAuthManager:
    """Manages the OAuth2 authorization-code flow and token refresh for YouTube uploads."""

    def __init__(self, token_store: TokenStore | None = None) -> None:
        self.client_id = settings.YOUTUBE_CLIENT_ID
        self.client_secret = settings.YOUTUBE_CLIENT_SECRET
        self.redirect_uri = settings.YOUTUBE_REDIRECT_URI
        self.token_store = token_store or InMemoryTokenStore()

    def _client_config(self) -> dict:
        return {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri],
            }
        }

    def get_authorization_url(self, state: str | None = None) -> str:
        """Build the URL the user should visit to authorize PlaySight AI's YouTube access."""
        if not _GOOGLE_AUTH_AVAILABLE:
            raise RuntimeError("google-auth-oauthlib is not installed; cannot build an authorization URL.")

        flow = Flow.from_client_config(self._client_config(), scopes=SCOPES, redirect_uri=self.redirect_uri)  # type: ignore[union-attr]
        auth_url, _state = flow.authorization_url(access_type="offline", include_granted_scopes="true", state=state)
        return auth_url

    def exchange_code_for_tokens(self, code: str, account_key: str) -> OAuthTokens:
        """Exchange an OAuth2 authorization code for access/refresh tokens and persist them."""
        if not _GOOGLE_AUTH_AVAILABLE:
            raise RuntimeError("google-auth-oauthlib is not installed; cannot exchange authorization code.")

        flow = Flow.from_client_config(self._client_config(), scopes=SCOPES, redirect_uri=self.redirect_uri)  # type: ignore[union-attr]
        flow.fetch_token(code=code)
        credentials = flow.credentials

        tokens = OAuthTokens(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token or "",
            expires_at=credentials.expiry.timestamp() if credentials.expiry else time.time() + 3600,
        )
        self.token_store.set(account_key, tokens)
        return tokens

    def get_valid_tokens(self, account_key: str) -> OAuthTokens | None:
        """Return stored tokens for an account, refreshing them first if expired."""
        tokens = self.token_store.get(account_key)
        if tokens is None:
            return None

        if tokens.expires_at <= time.time() and _GOOGLE_AUTH_AVAILABLE:
            tokens = self._refresh(tokens)
            self.token_store.set(account_key, tokens)

        return tokens

    def _refresh(self, tokens: OAuthTokens) -> OAuthTokens:  # pragma: no cover - requires live Google endpoint
        credentials = Credentials(
            token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        )
        import google.auth.transport.requests  # type: ignore[import-not-found]

        credentials.refresh(google.auth.transport.requests.Request())
        return OAuthTokens(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token or tokens.refresh_token,
            expires_at=credentials.expiry.timestamp() if credentials.expiry else time.time() + 3600,
        )
