from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from avicola_pro.modules.identity.application.credentials import Argon2PasswordService
from avicola_pro.modules.identity.application.sessions import IssuedSessionTokens, SessionTokenService


class AuthenticationError(RuntimeError):
    """Base class for safe authentication failures."""


class InvalidCredentialsError(AuthenticationError):
    """Raised for every login denial without disclosing its cause."""


class InvalidSessionError(AuthenticationError):
    """Raised when an opaque session cannot authorize a request."""


class SessionReuseError(InvalidSessionError):
    """Raised after a rotated credential is presented and its family is revoked."""


class CsrfValidationError(AuthenticationError):
    """Raised when a mutable authenticated request lacks valid CSRF proof."""


class PasswordChangeRequiredError(AuthenticationError):
    """Raised when a forced-change account attempts a disallowed operation."""


class PasswordChangeError(AuthenticationError):
    """Raised when the current password cannot authorize a password change."""


@dataclass(frozen=True, slots=True)
class RequestContext:
    correlation_id: str
    ip_address: str | None
    user_agent: str | None


@dataclass(frozen=True, slots=True)
class UserAccount:
    id: UUID
    username: str
    email: str
    display_name: str
    password_hash: str
    status: str
    must_change_password: bool
    failed_login_attempts: int
    locked_until: datetime | None
    token_version: int


@dataclass(frozen=True, slots=True)
class SessionAccount:
    session_id: UUID
    family_id: UUID
    user: UserAccount
    csrf_hash: bytes
    created_at: datetime
    last_used_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    rotated_at: datetime | None
    replaced_by_session_id: UUID | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class NewSession:
    id: UUID
    user_id: UUID
    family_id: UUID
    token_hash: bytes
    csrf_hash: bytes
    created_at: datetime
    last_used_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    ip_address: str | None
    user_agent: str | None


@dataclass(frozen=True, slots=True)
class AuthResult:
    user: UserAccount
    session: NewSession
    tokens: IssuedSessionTokens


@dataclass(frozen=True, slots=True)
class RefreshResult:
    user: UserAccount
    tokens: IssuedSessionTokens | None


@dataclass(frozen=True, slots=True)
class SecurityEventData:
    actor_user_id: UUID | None
    actor_username: str | None
    event_type: str
    outcome: str
    context: RequestContext
    metadata: dict[str, object]


class AuthenticationRepository(Protocol):
    async def find_user(self, identity: str) -> UserAccount | None: ...

    async def record_login_failure(
        self, user_id: UUID, now: datetime, max_attempts: int, lockout_seconds: int
    ) -> tuple[int, datetime | None]: ...

    async def complete_login(self, user_id: UUID, updated_hash: str | None, session: NewSession) -> None: ...

    async def find_session(self, token_hash: bytes) -> SessionAccount | None: ...

    async def touch_session(self, session_id: UUID, last_used_at: datetime, idle_expires_at: datetime) -> None: ...

    async def rotate_session(self, old_session_id: UUID, now: datetime, replacement: NewSession) -> bool: ...

    async def revoke_session(self, session_id: UUID, now: datetime, reason: str) -> None: ...

    async def revoke_family(self, family_id: UUID, now: datetime, reason: str) -> None: ...

    async def change_password(
        self, user_id: UUID, password_hash: str, now: datetime, replacement: NewSession
    ) -> None: ...


class SecurityEventWriter(Protocol):
    async def write(self, event: SecurityEventData) -> None: ...

    async def count_recent_login_denials(self, identity: str, ip_address: str | None, since: datetime) -> int: ...


class AuthenticationService:
    """Stateful opaque-session authentication orchestration."""

    def __init__(
        self,
        *,
        repository: AuthenticationRepository,
        security_events: SecurityEventWriter,
        password_service: Argon2PasswordService,
        token_service: SessionTokenService,
        idle_timeout_seconds: int,
        absolute_timeout_seconds: int,
        rotation_interval_seconds: int,
        max_failed_attempts: int,
        lockout_seconds: int,
        rate_limit_attempts: int,
        rate_limit_window_seconds: int,
    ) -> None:
        self._repository = repository
        self._security_events = security_events
        self._password_service = password_service
        self._token_service = token_service
        self._idle_timeout = timedelta(seconds=idle_timeout_seconds)
        self._absolute_timeout = timedelta(seconds=absolute_timeout_seconds)
        self._rotation_interval = timedelta(seconds=rotation_interval_seconds)
        self._max_failed_attempts = max_failed_attempts
        self._lockout_seconds = lockout_seconds
        self._rate_limit_attempts = rate_limit_attempts
        self._rate_limit_window = timedelta(seconds=rate_limit_window_seconds)
        self._dummy_hash = password_service.hash("Timing-Mitigation-Only-Password-47!")

    @staticmethod
    def _normalize_identity(identity: str) -> str:
        return unicodedata.normalize("NFKC", identity).strip().casefold()

    def _new_session(
        self,
        *,
        user_id: UUID,
        family_id: UUID,
        now: datetime,
        context: RequestContext,
        tokens: IssuedSessionTokens,
        absolute_expires_at: datetime | None = None,
    ) -> NewSession:
        absolute_expiry = absolute_expires_at or now + self._absolute_timeout
        return NewSession(
            id=uuid4(),
            user_id=user_id,
            family_id=family_id,
            token_hash=tokens.session_hash,
            csrf_hash=tokens.csrf_hash,
            created_at=now,
            last_used_at=now,
            idle_expires_at=min(now + self._idle_timeout, absolute_expiry),
            absolute_expires_at=absolute_expiry,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
        )

    async def _event(
        self,
        *,
        event_type: str,
        outcome: str,
        context: RequestContext,
        user: UserAccount | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        await self._security_events.write(
            SecurityEventData(
                actor_user_id=user.id if user else None,
                actor_username=user.username if user else None,
                event_type=event_type,
                outcome=outcome,
                context=context,
                metadata=metadata or {},
            )
        )

    async def login(self, identity: str, password: str, context: RequestContext) -> AuthResult:
        """Verify credentials generically, persist lockout state, and issue an opaque session."""
        now = datetime.now(UTC)
        normalized = self._normalize_identity(identity)
        recent_denials = await self._security_events.count_recent_login_denials(
            normalized, context.ip_address, now - self._rate_limit_window
        )
        if recent_denials >= self._rate_limit_attempts:
            self._password_service.verify(password, self._dummy_hash)
            await self._event(
                event_type="auth.rate_limited",
                outcome="DENIED",
                context=context,
                metadata={"username": normalized, "reason": "rate_limit"},
            )
            raise InvalidCredentialsError

        user = await self._repository.find_user(normalized)
        verification = self._password_service.verify(password, user.password_hash if user else self._dummy_hash)
        if user is None or user.status != "ACTIVE":
            await self._event(
                event_type="auth.login",
                outcome="FAILURE",
                context=context,
                user=user,
                metadata={"username": normalized, "reason": "invalid_credentials"},
            )
            raise InvalidCredentialsError
        if user.locked_until is not None and user.locked_until > now:
            await self._event(
                event_type="auth.locked",
                outcome="DENIED",
                context=context,
                user=user,
                metadata={"username": user.username, "locked_until": user.locked_until.isoformat()},
            )
            raise InvalidCredentialsError
        if not verification.is_valid:
            failed_attempts, locked_until = await self._repository.record_login_failure(
                user.id, now, self._max_failed_attempts, self._lockout_seconds
            )
            locked = locked_until is not None
            await self._event(
                event_type="auth.locked" if locked else "auth.login",
                outcome="DENIED" if locked else "FAILURE",
                context=context,
                user=user,
                metadata={
                    "username": user.username,
                    "reason": "invalid_credentials",
                    "failed_attempts": failed_attempts,
                    "locked_until": locked_until.isoformat() if locked_until else None,
                },
            )
            raise InvalidCredentialsError

        tokens = self._token_service.issue()
        new_session = self._new_session(
            user_id=user.id,
            family_id=uuid4(),
            now=now,
            context=context,
            tokens=tokens,
        )
        await self._repository.complete_login(user.id, verification.updated_hash, new_session)
        await self._event(
            event_type="auth.login",
            outcome="SUCCESS",
            context=context,
            user=user,
            metadata={"username": user.username, "user_id": str(user.id), "session_id": str(new_session.id)},
        )
        return AuthResult(user=user, session=new_session, tokens=tokens)

    async def _load_session(
        self,
        session_token: str | None,
        context: RequestContext,
        *,
        csrf_token: str | None = None,
    ) -> SessionAccount:
        now = datetime.now(UTC)
        record = (
            None
            if not session_token
            else await self._repository.find_session(self._token_service.hash_session(session_token))
        )
        if record is None:
            await self._event(
                event_type="auth.unauthorized",
                outcome="DENIED",
                context=context,
                metadata={"reason": "missing"},
            )
            raise InvalidSessionError
        if csrf_token is not None and not self._token_service.verify_csrf(csrf_token, record.csrf_hash):
            await self._event(
                event_type="auth.csrf_denied",
                outcome="DENIED",
                context=context,
                user=record.user,
                metadata={"session_id": str(record.session_id), "reason": "csrf"},
            )
            raise CsrfValidationError
        if record.replaced_by_session_id is not None:
            await self._repository.revoke_family(record.family_id, now, "session_reuse")
            await self._event(
                event_type="auth.session_reuse",
                outcome="DENIED",
                context=context,
                user=record.user,
                metadata={"session_id": str(record.session_id), "session_family_id": str(record.family_id)},
            )
            raise SessionReuseError
        invalid = (
            record.revoked_at is not None
            or record.user.status != "ACTIVE"
            or record.idle_expires_at <= now
            or record.absolute_expires_at <= now
        )
        if invalid:
            if record.revoked_at is None:
                await self._repository.revoke_session(record.session_id, now, "expired_or_inactive")
            await self._event(
                event_type="auth.unauthorized",
                outcome="DENIED",
                context=context,
                user=record.user,
                metadata={"session_id": str(record.session_id), "reason": "invalid_session"},
            )
            raise InvalidSessionError
        return record

    async def current_session(self, session_token: str | None, context: RequestContext) -> UserAccount:
        """Return the active account and extend its bounded idle expiry."""
        record = await self._load_session(session_token, context)
        now = datetime.now(UTC)
        await self._repository.touch_session(
            record.session_id, now, min(now + self._idle_timeout, record.absolute_expires_at)
        )
        return record.user

    async def validate_mutation(
        self, session_token: str | None, csrf_token: str | None, context: RequestContext
    ) -> UserAccount:
        """Validate an authenticated state-changing request without changing session state."""
        record = await self._load_session(session_token, context, csrf_token=csrf_token)
        return record.user

    async def password_change_is_required(
        self, session_token: str | None, context: RequestContext
    ) -> UserAccount | None:
        """Inspect a valid session for the global forced-change guard without touching it."""
        try:
            record = await self._load_session(session_token, context)
        except InvalidSessionError:
            return None
        return record.user if record.user.must_change_password else None

    async def record_password_change_required(self, user: UserAccount, context: RequestContext) -> None:
        """Record a forced-password-change policy denial independently."""
        await self._event(
            event_type="auth.password_change_required",
            outcome="DENIED",
            context=context,
            user=user,
            metadata={"user_id": str(user.id), "reason": "password_change_required"},
        )

    async def _require_csrf(self, session_token: str | None, csrf_token: str | None, context: RequestContext) -> str:
        if csrf_token is not None:
            return csrf_token
        record = await self._load_session(session_token, context)
        await self._event(
            event_type="auth.csrf_denied",
            outcome="DENIED",
            context=context,
            user=record.user,
            metadata={"session_id": str(record.session_id), "reason": "missing_csrf"},
        )
        raise CsrfValidationError

    async def refresh(
        self, session_token: str | None, csrf_token: str | None, context: RequestContext
    ) -> RefreshResult:
        """Rotate a due opaque identifier or only extend a still-recent session."""
        required_csrf = await self._require_csrf(session_token, csrf_token, context)
        record = await self._load_session(session_token, context, csrf_token=required_csrf)
        if record.user.must_change_password:
            raise PasswordChangeRequiredError
        now = datetime.now(UTC)
        if now - record.created_at < self._rotation_interval:
            await self._repository.touch_session(
                record.session_id, now, min(now + self._idle_timeout, record.absolute_expires_at)
            )
            await self._event(
                event_type="auth.refresh",
                outcome="SUCCESS",
                context=context,
                user=record.user,
                metadata={"session_id": str(record.session_id), "reason": "not_due"},
            )
            return RefreshResult(user=record.user, tokens=None)

        tokens = self._token_service.issue()
        replacement = self._new_session(
            user_id=record.user.id,
            family_id=record.family_id,
            now=now,
            context=context,
            tokens=tokens,
            absolute_expires_at=record.absolute_expires_at,
        )
        if not await self._repository.rotate_session(record.session_id, now, replacement):
            await self._repository.revoke_family(record.family_id, now, "session_reuse")
            raise SessionReuseError
        await self._event(
            event_type="auth.refresh",
            outcome="SUCCESS",
            context=context,
            user=record.user,
            metadata={"session_id": str(replacement.id), "session_family_id": str(record.family_id)},
        )
        return RefreshResult(user=record.user, tokens=tokens)

    async def logout(self, session_token: str | None, csrf_token: str | None, context: RequestContext) -> None:
        """Revoke one active session after CSRF validation."""
        required_csrf = await self._require_csrf(session_token, csrf_token, context)
        record = await self._load_session(session_token, context, csrf_token=required_csrf)
        await self._repository.revoke_session(record.session_id, datetime.now(UTC), "logout")
        await self._event(
            event_type="auth.logout",
            outcome="SUCCESS",
            context=context,
            user=record.user,
            metadata={"session_id": str(record.session_id)},
        )

    async def change_password(
        self,
        session_token: str | None,
        csrf_token: str | None,
        current_password: str,
        new_password: str,
        context: RequestContext,
    ) -> AuthResult:
        """Replace the credential, revoke every old session, and issue a fresh family."""
        required_csrf = await self._require_csrf(session_token, csrf_token, context)
        record = await self._load_session(session_token, context, csrf_token=required_csrf)
        if not self._password_service.verify(current_password, record.user.password_hash).is_valid:
            await self._event(
                event_type="auth.password_change",
                outcome="FAILURE",
                context=context,
                user=record.user,
                metadata={"reason": "invalid_current_password"},
            )
            raise PasswordChangeError
        password_hash = self._password_service.hash(new_password)
        now = datetime.now(UTC)
        tokens = self._token_service.issue()
        replacement = self._new_session(
            user_id=record.user.id,
            family_id=uuid4(),
            now=now,
            context=context,
            tokens=tokens,
        )
        await self._repository.change_password(record.user.id, password_hash, now, replacement)
        changed_user = UserAccount(
            id=record.user.id,
            username=record.user.username,
            email=record.user.email,
            display_name=record.user.display_name,
            password_hash=password_hash,
            status=record.user.status,
            must_change_password=False,
            failed_login_attempts=0,
            locked_until=None,
            token_version=record.user.token_version + 1,
        )
        await self._event(
            event_type="auth.password_change",
            outcome="SUCCESS",
            context=context,
            user=changed_user,
            metadata={"user_id": str(changed_user.id), "token_version": changed_user.token_version},
        )
        return AuthResult(user=changed_user, session=replacement, tokens=tokens)
