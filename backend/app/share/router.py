"""
Compartir un reporte con un enlace público (docs/FRONTEND_SPEC.md §5.7 y §5.12):
POST /api/report/{id}/share (con sesión) y la vista de solo lectura GET /api/public/r/{id} (sin sesión).

El enlace muestra el score y los hallazgos abiertos de severidad alta y media, con la configuración
actual del proyecto. Los fragmentos de código solo se incluyen si quien comparte lo pidió.
Con contraseña, POST /api/public/r/{id}/unlock la canjea por un token temporal firmado (HMAC) que el
frontend manda como `?token=`: la contraseña nunca se guarda ni viaja en las siguientes peticiones.
"""

import hashlib
import hmac
import secrets
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from app.analyses.access import Analyses, UserId
from app.analyses.schemas import Finding, Scores
from app.analyses.views import finding_view, scores, visible
from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.reports.router import find_report

router = APIRouter(prefix="/api", tags=["compartir"])

UNLOCK_TTL_S = 12 * 3600
# Intentos fallidos de contraseña por enlace antes de bloquearlo un rato (anti fuerza bruta)
MAX_FAILURES = 10
FAILURE_WINDOW_S = 15 * 60


class ShareRequest(BaseModel):
    password: str | None = Field(default=None, max_length=200)
    # 0 = nunca expira
    expires_days: Literal[0, 1, 7, 30] = 7
    include_code: bool = False


class ShareResponse(BaseModel):
    share_id: str
    url: str
    expires_at: str | None


class PublicReport(BaseModel):
    repo_name: str
    branch: str
    commit: str
    created_at: str
    scores: Scores
    findings: list[Finding]
    shared_by: str
    expires_at: str | None
    include_code: bool


class UnlockRequest(BaseModel):
    password: str = Field(max_length=200)


class UnlockResponse(BaseModel):
    token: str


# ───────────────────────── Contraseñas y tokens ─────────────────────────


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    salt, _, digest = stored.partition("$")
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
    return hmac.compare_digest(candidate.hex(), digest)


def _sign(share_id: str, exp: int, key: str) -> str:
    return hmac.new(key.encode(), f"share:{share_id}:{exp}".encode(), hashlib.sha256).hexdigest()


def issue_unlock_token(share_id: str, settings: Settings) -> str:
    exp = int(time.time()) + UNLOCK_TTL_S
    return f"{exp}.{_sign(share_id, exp, settings.secret_key)}"


def valid_unlock_token(share_id: str, token: str | None, settings: Settings) -> bool:
    exp, _, signature = (token or "").partition(".")
    if not exp.isdigit() or int(exp) < time.time():
        return False
    return hmac.compare_digest(signature, _sign(share_id, int(exp), settings.secret_key))


class FailedAttempts:
    """Intentos fallidos recientes por enlace, en SQLite (tabla share_failures): valen para todos los workers."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def blocked(self, share_id: str) -> bool:
        since = time.time() - FAILURE_WINDOW_S
        return self.conn.execute("SELECT COUNT(*) FROM share_failures WHERE share_id = ? AND at > ?", (share_id, since)).fetchone()[0] >= MAX_FAILURES

    def add(self, share_id: str) -> None:
        now = time.time()
        self.conn.execute("DELETE FROM share_failures WHERE at <= ?", (now - FAILURE_WINDOW_S,))
        self.conn.execute("INSERT INTO share_failures (share_id, at) VALUES (?, ?)", (share_id, now))
        self.conn.commit()


def get_failed_attempts(conn: sqlite3.Connection = Depends(get_db)) -> FailedAttempts:
    return FailedAttempts(conn)


# ───────────────────────── Rutas ─────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds").replace("+00:00", "Z")


@router.post("/report/{report_id}/share", response_model=ShareResponse)
def create_share(
    report_id: str, body: ShareRequest, store: Analyses, user_id: UserId,
    repo: str | None = Query(default=None, max_length=64), origin: str | None = Header(default=None), settings: Settings = Depends(get_settings),
) -> ShareResponse:
    _, report = find_report(store, user_id, report_id, repo)
    share_id = secrets.token_urlsafe(9)
    expires_at = _iso(_now() + timedelta(days=body.expires_days)) if body.expires_days else None
    password = hash_password(body.password) if body.password else None
    store.conn.execute(
        "INSERT INTO shares (id, report_id, user_id, password_hash, expires_at, include_code, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (share_id, report["id"], user_id, password, expires_at, int(body.include_code), _iso(_now())),
    )
    store.conn.commit()
    # El enlace usa el origen desde el que se pidió (localhost o el túnel público); si no llega, FRONTEND_URL
    base = (origin if origin and origin.startswith(("http://", "https://")) else settings.frontend_url).rstrip("/")
    return ShareResponse(share_id=share_id, url=f"{base}/r/{share_id}", expires_at=expires_at)


def _open_share(conn: sqlite3.Connection, share_id: str) -> sqlite3.Row:
    """El enlace vigente; 404 si no existe y 410 si expiró."""
    share = conn.execute("SELECT * FROM shares WHERE id = ?", (share_id,)).fetchone()
    if share is None:
        raise ApiError(404, "not_found", "Este enlace no existe")
    if share["expires_at"] and datetime.fromisoformat(share["expires_at"]) < _now():
        raise ApiError(410, "expired", "Este enlace expiró")
    return share


@router.get("/public/r/{share_id}", response_model=PublicReport)
def public_report(share_id: str, store: Analyses, token: str | None = Query(default=None, max_length=200), settings: Settings = Depends(get_settings)) -> PublicReport:
    share = _open_share(store.conn, share_id)
    if share["password_hash"] and not valid_unlock_token(share_id, token, settings):
        raise ApiError(401, "password_required", "Este reporte está protegido")
    report = store.report(share["report_id"])
    repo = store.repo(report["repo_id"]) if report else None
    if report is None or repo is None:
        raise ApiError(404, "not_found", "Este enlace no existe")
    cfg = store.config(repo["id"])
    rows = visible(store.findings(report["id"]), cfg)
    author = store.conn.execute("SELECT name FROM users WHERE id = ?", (share["user_id"],)).fetchone()
    include_code = bool(share["include_code"])
    return PublicReport(
        repo_name=repo["name"],
        branch=report["branch"],
        commit=report["commit_sha"],
        created_at=report["created_at"],
        scores=scores(report, rows, cfg),
        findings=[finding_view(f, with_code=include_code) for f in rows if f["status"] == "open" and f["sev"] != "baja"],
        shared_by=author["name"] if author else "un usuario de IA voy",
        expires_at=share["expires_at"],
        include_code=include_code,
    )


@router.post("/public/r/{share_id}/unlock", response_model=UnlockResponse)
def unlock(
    share_id: str, body: UnlockRequest, store: Analyses, settings: Settings = Depends(get_settings), attempts: FailedAttempts = Depends(get_failed_attempts),
) -> UnlockResponse:
    share = _open_share(store.conn, share_id)
    if not share["password_hash"]:
        return UnlockResponse(token=issue_unlock_token(share_id, settings))
    if attempts.blocked(share_id):
        raise ApiError(429, "too_many_attempts", "Demasiados intentos. Espera unos minutos y vuelve a intentarlo.")
    if not check_password(body.password, share["password_hash"]):
        attempts.add(share_id)
        raise ApiError(403, "wrong_password", "Contraseña incorrecta")
    return UnlockResponse(token=issue_unlock_token(share_id, settings))
