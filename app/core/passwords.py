MAX_PASSWORD_BYTES = 72


def password_exceeds_bcrypt_limit(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


def ensure_password_within_bcrypt_limit(password: str) -> None:
    if password_exceeds_bcrypt_limit(password):
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
