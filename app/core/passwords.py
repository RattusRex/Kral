MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_BYTES = 72

# A deliberately small local deny-list catches the passwords browsers and
# password managers most commonly flag without sending a user's password (or a
# derivative of it) to a third-party breach-checking service.
COMMON_COMPROMISED_PASSWORDS = frozenset({
    "12345678",
    "admin123",
    "letmein123",
    "password",
    "password123",
    "qwerty123",
    "secret123",
})

PASSWORD_POLICY_DETAIL = (
    "Password must be at least 12 characters and include uppercase, lowercase, "
    "number, and special characters"
)
COMPROMISED_PASSWORD_DETAIL = (
    "Choose a less common password that has not appeared in known breaches"
)


def password_exceeds_bcrypt_limit(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


def ensure_password_within_bcrypt_limit(password: str) -> None:
    if password_exceeds_bcrypt_limit(password):
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")


def new_password_policy_error(password: str) -> str | None:
    """Return a safe validation message; never log or transmit the password."""
    if password.casefold() in COMMON_COMPROMISED_PASSWORDS:
        return COMPROMISED_PASSWORD_DETAIL

    has_required_classes = all((
        any(character.isupper() for character in password),
        any(character.islower() for character in password),
        any(character.isdigit() for character in password),
        any(not character.isalnum() for character in password),
    ))
    if len(password) < MIN_PASSWORD_LENGTH or not has_required_classes:
        return PASSWORD_POLICY_DETAIL

    return None
