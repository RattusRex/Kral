"""User role definitions and helpers.

The application recognises three roles, ordered from most to least privileged:

* ``owner``  - full control, including user and role management.
* ``admin``  - game master tools (karma, currency, items, logs) but no
  ability to manage users or roles.
* ``player`` - default role, may only manage their own characters and
  participate in the chat.
"""


class Role:
    OWNER = "owner"
    ADMIN = "admin"
    PLAYER = "player"


# All valid role identifiers.
VALID_ROLES = (Role.OWNER, Role.ADMIN, Role.PLAYER)

# Roles that may use the game-master / administrative endpoints.
ADMIN_ROLES = (Role.OWNER, Role.ADMIN)


def normalize_role(role: str | None) -> str:
    """Return a valid role string, defaulting to ``player``."""
    if not role:
        return Role.PLAYER
    candidate = role.strip().lower()
    return candidate if candidate in VALID_ROLES else Role.PLAYER


def is_admin_role(role: str | None) -> bool:
    return normalize_role(role) in ADMIN_ROLES


def is_owner_role(role: str | None) -> bool:
    return normalize_role(role) == Role.OWNER
