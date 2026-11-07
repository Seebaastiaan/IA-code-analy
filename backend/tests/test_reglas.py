"""Reglas de negocio del repo analizado (app.analyses.reglas, ADR-003): archivo, validación, nivel patrón y API."""

from pathlib import Path

import pytest

from app.analyses import reglas
from app.analyses.reglas import RulesError, parse
from app.analysis import clone as clone_mod
from app.analysis import fake
from app.analysis.clone import CloneResult
from app.config import Settings
from app.seed import seed
from tests.conftest import FakeCloner, login
from tests.test_analysis import URL, wait_done

VALIDO = '''
[proyecto]
nombre = "Tienda escolar"
version = 1.2

[[regla]]
id          = "RN-001"
titulo      = "Montos con Decimal"
descripcion = "Todo monto se calcula con Decimal."
severidad   = "alta"
rutas       = ["./app\\\\pagos/", "app/pagos/"]
prohibido   = 'float\\('
historia    = "HU-03"

[[regla]]
id          = "RN-002"
titulo      = "Cancelado no vuelve a pagado"
descripcion = "Un pedido cancelado no cambia a pagado."
severidad   = "media"
'''


def regla(**campos: str) -> str:
    base = {"id": '"RN-001"', "titulo": '"T"', "descripcion": '"D"', "severidad": '"alta"'}
    base.update(campos)
    cuerpo = "\n".join(f"{k} = {v}" for k, v in base.items() if v is not None)
    return f'[proyecto]\nnombre = "P"\n\n[[regla]]\n{cuerpo}\n'


# ─── Archivo y validación ───


def test_lee_reglas_validas():
    rs = parse(VALIDO)
    assert rs.project == "Tienda escolar" and rs.version == "1.2"
    r1, r2 = rs.rules
    assert (r1.id, r1.severity, r1.forbidden, r1.story) == ("RN-001", "alta", r"float\(", "HU-03")
    # Rutas normalizadas y sin repetir
    assert r1.paths == ("app/pagos/",)
    assert r2.paths == () and r2.forbidden is None and r2.required is None


def test_archivo_sin_reglas_es_valido():
    assert parse('[proyecto]\nnombre = "P"\n').rules == []


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("[proyecto\nnombre = 1", "no es TOML válido"),
        ('[[regla]]\nid = "RN-001"\n', "falta la sección [proyecto]"),
        ('[proyecto]\nnombre = "P"\n[reglas]\nignorar = []\n', "tablas [[regla]] (en singular)"),
        ('[proyecto]\nnombre = "P"\n[regla]\nid = "RN-001"\n', "doble corchete"),
        ('[proyecto]\nnombre = "P"\n[extra]\n', "sección desconocida `extra`"),
        (regla(id='"RN-02"'), "línea 4: `RN-02` no cumple el formato `RN-###`"),
        (regla(severidad=None), "línea 4 · RN-001: falta `severidad`"),
        (regla(severidad='"critica"'), "`severidad` debe ser alta, media o baja"),
        (regla(titulo='""'), "`titulo` está vacío"),
        (regla(severida='"alta"'), "campo desconocido `severida`"),
        (regla(prohibido=r"'float\('"), None),
        (regla(prohibido="'(sin cerrar'"), "`prohibido` no es una expresión regular válida"),
        (regla(rutas='"app/"'), "`rutas` debe ser una lista"),
        (regla(rutas='["../fuera/"]'), "no es una ruta válida"),
        (regla(ia='"si"'), "`ia` debe ser true o false"),
        (regla(titulo='"' + "x" * 121 + '"'), "demasiado largo"),
    ],
)
def test_errores_de_validacion(texto, mensaje):
    if mensaje is None:
        parse(texto)
        return
    with pytest.raises(RulesError) as exc:
        parse(texto)
    assert mensaje in str(exc.value)


def test_id_repetido_indica_la_linea():
    texto = regla() + '\n[[regla]]\nid = "RN-001"\ntitulo = "T2"\ndescripcion = "D"\nseveridad = "baja"\n'
    with pytest.raises(RulesError, match="línea 10: RN-001 está repetida"):
        parse(texto)


def test_maximo_de_reglas():
    bloque = '[[regla]]\nid = "RN-{:03d}"\ntitulo = "T"\ndescripcion = "D"\nseveridad = "baja"\n'
    texto = '[proyecto]\nnombre = "P"\n' + "".join(bloque.format(i) for i in range(reglas.MAX_RULES + 1))
    with pytest.raises(RulesError, match="máximo 200 reglas"):
        parse(texto)


# ─── Nivel patrón ───


def repo(tmp_path: Path, archivos: dict[str, str]) -> tuple[Path, list[str]]:
    for rel, contenido in archivos.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(contenido, encoding="utf-8")
    return tmp_path, sorted(archivos)


def correr(root: Path, files: list[str]) -> reglas.RulesCheck:
    return reglas.run(root, files, lambda f: (root / f).read_text(encoding="utf-8").split("\n"))


REGLAS = '''
[proyecto]
nombre = "Tienda"

[[regla]]
id = "RN-001"
titulo = "Montos con Decimal"
descripcion = "Nunca float."
severidad = "alta"
rutas = ["app/pagos/"]
prohibido = 'float\\('

[[regla]]
id = "RN-002"
titulo = "Admin protegido"
descripcion = "Toda ruta de admin lleva @requiere_admin."
severidad = "media"
rutas = ["app/admin/"]
obligatorio = '@requiere_admin'

[[regla]]
id = "RN-003"
titulo = "Sin patrón"
descripcion = "Se verifica con pruebas."
severidad = "baja"

[[regla]]
id = "RN-004"
titulo = "Ruta mal escrita"
descripcion = "rutas no existe."
severidad = "baja"
rutas = ["app/pago/"]
prohibido = 'x'
'''


def test_patrones_prohibido_y_obligatorio(tmp_path):
    root, files = repo(tmp_path, {
        "reglas_negocio.toml": REGLAS,
        "app/pagos/cobro.py": "from decimal import Decimal\n\ndef total(m):\n    return float(m) * 2\n",
        "app/pagos/__init__.py": "",
        "app/admin/usuarios.py": "@requiere_admin\ndef listar():\n    pass\n",
        "app/admin/reportes.py": "def exportar():\n    pass\n",
        "app/admin/__init__.py": "",
        # Las pruebas no cuentan: usar float() ahí para comprobar la regla es normal
        "tests/test_cobro.py": "def test_x():\n    assert float('1') == 1\n",
    })
    check = correr(root, files)
    assert check.source == "reglas_negocio.toml" and check.project == "Tienda" and check.error is None
    r1, r2, r3, r4 = check.results

    assert (r1.status, r1.level, r1.evidence_total) == ("no_cumple", "patron", 1)
    assert r1.evidence[0] == reglas.Evidence(file="app/pagos/cobro.py", line=4, text="return float(m) * 2")

    # __init__.py vacío no necesita el patrón; reportes.py sí y no lo tiene
    assert r2.status == "no_cumple"
    assert [(e.file, e.line) for e in r2.evidence] == [("app/admin/reportes.py", 1)]
    assert "falta `obligatorio` en 1 de 2 archivo(s) con código" in r2.detail

    assert (r3.status, r3.level) == ("sin_verificar", "ninguno")
    assert (r4.status, r4.level) == ("sin_verificar", "patron") and "revisa `rutas`" in r4.detail
    assert reglas.summary_line(check) == "  4 regla(s) · 0 cumplen · 2 no cumplen · 2 sin verificar"


def test_cumple_y_respeta_rutas_excluidas(tmp_path):
    root, files = repo(tmp_path, {
        "docs/reglas_negocio.toml": REGLAS,
        "app/pagos/cobro.py": "from decimal import Decimal\n\ndef total(m):\n    return Decimal(m)\n",
        "app/admin/usuarios.py": "@requiere_admin\ndef listar():\n    pass\n",
    })
    # "Rutas excluidas" del proyecto: el job ya pasa `files` sin ellas
    check = correr(root, [f for f in files if not f.startswith("app/admin/")])
    assert check.source == "docs/reglas_negocio.toml"
    assert check.results[0].status == "cumple"
    assert check.results[1].status == "sin_verificar"


def test_evidencia_se_limita_pero_se_cuenta_completa(tmp_path):
    root, files = repo(tmp_path, {
        "reglas_negocio.toml": REGLAS,
        "app/pagos/cobro.py": "float(1)\n" * 30,
    })
    r1 = correr(root, files).results[0]
    assert r1.evidence_total == 30 and len(r1.evidence) == reglas.MAX_EVIDENCE


def test_sin_archivo_y_archivo_invalido(tmp_path):
    root, files = repo(tmp_path, {"main.py": "print(1)\n"})
    check = correr(root, files)
    assert check.source is None and check.results == []
    assert "sin reglas declaradas" in reglas.summary_line(check)

    (root / "reglas_negocio.toml").write_text(regla(id='"RN-1"'), encoding="utf-8")
    check = correr(root, files)
    assert check.source == "reglas_negocio.toml" and check.results == []
    assert "no cumple el formato" in check.error
    assert reglas.summary_line(check).startswith("  ERROR en reglas_negocio.toml")


def test_archivo_demasiado_grande(tmp_path, monkeypatch):
    monkeypatch.setattr(reglas, "MAX_BYTES", 10)
    root, files = repo(tmp_path, {"reglas_negocio.toml": REGLAS})
    assert "demasiado grande" in correr(root, files).error


def test_reglas_del_repo_de_demostracion():
    root = Path(__file__).resolve().parent.parent / "seed_data" / "demo_repo"
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    check = correr(root, files)
    assert check.error is None
    assert {r.rule.id: r.status for r in check.results} == {"RN-001": "cumple", "RN-002": "no_cumple", "RN-003": "no_cumple", "RN-004": "sin_verificar"}


# ─── En el análisis y en la API ───


class ClonerConReglas(FakeCloner):
    """El repo de prueba de conftest más un reglas_negocio.toml."""

    contenido = REGLAS

    def clone(self, settings: Settings, repo_id: str, url: str, branch: str, token: str | None, attempt: str) -> CloneResult:
        result = super().clone(settings, repo_id, url, branch, token, attempt)
        tmp = clone_mod.clones_root(settings) / f"{repo_id}.tmp-{attempt}"
        (tmp / "app" / "pagos").mkdir(parents=True)
        (tmp / "app" / "pagos" / "cobro.py").write_text("def total(m):\n    return float(m)\n", encoding="utf-8")
        if self.contenido is not None:
            (tmp / "reglas_negocio.toml").write_text(self.contenido, encoding="utf-8")
        return result


@pytest.fixture
def cloner() -> ClonerConReglas:
    return ClonerConReglas()


def test_paso_de_reglas_en_el_analisis_y_api(client):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "done" and job["total"] == len(fake.JOB_STEPS) == 12
    i = job["logs"].index(next(line for line in job["logs"] if "Verificando reglas de negocio" in line))
    assert job["logs"][i].startswith("[10/12]")
    assert job["logs"][i + 1] == "  4 regla(s) · 0 cumplen · 1 no cumplen · 3 sin verificar"

    body = client.get(f"/api/report/{job['report_id']}/reglas").json()
    assert body["checked"] is True and body["source"] == "reglas_negocio.toml" and body["project"] == "Tienda"
    assert body["summary"] == {"total": 4, "cumple": 0, "no_cumple": 1, "sin_verificar": 3}
    r1 = body["rules"][0]
    assert r1["id"] == "RN-001" and r1["status"] == "no_cumple" and r1["paths"] == ["app/pagos/"]
    assert r1["evidence"] == [{"file": "app/pagos/cobro.py", "line": 2, "text": "return float(m)"}]
    # También con "latest"
    assert client.get("/api/report/latest/reglas", params={"repo": job["repo_id"]}).json() == body
    # Las reglas no son hallazgos y no cambian el score
    report = client.get(f"/api/report/{job['report_id']}").json()
    assert all(f["tool"] != "Reglas" for f in report["findings"])


def test_archivo_invalido_no_detiene_el_analisis(client, cloner):
    cloner.contenido = regla(severidad='"urgente"')
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "done"
    assert any(line.startswith("  ERROR en reglas_negocio.toml") for line in job["logs"])
    body = client.get(f"/api/report/{job['report_id']}/reglas").json()
    assert body["checked"] is True and body["rules"] == [] and "severidad" in body["error"]


def test_repo_sin_reglas(client, cloner):
    cloner.contenido = None
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert any("sin reglas declaradas" in line for line in job["logs"])
    body = client.get(f"/api/report/{job['report_id']}/reglas").json()
    assert body["checked"] is True and body["source"] is None and body["summary"]["total"] == 0


def test_reglas_de_otro_equipo_no_se_ven(client, fake):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    # Otra cuenta de GitHub en el mismo cliente
    fake.user = fake.user.__class__(id=99, login="eve", name=None, email=None, avatar_url=None)
    login(client)
    assert client.get(f"/api/report/{job['report_id']}/reglas").status_code == 404


def test_datos_de_demostracion_traen_reglas(client, settings):
    repo_id = seed("ana", settings)
    body = client.get("/api/report/latest/reglas", params={"repo": repo_id}).json()
    assert body["checked"] is True and body["project"] == "API de pagos"
    assert body["summary"] == {"total": 4, "cumple": 1, "no_cumple": 2, "sin_verificar": 1}
    assert body["rules"][1]["evidence"][0]["file"] == "api.py" and body["rules"][1]["story"] == "HU-05"
