import logging
import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from fastapi import HTTPException, Request, status

from app.core.passwords import MAX_PASSWORD_BYTES, password_exceeds_bcrypt_limit

logger = logging.getLogger(__name__)

LOGIN_FAILURE_LIMIT = int(os.getenv("AUTH_LOGIN_FAILURE_LIMIT", "5"))
LOGIN_IP_FAILURE_LIMIT = int(os.getenv("AUTH_LOGIN_IP_FAILURE_LIMIT", "25"))
LOGIN_WINDOW_SECONDS = int(os.getenv("AUTH_LOGIN_WINDOW_SECONDS", "900"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("AUTH_LOGIN_LOCKOUT_SECONDS", "300"))
REGISTRATION_IP_LIMIT = int(os.getenv("AUTH_REGISTRATION_IP_LIMIT", "10"))
REGISTRATION_WINDOW_SECONDS = int(os.getenv("AUTH_REGISTRATION_WINDOW_SECONDS", "3600"))
PASSWORD_RESET_LIMIT = int(os.getenv("AUTH_PASSWORD_RESET_LIMIT", "5"))
PASSWORD_RESET_IP_LIMIT = int(os.getenv("AUTH_PASSWORD_RESET_IP_LIMIT", "20"))
PASSWORD_RESET_WINDOW_SECONDS = int(os.getenv("AUTH_PASSWORD_RESET_WINDOW_SECONDS", "3600"))


@dataclass(frozen=True)
class LimitRule:
    key: str
    limit: int
    window_seconds: int
    lockout_seconds: int


@dataclass
class _Bucket:
    events: deque[float] = field(default_factory=deque)
    locked_until: float = 0.0


class _AbuseTracker:
    def __init__(self, clock: Callable[[], float] | None = None):
        self._clock = clock or time.monotonic
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def clear(self, keys: list[str]) -> None:
        with self._lock:
            for key in keys:
                self._buckets.pop(key, None)

    def retry_after(self, rules: list[LimitRule]) -> int | None:
        now = self._clock()
        with self._lock:
            retry_after = self._retry_after_locked(rules, now)
        return retry_after

    def record(self, rules: list[LimitRule]) -> None:
        now = self._clock()
        with self._lock:
            for rule in rules:
                if rule.limit <= 0:
                    continue

                bucket = self._bucket_for(rule.key)
                self._prune(bucket, now, rule.window_seconds)
                bucket.events.append(now)
                if len(bucket.events) >= rule.limit:
                    bucket.locked_until = max(
                        bucket.locked_until,
                        now + rule.lockout_seconds,
                    )

    def _retry_after_locked(
        self,
        rules: list[LimitRule],
        now: float,
    ) -> int | None:
        retry_after = 0.0
        for rule in rules:
            if rule.limit <= 0:
                continue

            bucket = self._bucket_for(rule.key)
            self._prune(bucket, now, rule.window_seconds)
            if bucket.locked_until > now:
                retry_after = max(retry_after, bucket.locked_until - now)
            elif len(bucket.events) >= rule.limit:
                bucket.locked_until = now + rule.lockout_seconds
                retry_after = max(retry_after, rule.lockout_seconds)

        if retry_after <= 0:
            return None
        return max(1, math.ceil(retry_after))

    def _bucket_for(self, key: str) -> _Bucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket()
            self._buckets[key] = bucket
        return bucket

    @staticmethod
    def _prune(bucket: _Bucket, now: float, window_seconds: int) -> None:
        if bucket.locked_until and bucket.locked_until <= now:
            bucket.locked_until = 0.0
            bucket.events.clear()
            return

        cutoff = now - window_seconds
        while bucket.events and bucket.events[0] <= cutoff:
            bucket.events.popleft()


_tracker = _AbuseTracker()


def reset_auth_abuse_state() -> None:
    _tracker.reset()


def reject_oversized_password(password: str) -> None:
    if not password_exceeds_bcrypt_limit(password):
        return

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            f"Пароль должен содержать не более {MAX_PASSWORD_BYTES} байт "
            "в кодировке UTF-8"
        ),
    )


def assert_registration_allowed(request: Request) -> None:
    rules = _registration_rules(request)
    retry_after = _tracker.retry_after(rules)
    if retry_after is not None:
        logger.warning(
            "Registration rate limit exceeded for client=%s retry_after=%s",
            _audit_client(request),
            retry_after,
        )
        _raise_too_many_requests(
            "Too many registration attempts. Try again later.",
            retry_after,
        )

    _tracker.record(rules)


def assert_login_allowed(request: Request, username: str) -> None:
    rules = _login_rules(request, username)
    retry_after = _tracker.retry_after(rules)
    if retry_after is None:
        return

    logger.warning(
        "Login temporarily locked for subject=%r client=%s retry_after=%s",
        _normalize_subject(username),
        _audit_client(request),
        retry_after,
    )
    _raise_too_many_requests(
        "Too many failed login attempts. Try again later.",
        retry_after,
    )


def assert_password_reset_allowed(request: Request, email: str) -> None:
    subject = _normalize_subject(email)
    rules = [
        LimitRule(
            key=f"password-reset:subject:{subject}",
            limit=PASSWORD_RESET_LIMIT,
            window_seconds=PASSWORD_RESET_WINDOW_SECONDS,
            lockout_seconds=PASSWORD_RESET_WINDOW_SECONDS,
        ),
        *(
            LimitRule(
                key=f"password-reset:ip:{client_key}",
                limit=PASSWORD_RESET_IP_LIMIT,
                window_seconds=PASSWORD_RESET_WINDOW_SECONDS,
                lockout_seconds=PASSWORD_RESET_WINDOW_SECONDS,
            )
            for client_key in _client_keys(request)
        ),
    ]
    retry_after = _tracker.retry_after(rules)
    if retry_after is not None:
        logger.warning(
            "Password reset rate limit exceeded for subject=%r client=%s retry_after=%s",
            subject,
            _audit_client(request),
            retry_after,
        )
        _raise_too_many_requests(
            "Too many password reset attempts. Try again later.",
            retry_after,
        )
    _tracker.record(rules)


def record_failed_login(request: Request, username: str) -> None:
    rules = _login_rules(request, username)
    _tracker.record(rules)
    retry_after = _tracker.retry_after(rules)
    if retry_after is not None:
        logger.warning(
            "Failed login threshold reached for subject=%r client=%s retry_after=%s",
            _normalize_subject(username),
            _audit_client(request),
            retry_after,
        )


def record_successful_login(_request: Request, username: str) -> None:
    _tracker.clear([_login_subject_key(username)])


def _login_rules(request: Request, username: str) -> list[LimitRule]:
    rules = [
        LimitRule(
            key=_login_subject_key(username),
            limit=LOGIN_FAILURE_LIMIT,
            window_seconds=LOGIN_WINDOW_SECONDS,
            lockout_seconds=LOGIN_LOCKOUT_SECONDS,
        )
    ]
    rules.extend(
        LimitRule(
            key=f"login:ip:{client_key}",
            limit=LOGIN_IP_FAILURE_LIMIT,
            window_seconds=LOGIN_WINDOW_SECONDS,
            lockout_seconds=LOGIN_LOCKOUT_SECONDS,
        )
        for client_key in _client_keys(request)
    )
    return rules


def _registration_rules(request: Request) -> list[LimitRule]:
    return [
        LimitRule(
            key=f"registration:ip:{client_key}",
            limit=REGISTRATION_IP_LIMIT,
            window_seconds=REGISTRATION_WINDOW_SECONDS,
            lockout_seconds=REGISTRATION_WINDOW_SECONDS,
        )
        for client_key in _client_keys(request)
    ]


def _login_subject_key(username: str) -> str:
    return f"login:subject:{_normalize_subject(username)}"


def _normalize_subject(username: str) -> str:
    normalized = username.strip().casefold()
    return normalized or "<blank>"


def _client_keys(request: Request) -> list[str]:
    keys: list[str] = []
    peer = request.client.host if request.client else "unknown"
    _append_unique(keys, f"peer:{peer}")

    forwarded_for = request.headers.get("x-forwarded-for", "")
    forwarded_client = forwarded_for.split(",", 1)[0].strip()
    if forwarded_client:
        _append_unique(keys, f"forwarded:{forwarded_client}")

    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        _append_unique(keys, f"real:{real_ip}")

    return keys


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _audit_client(request: Request) -> str:
    return ",".join(_client_keys(request))


def _raise_too_many_requests(detail: str, retry_after: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(retry_after)},
    )
