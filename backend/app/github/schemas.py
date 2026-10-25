"""Modelos del contrato /api/github (docs/FRONTEND_SPEC.md §6.10, frontend/src/features/github/types.ts)."""

from pydantic import BaseModel


class GithubStatus(BaseModel):
    connected: bool
    login: str | None = None
    avatar_url: str | None = None


class GithubRepo(BaseModel):
    full_name: str
    html_url: str
    default_branch: str
    private: bool
    description: str | None
    pushed_at: str


class GithubBranch(BaseModel):
    name: str
