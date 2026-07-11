from __future__ import annotations

import hashlib
import logging
import os
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

logger = logging.getLogger(__name__)


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)


def hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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

    backend = os.getenv("EMAIL_BACKEND", "console").lower()
    if backend == "console":
        logger.info("Email verification link for %s: %s", email, verification_url)
        return
    if backend != "smtp":
        raise RuntimeError("EMAIL_BACKEND must be 'console' or 'smtp'")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.environ["SMTP_FROM_EMAIL"]
    message["To"] = email
    message.set_content(body)

    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    with smtplib.SMTP(host, port) as smtp:
        if use_tls:
            smtp.starttls()
        username_env = os.getenv("SMTP_USERNAME")
        if username_env:
            smtp.login(username_env, os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(message)
