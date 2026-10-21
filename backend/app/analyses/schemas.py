"""Modelos compartidos del contrato (frontend/src/shared/types/common.ts, features/{repos,findings}/types.ts)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["alta", "media", "baja"]
Category = Literal["seg", "test", "prac"]


class Weights(BaseModel):
    seg: float
    test: float
    prac: float


class Scores(Weights):
    # "global" es palabra reservada en Python: se expone con alias
    global_: float = Field(alias="global")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class Thresholds(BaseModel):
    score: float
    cov: float


class SnippetLine(BaseModel):
    line: int
    text: str


class Finding(BaseModel):
    id: int
    sev: Severity
    cat: Category
    tool: str
    rule: str
    file: str
    line: int
    msg: str
    why: str
    rec: str
    fix: bool
    status: Literal["open", "resolved"]
    snippet: list[SnippetLine] | None = None


class Progress(BaseModel):
    job_id: str
    step: int
    total: int
    name: str


class Repo(BaseModel):
    id: str
    name: str
    url: str
    branch: str
    commit: str | None
    status: Literal["listo", "analizando", "error"]
    last_analyzed_at: str | None
    files: int
    last_report_id: str | None
    last_report_num: int | None
    scores: Scores | None
    error: str | None
    progress: Progress | None = None
