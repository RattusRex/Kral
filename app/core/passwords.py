MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_BYTES = 72

PASSWORD_POLICY_DETAIL = f"Пароль должен содержать не менее {MIN_PASSWORD_LENGTH} символов"


def password_exceeds_bcrypt_limit(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


def ensure_password_within_bcrypt_limit(password: str) -> None:
    if password_exceeds_bcrypt_limit(password):
        raise ValueError(
            f"Пароль должен содержать не более {MAX_PASSWORD_BYTES} байт "
            "в кодировке UTF-8"
        )


def new_password_policy_error(password: str) -> str | None:
    """Return a safe validation message; never log or transmit the password."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return PASSWORD_POLICY_DETAIL

    return None
