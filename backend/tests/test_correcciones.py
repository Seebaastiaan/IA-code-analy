"""
Recomendaciones concretas y correcciones para todos los hallazgos: Ruff (safe y unsafe), versión de pip-audit
y, para lo demás, la propuesta de la IA validada (app.editor.ai_fix).
"""

from pathlib import Path

import pytest

from app.analyses import analyzers
from app.analyses.analyzers import RUFF_SELECT, fix_content, static_findings
from app.analyses.models import FindingInput
from app.analyses.remedies import BANDIT, bandit_remedy, ruff_remedy
from app.analyses.store import fix_kind_of
from app.assistant.llm import Answer, LlmError
from app.editor.ai_fix import Target, apply_ai_edits, bump_requirement, clean_replacement, fix_version, windows
from app.editor.router import get_fix_llm
from app.errors import ApiError
from app.seed import seed

# ─── Recomendaciones ───


def test_las_recomendaciones_son_concretas(client, settings):
    repo_id = seed("ana", settings)
    findings = client.get("/api/report/latest", params={"repo": repo_id}).json()["findings"]
    for f in findings:
        assert "documentación" not in f["rec"].lower() and "http" not in f["rec"], f
        assert "http" not in f["why"], f
    b105 = next(f for f in findings if f["rule"] == "B105")
    assert "os.environ" in b105["rec"]
    b602 = next(f for f in findings if f["rule"] == "B602")
    assert "shell=True" in b602["rec"] and "lista" in b602["rec"]


def test_todas_las_reglas_de_bandit_comunes_tienen_receta():
    for code in ("B101", "B105", "B201", "B301", "B307", "B311", "B324", "B506", "B602", "B608"):
        why, rec = BANDIT[code]
        assert why and rec and "documentación" not in rec
    # Una regla sin entrada sigue siendo concreta (sin enlaces)
    why, rec = bandit_remedy("B999", "Algo raro")
    assert "Algo raro" in rec and "http" not in rec


def test_ruff_fuera_del_catalogo_usa_el_ejemplo_de_ruff():
    _, rec = ruff_remedy("B006", "Do not use mutable data structures for argument defaults")
    assert "None" in rec
    # SIM113 no está en el catálogo: sale el "Use instead" de la documentación de Ruff
    _, rec = ruff_remedy("SIM113", "Use `enumerate()` for index variable")
    assert rec.startswith("Escríbelo así:") and "enumerate" in rec


# ─── Reglas de Ruff ───


def test_ruff_usa_solo_las_reglas_documentadas(tmp_path):
    code = "import os,sys\nfrom typing import List\n\n\ndef f(x: List[int] = []):\n    return x\n"
    found = static_findings(code, "m.py", tmp_path)
    prefixes = tuple(RUFF_SELECT.split(","))
    assert found and all(f.rule.startswith(prefixes) for f in found if f.tool == "Ruff")
    # Ruff 0.17 activaba por defecto reglas de estilo como I001 o UP006
    assert not {"I001", "UP006", "UP035"} & {f.rule for f in found}


def test_las_correcciones_unsafe_de_ruff_tambien_se_ofrecen(tmp_path):
    code = "def f(x=[]):\n    if x == None:\n        return dict()\n    y = 1\n    return x\n"
    found = {f.rule: f for f in static_findings(code, "m.py", tmp_path)}
    assert {"B006", "E711", "C408", "F841"} <= set(found)
    assert all(found[r].fix_kind == "auto" for r in ("B006", "E711", "C408", "F841"))
    fixed = fix_content(code, "m.py", tmp_path, [("E711", "    if x == None:", 2), ("C408", "        return dict()", 3)])
    assert "if x is None:" in fixed and "return {}" in fixed


def test_cada_hallazgo_sabe_como_se_corrige():
    base = {"sev": "alta", "cat": "seg", "file": "app.py", "line": 1, "msg": "m", "why": "w", "rec": "r"}
    assert fix_kind_of(FindingInput(tool="Ruff", rule="F401", fix=True, **base)) == "auto"
    assert fix_kind_of(FindingInput(tool="Bandit", rule="B602", fix=True, fix_kind="ia", **base)) == "ia"
    assert fix_kind_of(FindingInput(tool="pytest", rule="FAIL", **{**base, "file": "tests/test_a.py"})) == "ia"
    # Simulada (sin sandbox): no hay nada real que corregir
    assert fix_kind_of(FindingInput(tool="pytest", rule="FAIL", **{**base, "file": "tests/test_a.py", "rec": "Este resultado es simulado"})) is None
    assert fix_kind_of(FindingInput(tool="coverage", rule="COV", **base)) is None


# ─── pip-audit ───


@pytest.mark.parametrize(("linea", "esperada"), [
    ("requests==2.25.1", "requests==2.32.4"),
    ("requests>=2.0  # http", "requests>=2.32.4 # http"),
    ("requests[socks]", "requests[socks]>=2.32.4"),
    ("requests==2.25.1 ; python_version >= '3.8'", "requests==2.32.4 ; python_version >= '3.8'"),
])
def test_sube_la_version_del_paquete(linea, esperada):
    assert bump_requirement(f"flask==2.0\n{linea}\n", 2, "2.32.4").split("\n")[1] == esperada


def test_version_corregida_desde_la_recomendacion():
    assert fix_version("Actualizar a requests 2.32.4 o superior y volver a correr las pruebas.") == "2.32.4"
    assert fix_version("No hay versión corregida publicada") is None


# ─── Corrección con IA: validación ───

CODIGO = """import subprocess


def respaldo(destino):
    subprocess.call("cp pagos.db " + destino, shell=True)
    return {"ok": True}


def otra():
    return 1
"""


def target(line: int = 5) -> list[Target]:
    return [Target(1, "Bandit", "B602", line, "shell=True", "Quita shell=True")]


def test_la_ventana_es_la_funcion_del_hallazgo():
    lines = CODIGO.split("\n")
    assert windows("api.py", lines, target()) == [(4, 6)]
    # Un archivo que no es Python va completo si es corto
    assert windows("requirements.txt", ["a==1", "b==2"], target(2)) == [(1, 2)]


def test_aplica_ediciones_dentro_de_la_ventana_y_agrega_imports():
    lines = CODIGO.split("\n")
    data = {"edits": [{"start_line": 5, "end_line": 5, "replacement": '    subprocess.call(["cp", "pagos.db", destino])'}], "imports": ["import shlex", "import subprocess"]}
    out = apply_ai_edits("api.py", lines, data, [(4, 6)])
    assert out[:2] == ["import subprocess", "import shlex"]
    assert '    subprocess.call(["cp", "pagos.db", destino])' in out and "def otra():" in out


@pytest.mark.parametrize("edits", [
    [{"start_line": 9, "end_line": 10, "replacement": "x"}],  # fuera de la ventana
    [{"start_line": 4, "end_line": 5, "replacement": "a"}, {"start_line": 5, "end_line": 6, "replacement": "b"}],  # se solapan
    [{"start_line": "x", "end_line": 5, "replacement": ""}],
])
def test_rechaza_ediciones_invalidas(edits):
    with pytest.raises(ApiError) as exc:
        apply_ai_edits("api.py", CODIGO.split("\n"), {"edits": edits}, [(4, 6)])
    assert exc.value.status == 422


# ─── Corrección con IA: endpoint ───


class FakeLLM:
    """Responde lo que la prueba le diga y guarda lo que recibió."""

    def __init__(self):
        self.reply: dict | Exception = {"edits": [], "explanation": ""}
        # Respuestas en orden para los reintentos; al acabarse se usa `reply`
        self.replies: list[dict] = []
        self.prompts: list[str] = []

    def answer(self, system, turns, schema, on_delta=None):
        self.prompts.append(turns[-1].text)
        if self.replies:
            return Answer(self.replies.pop(0), "Fake")
        if isinstance(self.reply, Exception):
            raise self.reply
        return Answer(self.reply, "Fake")


@pytest.fixture
def fake_llm(client) -> FakeLLM:
    llm = FakeLLM()
    client.app.dependency_overrides[get_fix_llm] = lambda: llm
    return llm


@pytest.fixture
def demo(client, settings) -> str:
    return seed("ana", settings)


def finding(client, repo_id, rule) -> dict:
    return next(f for f in client.get("/api/report/latest", params={"repo": repo_id}).json()["findings"] if f["rule"] == rule)


def fix(client, repo_id, *ids):
    return client.post("/api/fix", json={"repo_id": repo_id, "finding_ids": list(ids)})


def test_corrige_bandit_con_ia(client, demo, fake_llm):
    f = finding(client, demo, "B602")
    assert f["fix"] is True and f["fix_kind"] == "ia"
    fake_llm.reply = {
        "edits": [{"start_line": 25, "end_line": 25, "replacement": '    subprocess.call(["cp", "pagos.db", destino])'}],
        "explanation": "Pasé el comando como lista y quité shell=True.",
    }
    res = fix(client, demo, f["id"])
    assert res.status_code == 200, res.json()
    body = res.json()
    (patch,) = body["patches"]
    # El clon puede tener CRLF (git en Windows): la línea nueva conserva el mismo final que la original
    eol = "\r" if patch["original"].endswith("\r") else ""
    assert patch == {"file": "api.py", "line": 25, "original": '    subprocess.call("cp pagos.db " + destino, shell=True)' + eol, "text": '    subprocess.call(["cp", "pagos.db", destino])' + eol}
    assert body["notes"] == ["api.py: Pasé el comando como lista y quité shell=True."]
    # El modelo recibe el hallazgo, su recomendación y la función numerada
    prompt = fake_llm.prompts[-1]
    assert "Bandit B602 en api.py:25" in prompt and "Recomendación:" in prompt and "   25|" in prompt


def test_mezcla_ruff_e_ia_en_el_mismo_archivo(client, demo, fake_llm):
    ruff = next(f for f in client.get("/api/report/latest", params={"repo": demo}).json()["findings"] if f["fix_kind"] == "auto" and f["file"] == "api.py")
    bandit = finding(client, demo, "B602")
    fake_llm.reply = {"edits": [], "explanation": ""}
    # La IA no cambió nada, pero la corrección de Ruff sí aplica: se entrega esa
    res = fix(client, demo, ruff["id"], bandit["id"])
    assert res.status_code == 200, res.json()
    assert res.json()["patches"] and res.json()["notes"] == ["api.py: la IA no propuso cambios para los demás hallazgos"]


def test_la_ia_no_puede_romper_el_archivo(client, demo, fake_llm):
    f = finding(client, demo, "B602")
    fake_llm.reply = {"edits": [{"start_line": 25, "end_line": 25, "replacement": "    subprocess.call(["}], "explanation": ""}
    res = fix(client, demo, f["id"])
    assert res.status_code == 422 and "no compila" in res.json()["error"]["message"]
    fake_llm.reply = {"edits": [{"start_line": 1, "end_line": 1, "replacement": "import os"}], "explanation": ""}
    res = fix(client, demo, f["id"])
    assert res.status_code == 422 and "fuera del código del hallazgo" in res.json()["error"]["message"]


def test_errores_del_modelo(client, demo, fake_llm):
    f = finding(client, demo, "B602")
    fake_llm.reply = LlmError("Gemini respondió 429", kind="quota")
    res = fix(client, demo, f["id"])
    assert res.status_code == 503 and res.json()["error"]["code"] == "llm_rate_limited"
    fake_llm.reply = {"edits": [], "explanation": "Nada que cambiar"}
    assert fix(client, demo, f["id"]).status_code == 409


def test_si_la_propuesta_no_compila_la_ia_reintenta_con_el_error(client, demo, fake_llm):
    f = finding(client, demo, "B602")
    fake_llm.replies = [
        {"edits": [{"start_line": 25, "end_line": 25, "replacement": "    subprocess.call(["}], "explanation": ""},
        {"edits": [{"start_line": 25, "end_line": 25, "replacement": '    subprocess.call(["cp", "pagos.db", destino])'}], "explanation": "Lista."},
    ]
    res = fix(client, demo, f["id"])
    assert res.status_code == 200, res.json()
    assert len(fake_llm.prompts) == 2 and "no compila" in fake_llm.prompts[-1]


@pytest.mark.parametrize(("text", "original", "esperado"), [
    # Copió el prefijo de los fragmentos numerados
    ("   25|     x = 1\n   26|     y = 2", "    x = 0", "    x = 1\n    y = 2"),
    # Devolvió el bloque sin la indentación de la línea que reemplaza
    ("try:\n    x = 1\nexcept ValueError:\n    pass", "        x = 0", "        try:\n            x = 1\n        except ValueError:\n            pass"),
    # Ya venía bien: no se toca
    ("    x = 1", "    x = 0", "    x = 1"),
])
def test_limpia_la_respuesta_del_modelo(text, original, esperado):
    assert clean_replacement(text, original) == esperado


def test_la_ia_no_puede_usar_nombres_sin_definir(client, demo, fake_llm):
    f = finding(client, demo, "B602")
    fake_llm.reply = {"edits": [{"start_line": 25, "end_line": 25, "replacement": "    logger.warning(destino)"}], "explanation": ""}
    res = fix(client, demo, f["id"])
    assert res.status_code == 422 and "`logger`" in res.json()["error"]["message"]


def test_ruff_ignora_fix_true_del_repo(tmp_path):
    # Con `fix = true`, Ruff sobre stdin imprimía el código corregido en vez del JSON
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nfix = true\n", encoding="utf-8")
    code = "import os\n"
    (tmp_path / "m.py").write_text(code, encoding="utf-8")
    assert [f.rule for f in static_findings(code, "m.py", tmp_path)] == ["F401"]
    analyzers.static_findings_dir(tmp_path, ["m.py"], bandit_on=False)
    # Sobre la carpeta tampoco reescribe los archivos del clon
    assert (tmp_path / "m.py").read_text(encoding="utf-8") == code


def test_fix_de_un_hallazgo_ya_corregido_lo_resuelve(client, demo, settings, fake_llm):
    from app.analyses.workspace import Workspace

    f = finding(client, demo, "B602")
    ws = Workspace(settings, demo)
    # Corregido en disco sin re-analizar (como un guardado cuyo análisis falló)
    content = ws.read("api.py").replace('subprocess.call("cp pagos.db " + destino, shell=True)', 'subprocess.call(["cp", "pagos.db", destino])')
    ws.write("api.py", content)
    res = fix(client, demo, f["id"])
    assert res.status_code == 409 and res.json()["error"]["code"] == "already_fixed"
    assert fake_llm.prompts == []  # no se gastó una llamada a la IA
    assert all(x["rule"] != "B602" or x["status"] != "open" for x in client.get("/api/report/latest", params={"repo": demo}).json()["findings"])


def test_reanalizar_respeta_los_analizadores_del_reporte(demo, settings):
    from app.analyses.workspace import Workspace
    from app.editor.router import analyze_file

    ws = Workspace(settings, demo)
    content = ws.read("api.py")
    tools = lambda analyzers: {f.tool for f in analyze_file(ws, "api.py", content, {"analyzers": analyzers})}  # noqa: E731
    assert tools('["ruff", "bandit"]') == {"Ruff", "Bandit"}
    # Un análisis sin Bandit no gana hallazgos de Bandit al guardar o corregir
    assert tools('["ruff", "pytest"]') == {"Ruff"}
    # Reportes viejos sin la lista: corrieron todos
    assert tools(None) == {"Ruff", "Bandit"}


def test_guardar_no_escribe_si_el_analisis_falla(client, demo, settings, monkeypatch):
    from app.analyses.workspace import Workspace
    from app.editor import router

    def falla(*_):
        raise analyzers.AnalyzerError("Ruff no devolvió un resultado válido")

    monkeypatch.setattr(router, "static_findings", falla)
    before = Workspace(settings, demo).read("api.py")
    res = client.put("/api/file", json={"repo_id": demo, "path": "api.py", "content": before + "\nx = 1\n"})
    assert res.status_code == 502
    assert Workspace(settings, demo).read("api.py") == before


def test_el_asistente_no_manda_a_leer_la_documentacion():
    from app.assistant.router import SYSTEM

    assert "Nunca respondas" in SYSTEM and "documentación" in SYSTEM


def test_el_catalogo_documentado_coincide(tmp_path):
    # docs/ia/catalogo-reglas.md describe estas reglas
    doc = (Path(__file__).resolve().parents[2] / "docs" / "ia" / "catalogo-reglas.md").read_text(encoding="utf-8")
    assert RUFF_SELECT in doc
    assert analyzers.FIX_APPLICABILITY == ("safe", "unsafe")
