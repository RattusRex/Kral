"""Global and project-scoped role definitions and helpers.

The application recognises the following roles, ordered from most to least
privileged:

* ``owner``       - full control of the system. Only the owner may manage the
  ``head_admin`` role or touch other owners.
* ``project_owner`` - full control within a project, but no global-owner
  permissions.
* ``head_admin``  - "Главный Администратор". A trusted deputy of the owner that
  wields every administrative power of the owner *except* the ability to manage
  the owner (changing, blocking, deleting or appointing owners) or to grant the
  ``head_admin``/``owner`` roles themselves.
* ``admin``       - game master tools (karma, currency, items, logs) but no
  ability to manage users or roles.
* ``technician``  - resource grants, logs, character editing and calendar
  administration, but no role, project-settings or character-deletion powers.
* ``player``      - default role, may only manage their own characters and
  participate in the chat.
"""


class Role:
    OWNER = "owner"
    PROJECT_OWNER = "project_owner"
    HEAD_ADMIN = "head_admin"
    ADMIN = "admin"
    TECHNICIAN = "technician"
    PLAYER = "player"


# All valid role identifiers.
PROJECT_ROLES = (
    Role.PROJECT_OWNER,
    Role.HEAD_ADMIN,
    Role.ADMIN,
    Role.TECHNICIAN,
    Role.PLAYER,
)
VALID_ROLES = (Role.OWNER, *PROJECT_ROLES)

ROLE_RANK = {
    Role.PLAYER: 0,
    Role.TECHNICIAN: 1,
    Role.ADMIN: 2,
    Role.HEAD_ADMIN: 3,
    Role.PROJECT_OWNER: 4,
    Role.OWNER: 5,
}

# Roles that may use the game-master / administrative endpoints.
ADMIN_ROLES = (
    Role.OWNER,
    Role.PROJECT_OWNER,
    Role.HEAD_ADMIN,
    Role.ADMIN,
    Role.TECHNICIAN,
)

# Roles that may manage other users' roles.
ROLE_MANAGER_ROLES = (Role.OWNER, Role.HEAD_ADMIN)


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


def is_head_admin_role(role: str | None) -> bool:
    return normalize_role(role) == Role.HEAD_ADMIN


def can_manage_roles(role: str | None) -> bool:
    """True for roles allowed to change other users' roles (owner, head admin)."""
    return normalize_role(role) in ROLE_MANAGER_ROLES
