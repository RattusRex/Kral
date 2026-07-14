import re
import unicodedata
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.users import get_current_user, get_db
from app.core.roles import PROJECT_ROLES, ROLE_RANK, Role, normalize_role
from app.models.project import DEFAULT_FEATURES, Project, ProjectAuditLog, ProjectMembership
from app.models.character import Character
from app.models.chat import ChatMessage
from app.models.content import ContentBlock
from app.models.recruitment import GameRecruitment
from app.models.inventory import AdminGrantLog, KarmaPurchase, MarketSaleLog, ShopTransactionLog, TransferLog
from app.models.character import CalendarAuditLog
from app.models.user import User
from app.schemas.project import (
    ProjectAvailabilityUpdate,
    ProjectCreate,
    ProjectFeaturesUpdate,
    ProjectRoleUpdate,
)


router = APIRouter(prefix="/projects")


def generate_project_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug[:100] or f"project-{uuid4().hex[:12]}"


def available_project_slug(name: str, db: Session) -> str:
    base = generate_project_slug(name)
    slug = base
    suffix = 2
    while db.query(Project).filter(Project.slug == slug).first():
        marker = f"-{suffix}"
        slug = f"{base[:100 - len(marker)]}{marker}"
        suffix += 1
    return slug


def serialize_project(project: Project, membership: ProjectMembership | None, user: User) -> dict:
    role = Role.OWNER if user.is_owner else membership.role if membership else None
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "is_default": project.is_default,
        "is_selectable": project.is_selectable,
        "role": role,
        "karma": membership.karma if membership else 0,
        "features": {**DEFAULT_FEATURES, **(project.features or {})},
        "can_manage_settings": user.is_owner or role in (Role.PROJECT_OWNER, Role.HEAD_ADMIN),
        "can_manage_roles": user.is_owner or role in (Role.PROJECT_OWNER, Role.HEAD_ADMIN),
        "is_admin": user.is_owner or role in (
            Role.PROJECT_OWNER, Role.HEAD_ADMIN, Role.ADMIN, Role.TECHNICIAN
        ),
    }


def get_project_access(
    project_id: int,
    current_user: User,
    db: Session,
    *,
    required_rank: int = 0,
) -> tuple[Project, str]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user.is_owner:
        return project, Role.OWNER
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project.id,
        ProjectMembership.user_id == current_user.id,
    ).first()
    # Selection availability is the invitation boundary for public projects.
    # Materialize the least-privileged membership only when the user actually
    # enters one; listing projects remains read-only.
    if not membership and project.is_selectable and required_rank == 0:
        membership = ProjectMembership(
            project_id=project.id,
            user_id=current_user.id,
            role=Role.PLAYER,
        )
        db.add(membership)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            membership = db.query(ProjectMembership).filter(
                ProjectMembership.project_id == project.id,
                ProjectMembership.user_id == current_user.id,
            ).first()
    if not membership or ROLE_RANK.get(membership.role, -1) < required_rank:
        raise HTTPException(status_code=403, detail="Project permissions required")
    return project, membership.role


def get_current_project_access(
    x_project_id: int | None = Header(default=None, alias="X-Project-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[Project, str]:
    if x_project_id is None:
        raise HTTPException(status_code=400, detail="X-Project-ID header is required")
    access = get_project_access(x_project_id, current_user, db)
    current_user.active_project_id = access[0].id
    current_user.active_project_role = access[1]
    return access


def require_project_admin(
    access: tuple[Project, str] = Depends(get_current_project_access),
) -> tuple[Project, str]:
    if ROLE_RANK[access[1]] < ROLE_RANK[Role.TECHNICIAN]:
        raise HTTPException(status_code=403, detail="Project admin permissions required")
    return access


def require_project_game_master(
    access: tuple[Project, str] = Depends(get_current_project_access),
) -> tuple[Project, str]:
    if ROLE_RANK[access[1]] < ROLE_RANK[Role.ADMIN]:
        raise HTTPException(status_code=403, detail="Game master permissions required")
    return access


def require_feature(feature: str):
    def dependency(access: tuple[Project, str] = Depends(get_current_project_access)) -> Project:
        project = access[0]
        if not {**DEFAULT_FEATURES, **(project.features or {})}.get(feature, False):
            raise HTTPException(status_code=403, detail=f"Project feature disabled: {feature}")
        return project
    return dependency


@router.get("")
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_owner:
        projects = db.query(Project).order_by(Project.id).all()
        memberships = {
            item.project_id: item for item in db.query(ProjectMembership).filter(
                ProjectMembership.user_id == current_user.id
            ).all()
        }
        return [serialize_project(project, memberships.get(project.id), current_user) for project in projects]
    # A visible project must be discoverable before membership exists. Existing
    # memberships are included only to expose their already-assigned role and
    # project-local karma in the selection UI.
    memberships = {
        item.project_id: item for item in db.query(ProjectMembership).filter(
            ProjectMembership.user_id == current_user.id
        ).all()
    }
    projects = db.query(Project).filter(
        Project.is_selectable.is_(True)
    ).order_by(Project.id).all()
    return [serialize_project(project, memberships.get(project.id), current_user) for project in projects]


@router.post("")
def create_project(data: ProjectCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_owner:
        raise HTTPException(status_code=403, detail="Owner permissions required")
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Project name cannot be blank")
    if db.query(Project).filter(Project.name == name).first():
        raise HTTPException(status_code=409, detail="Project name already exists")
    slug = data.slug or available_project_slug(name, db)
    if db.query(Project).filter(Project.slug == slug).first():
        raise HTTPException(status_code=409, detail="Project slug already exists")
    project = Project(
        name=name,
        slug=slug,
        owner_id=current_user.id,
        features=dict(DEFAULT_FEATURES),
        settings={},
    )
    db.add(project)
    db.flush()
    membership = ProjectMembership(
        project_id=project.id,
        user_id=current_user.id,
        role=Role.PROJECT_OWNER,
    )
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project name or slug already exists")
    db.refresh(project)
    return serialize_project(project, membership, current_user)


@router.patch("/{project_id}/availability")
def update_availability(
    data: ProjectAvailabilityUpdate,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_owner:
        raise HTTPException(status_code=403, detail="Owner permissions required")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.is_selectable = data.is_selectable
    db.commit()
    db.refresh(project)
    membership = db.query(ProjectMembership).filter_by(
        project_id=project.id, user_id=current_user.id
    ).first()
    return serialize_project(project, membership, current_user)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_owner:
        raise HTTPException(status_code=403, detail="Owner permissions required")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.is_default:
        raise HTTPException(status_code=409, detail="The default project cannot be deleted")

    db.add(ProjectAuditLog(
        admin_id=current_user.id,
        admin_username=current_user.username,
        project_id=project.id,
        project_name=project.name,
        action="delete",
    ))
    # Project data predates consistent database-level ON DELETE cascades. Delete
    # project roots through the ORM so their existing delete-orphan cascades run.
    for recruitment in db.query(GameRecruitment).filter_by(project_id=project.id).all():
        db.delete(recruitment)
    for character in db.query(Character).filter_by(project_id=project.id).all():
        db.delete(character)
    db.query(ChatMessage).filter_by(project_id=project.id).delete(synchronize_session=False)
    db.query(ContentBlock).filter_by(project_id=project.id).delete(synchronize_session=False)
    for model in (
        ShopTransactionLog, MarketSaleLog, TransferLog, AdminGrantLog,
        CalendarAuditLog, KarmaPurchase,
    ):
        db.query(model).filter_by(project_id=project.id).delete(synchronize_session=False)
    db.query(ProjectMembership).filter_by(project_id=project.id).delete(synchronize_session=False)
    db.delete(project)
    db.commit()


@router.get("/current")
def current_project(
    access: tuple[Project, str] = Depends(get_current_project_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == access[0].id,
        ProjectMembership.user_id == current_user.id,
    ).first()
    return serialize_project(access[0], membership, current_user)


@router.get("/{project_id}/settings")
def get_settings(project_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project, role = get_project_access(project_id, current_user, db, required_rank=ROLE_RANK[Role.HEAD_ADMIN])
    membership = db.query(ProjectMembership).filter_by(project_id=project.id, user_id=current_user.id).first()
    return serialize_project(project, membership, current_user) | {"role": role}


@router.patch("/{project_id}/settings")
def update_settings(data: ProjectFeaturesUpdate, project_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project, _ = get_project_access(project_id, current_user, db, required_rank=ROLE_RANK[Role.HEAD_ADMIN])
    unknown = set(data.features) - set(DEFAULT_FEATURES)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown features: {', '.join(sorted(unknown))}")
    project.features = {**DEFAULT_FEATURES, **(project.features or {}), **data.features}
    db.commit()
    db.refresh(project)
    membership = db.query(ProjectMembership).filter_by(project_id=project.id, user_id=current_user.id).first()
    return serialize_project(project, membership, current_user)


@router.get("/{project_id}/members")
def list_members(project_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project, _ = get_project_access(project_id, current_user, db, required_rank=ROLE_RANK[Role.HEAD_ADMIN])
    return [{"user_id": item.user_id, "username": item.user.username, "role": item.role} for item in project.memberships]


@router.put("/{project_id}/members/{user_id}")
def set_member_role(data: ProjectRoleUpdate, project_id: int, user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project, actor_role = get_project_access(project_id, current_user, db, required_rank=ROLE_RANK[Role.HEAD_ADMIN])
    requested_role = normalize_role(data.role)
    if data.role.strip().lower() not in PROJECT_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(PROJECT_ROLES)}")
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project.id,
        ProjectMembership.user_id == user_id,
    ).first()
    target_role = membership.role if membership else Role.PLAYER
    if not current_user.is_owner:
        if target_role == Role.PROJECT_OWNER:
            raise HTTPException(status_code=403, detail="Only the global owner may manage project owners")
        if ROLE_RANK[requested_role] >= ROLE_RANK[actor_role]:
            raise HTTPException(status_code=403, detail="Cannot assign an equal or higher role")
        if ROLE_RANK[target_role] >= ROLE_RANK[actor_role] and membership:
            raise HTTPException(status_code=403, detail="Cannot manage an equal or higher role")
    if membership:
        membership.role = requested_role
    else:
        membership = ProjectMembership(project_id=project.id, user_id=user_id, role=requested_role)
        db.add(membership)
    db.commit()
    return {"user_id": user_id, "username": target_user.username, "role": membership.role}
