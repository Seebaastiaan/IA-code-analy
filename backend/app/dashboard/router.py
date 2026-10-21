"""Lista de repositorios del equipo (docs/FRONTEND_SPEC.md §5.4 y §6.2)."""

from fastapi import APIRouter

from app.analyses.access import Analyses, Jobs, UserId
from app.analyses.schemas import Repo
from app.analyses.views import repo_view

router = APIRouter(prefix="/api", tags=["tablero"])


@router.get("/repos", response_model=list[Repo])
def list_repos(store: Analyses, user_id: UserId, jobs: Jobs) -> list[Repo]:
    return [repo_view(store, jobs, r) for r in store.repos(user_id)]
