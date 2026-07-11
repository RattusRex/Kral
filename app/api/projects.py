from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.users import get_current_user, get_db
from app.models.project import PROJECT_ROLES, Project, ProjectMembership
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectMembershipCreate, ProjectMembershipUpdate


router = APIRouter(prefix="/projects")


def serialize_project(project: Project, user: User) -> dict:
    membership = next((row for row in project.memberships if row.user_id == user.id), None)
    return {
        "id": project.id,
        "name": project.name,
        "created_at": project.created_at,
        "owner_id": project.owner_id,
        "settings": project.settings,
        "role": "owner" if user.is_owner else membership.role if membership else None,
    }


def project_or_404(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("")
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Project).order_by(Project.name)
    if not user.is_owner:
        query = query.join(ProjectMembership).filter(ProjectMembership.user_id == user.id)
    return [serialize_project(project, user) for project in query.all()]


@router.post("")
def create_project(data: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.is_owner:
        raise HTTPException(status_code=403, detail="Owner permissions required")
    project = Project(name=data.name.strip(), owner_id=user.id, settings={})
    db.add(project)
    try:
        db.flush()
        db.add(ProjectMembership(project_id=project.id, user_id=user.id, role="admin"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project name already exists")
    db.refresh(project)
    return serialize_project(project, user)


@router.get("/{project_id}/members")
def list_members(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = project_or_404(db, project_id)
    if not user.is_owner:
        membership = next((row for row in project.memberships if row.user_id == user.id), None)
        if not membership or membership.role != "admin":
            raise HTTPException(status_code=403, detail="Project admin permissions required")
    return [{"user_id": row.user_id, "username": row.user.username, "role": row.role} for row in project.memberships]


@router.post("/{project_id}/members")
def add_member(project_id: int, data: ProjectMembershipCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.is_owner:
        raise HTTPException(status_code=403, detail="Owner permissions required")
    project_or_404(db, project_id)
    if data.role not in PROJECT_ROLES:
        raise HTTPException(status_code=400, detail="Unknown project role")
    if not db.query(User).filter(User.id == data.user_id).first():
        raise HTTPException(status_code=404, detail="User not found")
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == data.user_id,
    ).first()
    if membership:
        membership.role = data.role
    else:
        membership = ProjectMembership(project_id=project_id, user_id=data.user_id, role=data.role)
        db.add(membership)
    db.commit()
    return {"user_id": membership.user_id, "role": membership.role}


@router.patch("/{project_id}/members/{user_id}")
def update_member(project_id: int, user_id: int, data: ProjectMembershipUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return add_member(project_id, ProjectMembershipCreate(user_id=user_id, role=data.role), db, user)
