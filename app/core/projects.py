from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.character import Character
from app.core.roles import ROLE_RANK, Role
from app.models.project import ProjectMembership
from app.models.user import User


def membership_for(db: Session, user: User, project_id: int) -> ProjectMembership | None:
    return db.query(ProjectMembership).filter(
        ProjectMembership.user_id == user.id,
        ProjectMembership.project_id == project_id,
    ).first()


def require_project_access(db: Session, user: User, project_id: int) -> ProjectMembership | None:
    if user.is_owner:
        return membership_for(db, user, project_id)
    membership = membership_for(db, user, project_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Project access required")
    return membership


def require_project_admin(db: Session, user: User, project_id: int) -> ProjectMembership | None:
    if user.is_owner:
        return membership_for(db, user, project_id)
    membership = membership_for(db, user, project_id)
    if not membership or ROLE_RANK.get(membership.role, -1) < ROLE_RANK[Role.TECHNICIAN]:
        raise HTTPException(status_code=403, detail="Project admin permissions required")
    return membership


def accessible_project_ids(db: Session, user: User) -> list[int] | None:
    if user.is_owner:
        return None
    return [row.project_id for row in db.query(ProjectMembership).filter(
        ProjectMembership.user_id == user.id
    )]


def admin_project_ids(db: Session, user: User) -> list[int] | None:
    if user.is_owner:
        return None
    return [row.project_id for row in db.query(ProjectMembership).filter(
        ProjectMembership.user_id == user.id,
        ProjectMembership.role.in_((
            Role.PROJECT_OWNER, Role.HEAD_ADMIN, Role.ADMIN, Role.TECHNICIAN,
        )),
    )]


def get_admin_character_or_404(
    db: Session, user: User, character_id: int
) -> Character:
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    try:
        require_project_admin(db, user, character.project_id)
    except HTTPException:
        # Do not disclose that a character exists in another project.
        raise HTTPException(status_code=404, detail="Character not found")
    return character
