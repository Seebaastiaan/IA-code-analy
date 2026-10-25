"""
Analizadores de Seguridad del Sprint 5 sobre el clon:
- Bandit (paso 4): lee el código y corre en el backend (`analyze_static`).
- pip-audit (paso 5): revisa las dependencias instaladas en el sandbox (app.analysis.sandbox); aquí se
  convierten sus resultados en hallazgos (`audit_findings`).

Respeta la configuración del proyecto: las rutas excluidas no se analizan.
"""

import re
from dataclasses import dataclass

from app.analyses.analyzers import bandit_findings_dir
from app.analyses.models import FindingInput
from app.analyses.store import AnalysisStore
from app.analyses.workspace import Workspace
from app.analysis.sandbox import SandboxOutput, parse_audit
from app.config import Settings
from app.db import session
from app.errors import ApiError


@dataclass
class StaticResult:
    """Lo que sale de leer el código (Bandit), sin ejecutarlo."""

    files: list[str]
    findings: list[FindingInput]


def analyze_static(settings: Settings, repo_id: str) -> StaticResult:
    """Bandit sobre el clon. Bloqueante: el job lo llama con asyncio.to_thread."""
    ws = Workspace(settings, repo_id)
    with session(settings.database_path) as conn:
        cfg = AnalysisStore(conn).config(repo_id)
    files = ws.list_files(cfg.excluded)
    return StaticResult(files=files, findings=bandit_findings_dir(ws.root, files))


def bandit_summary(findings: list[FindingInput]) -> str:
    count = {s: sum(1 for f in findings if f.sev == s) for s in ("alta", "media", "baja")}
    return f"  {count['alta']} alta · {count['media']} media · {count['baja']} baja"


# ───────────────────────── Resultados del sandbox ─────────────────────────


def _deps_file(files: list[str]) -> str:
    return next((f for f in ("requirements.txt", "pyproject.toml", "setup.py") if f in files), "requirements.txt")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _package_line(lines: list[str] | None, package: str) -> int:
    """Línea del archivo de dependencias que menciona el paquete (1 si no aparece: es una dependencia indirecta)."""
    target = _normalize(package)
    for i, text in enumerate(lines or [], start=1):
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", text)
        if m and _normalize(m.group(1)) == target:
            return i
    return 1


def audit_findings(ws: Workspace, files: list[str], out: SandboxOutput) -> list[FindingInput]:
    """Un hallazgo alto por cada paquete vulnerable, en la línea donde se declara."""
    deps = _deps_file(files)
    lines = None
    if deps in files:
        try:
            lines = ws.read(deps).splitlines()
        except ApiError:
            pass  # binario o demasiado grande: los hallazgos quedan en la línea 1
    findings = []
    for v in parse_audit(out.audit):
        fix = f"Actualizar a {v.package} {v.fix_versions[0]} o superior" if v.fix_versions else "No hay versión corregida publicada: evalúa reemplazar el paquete"
        findings.append(FindingInput(
            sev="alta", cat="seg", tool="pip-audit", rule=f"{v.package} {v.version}", file=deps, line=_package_line(lines, v.package),
            msg=f"{v.package} {v.version} tiene {len(v.ids)} vulnerabilidad(es) conocida(s): {', '.join(v.ids[:5])}",
            why=v.description[:400] or "La versión instalada tiene avisos de seguridad publicados.",
            rec=f"{fix} y volver a correr las pruebas.",
        ))
    return findings


def install_finding(files: list[str], log_tail: str) -> FindingInput:
    """Las dependencias no se instalaron: pip-audit no puede revisarlas y el proyecto no arrancaría limpio."""
    return FindingInput(
        sev="alta", cat="seg", tool="pip-audit", rule="DEPS", file=_deps_file(files), line=1, code="",
        msg="No se pudieron instalar las dependencias del proyecto",
        why=f"Sin dependencias instaladas pip-audit no puede revisarlas. Salida de la instalación:\n{log_tail[-600:]}",
        rec="Revisa que requirements.txt (o pyproject.toml) tenga versiones que existan y se instalen en Python 3.12.",
    )
