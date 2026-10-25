"""
Validación de la configuración del proyecto y su archivo `.ia_voy.toml` (docs/FRONTEND_SPEC.md §5.11).
El formato es el mismo de la vista previa del frontend (frontend/src/features/settings/utils/toToml.ts).
"""

import json
import logging
import tomllib
from pathlib import Path

from app.analyses.store import AnalysisStore, ProjectConfig

log = logging.getLogger(__name__)

FILENAME = ".ia_voy.toml"
MAX_RULES = 200
MAX_PATHS = 100
MAX_ITEM = 200


class ConfigError(ValueError):
    pass


def _percent(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise ConfigError(f"{name} debe ser un número entre 0 y 100")
    return float(value) if value != int(value) else int(value)


def _items(values: list[str], name: str, limit: int) -> list[str]:
    if len(values) > limit:
        raise ConfigError(f"{name}: máximo {limit} elementos")
    out: list[str] = []
    for raw in values:
        item = " ".join(str(raw).split())
        if not item:
            continue
        if len(item) > MAX_ITEM:
            raise ConfigError(f"{name}: «{item[:30]}…» es demasiado largo")
        if item not in out:
            out.append(item)
    return out


def _path(raw: str) -> str:
    """Ruta relativa al repo con "/"; las carpetas conservan su "/" final."""
    path = raw.strip().replace("\\", "/")
    while path.startswith(("./", "/")):
        path = path.removeprefix("./").lstrip("/")
    parts = [p for p in path.split("/") if p]
    if not parts or ".." in parts or ":" in parts[0]:
        raise ConfigError(f"Ruta excluida no válida: «{raw}». Usa rutas relativas al repositorio, p. ej. migrations/")
    return "/".join(parts) + ("/" if path.endswith("/") else "")


def normalize(cfg: ProjectConfig) -> ProjectConfig:
    weights = {k: _percent(cfg.weights.get(k), f"El peso de {k}") for k in ("seg", "test", "prac")}
    if sum(weights.values()) <= 0:
        raise ConfigError("Al menos un peso debe ser mayor que 0")
    thresholds = {"score": _percent(cfg.thresholds.get("score"), "El score mínimo"), "cov": _percent(cfg.thresholds.get("cov"), "La cobertura mínima")}
    ignored = _items(cfg.ignored, "Reglas ignoradas", MAX_RULES)
    excluded = list(dict.fromkeys(_path(p) for p in _items(cfg.excluded, "Rutas excluidas", MAX_PATHS)))
    return ProjectConfig(weights=weights, thresholds=thresholds, ignored=ignored, excluded=excluded)


def to_toml(cfg: ProjectConfig) -> str:
    total = sum(cfg.weights.values()) or 1
    w = {k: cfg.weights[k] / total for k in ("seg", "test", "prac")}
    lst = lambda xs: "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in xs) + "]"
    return f"""# .ia_voy.toml — configuración de IA voy (se edita desde la pantalla Configuración)
[pesos]
seguridad = {w["seg"]:.2f}
pruebas   = {w["test"]:.2f}
practicas = {w["prac"]:.2f}

[umbrales]
score_minimo     = {cfg.thresholds["score"]}
cobertura_minima = {cfg.thresholds["cov"]}

[reglas]
ignorar = {lst(cfg.ignored)}

[rutas]
excluir = {lst(cfg.excluded)}
"""


def from_toml(text: str, base: ProjectConfig) -> ProjectConfig:
    """Configuración a partir de un `.ia_voy.toml`; lo que falte se toma de `base`. ConfigError si no es válido."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{FILENAME} no es TOML válido: {exc}") from exc
    pesos, umbrales = data.get("pesos", {}), data.get("umbrales", {})
    names = {"seg": "seguridad", "test": "pruebas", "prac": "practicas"}
    weights = dict(base.weights)
    if any(n in pesos for n in names.values()):
        # El archivo guarda fracciones (0.50); la app trabaja en porcentajes (50)
        weights = {k: round(float(pesos.get(n, 0)) * 100) if isinstance(pesos.get(n, 0), (int, float)) else pesos.get(n) for k, n in names.items()}
    thresholds = {"score": umbrales.get("score_minimo", base.thresholds["score"]), "cov": umbrales.get("cobertura_minima", base.thresholds["cov"])}
    ignored = data.get("reglas", {}).get("ignorar", base.ignored)
    excluded = data.get("rutas", {}).get("excluir", base.excluded)
    if not isinstance(ignored, list) or not isinstance(excluded, list):
        raise ConfigError(f"{FILENAME}: [reglas] ignorar y [rutas] excluir deben ser listas")
    return normalize(ProjectConfig(weights=weights, thresholds=thresholds, ignored=ignored, excluded=excluded))


def import_repo_config(store: AnalysisStore, root: Path, repo_id: str) -> None:
    """Primer análisis de un repo que trae su propio `.ia_voy.toml`: se adopta. Después manda la pantalla Configuración."""
    path = root / FILENAME
    if store.has_config(repo_id) or not path.is_file():
        return
    try:
        store.save_config(repo_id, from_toml(path.read_text(encoding="utf-8", errors="replace"), store.config(repo_id)))
    except ConfigError as exc:
        log.warning("Se ignora %s de %s: %s", FILENAME, repo_id, exc)
