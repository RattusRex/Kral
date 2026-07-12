from __future__ import annotations

import hashlib
import logging
import os
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from ipaddress import ip_address
from urllib.parse import quote

logger = logging.getLogger(__name__)
SMTP_SECURITY_MODES = {"starttls", "ssl", "none"}


def _validate_smtp_host(host: str) -> None:
    if "@" in host or "://" in host or any(character.isspace() for character in host):
        raise RuntimeError(
            "SMTP_HOST must be a server hostname such as smtp.gmail.com, not an email address or URL"
        )
    try:
        ip_address(host)
        return
    except ValueError:
        pass
    labels = host.rstrip(".").split(".")
    if not host or any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or not all(character.isalnum() or character == "-" for character in label)
        for label in labels
    ):
        raise RuntimeError("SMTP_HOST must be a valid server hostname or IP address")


def validate_email_configuration() -> str:
    backend = os.getenv("EMAIL_BACKEND", "console").strip().lower()
    if backend not in {"console", "smtp"}:
        raise RuntimeError("EMAIL_BACKEND must be 'console' or 'smtp'")
    if backend == "smtp":
        missing = [name for name in ("SMTP_HOST", "SMTP_FROM_EMAIL") if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                "SMTP email delivery requires: " + ", ".join(missing)
            )
        _validate_smtp_host(os.environ["SMTP_HOST"].strip())
        try:
            port = int(os.getenv("SMTP_PORT", "587"))
        except ValueError as error:
            raise RuntimeError("SMTP_PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise RuntimeError("SMTP_PORT must be between 1 and 65535")
        security = os.getenv("SMTP_SECURITY", "starttls").strip().lower()
        if security not in SMTP_SECURITY_MODES:
            raise RuntimeError("SMTP_SECURITY must be 'starttls', 'ssl', or 'none'")
        try:
            timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
        except ValueError as error:
            raise RuntimeError("SMTP_TIMEOUT_SECONDS must be a number") from error
        if timeout <= 0:
            raise RuntimeError("SMTP_TIMEOUT_SECONDS must be greater than zero")
        username = os.getenv("SMTP_USERNAME", "").strip()
        password = os.getenv("SMTP_PASSWORD", "")
        if bool(username) != bool(password):
            missing_credential = "SMTP_PASSWORD" if username else "SMTP_USERNAME"
            raise RuntimeError(
                f"SMTP authentication requires {missing_credential} when the other credential is set"
            )
    return backend


def log_email_configuration() -> None:
    """Log effective delivery settings without exposing credentials."""

    backend = validate_email_configuration()
    if backend == "console":
        logger.info("Email delivery configured: backend=console")
        return
    logger.info(
        "Email delivery configured: backend=smtp host=%s port=%s security=%s "
        "timeout=%s authentication=%s from=%s",
        os.environ["SMTP_HOST"].strip(),
        int(os.getenv("SMTP_PORT", "587")),
        os.getenv("SMTP_SECURITY", "starttls").strip().lower(),
        float(os.getenv("SMTP_TIMEOUT_SECONDS", "10")),
        "enabled" if os.getenv("SMTP_USERNAME", "").strip() else "disabled",
        os.environ["SMTP_FROM_EMAIL"].strip(),
    )


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)


def hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _smtp_error_details(error: Exception, secrets_to_redact: tuple[str, ...]) -> tuple[object, object]:
    """Return SMTP response metadata even when an exception has no useful text."""

    code = getattr(error, "smtp_code", None)
    response = getattr(error, "smtp_error", None)
    if isinstance(response, bytes):
        response = response.decode("utf-8", errors="replace")
    if response is None and isinstance(error, smtplib.SMTPRecipientsRefused):
        response = error.recipients
    if response is not None:
        response = repr(response)
        for secret in secrets_to_redact:
            if secret:
                response = response.replace(secret, "[REDACTED]")
    return code, response


def send_verification_email(email: str, username: str, token: str) -> None:
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    verification_url = f"{frontend_url}/verify-email?token={quote(token, safe='')}"
    subject = "Подтверждение электронной почты"
    body = (
        f"Здравствуйте, {username}!\n\n"
        "Подтвердите адрес электронной почты, перейдя по ссылке:\n"
        f"{verification_url}\n\n"
        "Ссылка действует 24 часа."
    )

    backend = validate_email_configuration()
    if backend == "console":
        logger.info("Email verification link for %s: %s", email, verification_url)
        return
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.environ["SMTP_FROM_EMAIL"]
    message["To"] = email
    message.set_content(body)

    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    security = os.getenv("SMTP_SECURITY", "starttls").strip().lower()
    timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
    smtp_class = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    logger.info(
        "Starting verification email delivery: recipient=%s host=%s port=%s "
        "security=%s authentication=%s",
        email,
        host,
        port,
        security,
        "enabled" if os.getenv("SMTP_USERNAME", "").strip() else "disabled",
    )
    stage = "connection"
    try:
        with smtp_class(host, port, timeout=timeout) as smtp:
            logger.info("SMTP connection established: host=%s port=%s", host, port)
            if security == "starttls":
                stage = "starttls"
                smtp.starttls(context=ssl.create_default_context())
                logger.info("SMTP STARTTLS completed: host=%s port=%s", host, port)
            username_env = os.getenv("SMTP_USERNAME")
            if username_env:
                stage = "authentication"
                smtp.login(username_env, os.environ["SMTP_PASSWORD"])
                logger.info("SMTP authentication completed: username=%s", username_env)
            stage = "send"
            smtp.send_message(message)
            logger.info("Verification email accepted by SMTP server: recipient=%s", email)
    except Exception as error:
        smtp_code, smtp_response = _smtp_error_details(
            error,
            (os.getenv("SMTP_PASSWORD", ""), token),
        )
        logger.exception(
            "Verification email delivery failed: stage=%s error_type=%s "
            "smtp_code=%r smtp_response=%r host=%s port=%s security=%s "
            "recipient=%s",
            stage,
            type(error).__name__,
            smtp_code,
            smtp_response,
            host,
            port,
            security,
            email,
        )
        raise
