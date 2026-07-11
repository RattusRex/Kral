from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.users import get_current_user, get_db
from app.core.roles import PROJECT_ROLES, ROLE_RANK, Role, normalize_role
from app.models.project import DEFAULT_FEATURES, Project, ProjectMembership
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectFeaturesUpdate, ProjectRoleUpdate


router = APIRouter(prefix="/projects")


def serialize_project(project: Project, membership: ProjectMembership | None, user: User) -> dict:
    role = Role.OWNER if user.is_owner else membership.role if membership else None
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "role": role,
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
    if not membership or ROLE_RANK.get(membership.role, -1) < required_rank:
        raise HTTPException(status_code=403, detail="Project permissions required")
    return project, membership.role


def get_current_project_access(
    x_project_id: int | None = Header(default=None, alias="X-Project-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[Project, str]:
    if x_project_id is None:
        if not current_user.is_owner:
            memberships = db.query(ProjectMembership).filter(
                ProjectMembership.user_id == current_user.id
            ).order_by(ProjectMembership.id).all()
            non_default = [item for item in memberships if not item.project.is_default]
            if len(non_default) == 1:
                return non_default[0].project, non_default[0].role
        project = db.query(Project).filter(Project.is_default.is_(True)).first()
        if not project:
            raise HTTPException(status_code=400, detail="X-Project-ID header is required")
        x_project_id = project.id
    return get_project_access(x_project_id, current_user, db)


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
        return [serialize_project(project, None, current_user) for project in projects]
    memberships = db.query(ProjectMembership).filter(ProjectMembership.user_id == current_user.id).all()
    return [serialize_project(item.project, item, current_user) for item in memberships]


@router.post("")
def create_project(data: ProjectCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_owner:
        raise HTTPException(status_code=403, detail="Owner permissions required")
    slug = data.slug or "-".join(data.name.strip().lower().split())
    if db.query(Project).filter(Project.slug == slug).first():
        raise HTTPException(status_code=409, detail="Project slug already exists")
    project = Project(
        name=data.name.strip(),
        slug=slug,
        owner_id=current_user.id,
        features=dict(DEFAULT_FEATURES),
        settings={},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return serialize_project(project, None, current_user)


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
    return serialize_project(project, None, current_user) | {"role": role}


@router.patch("/{project_id}/settings")
def update_settings(data: ProjectFeaturesUpdate, project_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project, _ = get_project_access(project_id, current_user, db, required_rank=ROLE_RANK[Role.HEAD_ADMIN])
    unknown = set(data.features) - set(DEFAULT_FEATURES)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown features: {', '.join(sorted(unknown))}")
    project.features = {**DEFAULT_FEATURES, **(project.features or {}), **data.features}
    db.commit()
    db.refresh(project)
    return serialize_project(project, None, current_user)


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
