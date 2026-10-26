"""Asistente IA con un modelo falso: sin red ni cuota de Gemini."""

import hashlib
import re

import httpx
import numpy as np
import pytest

from app.assistant import index
from app.assistant import llm as llm_mod
from app.assistant import router as assistant_router
from app.assistant.chunker import chunk_file
from app.assistant.llm import EMBED_DIM, LLM, Answer, LlmError
from app.config import get_settings
from app.seed import seed


def fake_vector(text: str) -> np.ndarray:
    """Bolsa de palabras con hash: textos con palabras en común quedan cerca."""
    v = np.zeros(EMBED_DIM, dtype=np.float32)
    for word in re.findall(r"[a-záéíóúñ_]{3,}", text.lower()):
        v[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBED_DIM] += 1
    n = np.linalg.norm(v)
    return v / n if n else v


class FakeLLM:
    def __init__(self) -> None:
        self.embedded: list[str] = []
        self.calls: list[dict] = []
        self.reply: dict = {"answer": "Respuesta de prueba", "sources": [], "finding_id": None}
        self.fail: LlmError | None = None

    def embed(self, texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
        if task == "RETRIEVAL_DOCUMENT":
            self.embedded += texts
        return np.stack([fake_vector(t) for t in texts]) if texts else np.zeros((0, EMBED_DIM), dtype=np.float32)

    def answer(self, system: str, turns: list, schema: dict, on_delta=None) -> Answer:
        self.calls.append({"system": system, "turns": turns})
        if self.fail:
            raise self.fail
        if on_delta:
            # Como el streaming real: la respuesta llega en trozos
            text = self.reply["answer"]
            for i in range(0, len(text), 5):
                on_delta(text[i : i + 5])
        return Answer(self.reply, "Gemini 3.8 Flash")


@pytest.fixture
def llm(client) -> FakeLLM:
    fake = FakeLLM()
    client.app.dependency_overrides[assistant_router.get_llm] = lambda: fake
    return fake


@pytest.fixture
def repo_id(client, settings) -> str:
    return seed("ana", settings)


def ask(client, repo_id: str, message: str, history: list | None = None):
    return client.post("/api/chat", json={"repo_id": repo_id, "message": message, "history": history or []})


def context_of(llm: FakeLLM) -> str:
    return llm.calls[-1]["turns"][-1].text


# ─── Fragmentos ───


def test_fragmentos_por_funcion():
    source = "import os\n\nX = 1\n\n\n@decorador\ndef f(a):\n    return a\n\n\nclass C:\n    def m(self):\n        pass\n"
    chunks = chunk_file("m.py", source)
    assert [(c.start, c.end) for c in chunks] == [(1, 3), (6, 8), (11, 13)]
    assert chunks[1].text.startswith("@decorador")


def test_fragmentos_con_error_de_sintaxis_usan_ventanas():
    chunks = chunk_file("roto.py", "def (:\n" + "x = 1\n" * 130)
    assert chunks[0].start == 1 and chunks[0].end == 60 and chunks[1].start == 51


def test_mover_un_fragmento_no_cambia_su_hash():
    a = chunk_file("m.py", "def f():\n    return 1\n")[0]
    b = chunk_file("m.py", "\n\n\ndef f():\n    return 1\n")[0]
    assert a.hash == b.hash and (a.start, b.start) == (1, 4)


# ─── Índice ───


def test_indice_incremental(client, settings, repo_id, llm):
    from app.db import connect

    conn = connect(settings.database_path)
    first = index.refresh(settings, conn, llm, repo_id)
    assert first.chunks == first.embedded > 0 and first.readme and first.py_files == 6
    # Sin cambios: no se vuelve a pedir ningún embedding
    assert index.refresh(settings, conn, llm, repo_id).embedded == 0
    # Guardar un archivo desde el editor solo re-embebe lo que cambió
    content = client.get("/api/file", params={"repo": repo_id, "path": "auth.py"}).json()["content"]
    client.put("/api/file", json={"repo_id": repo_id, "path": "auth.py", "content": content + "\n\ndef nueva():\n    return 42\n"})
    again = index.refresh(settings, conn, llm, repo_id)
    assert 0 < again.embedded <= 2 and again.chunks == first.chunks + 1


def test_busqueda_encuentra_el_codigo_relevante(settings, repo_id, llm):
    from app.db import connect

    conn = connect(settings.database_path)
    index.refresh(settings, conn, llm, repo_id)
    hits = index.search(conn, repo_id, fake_vector("monto limite autorizado rechazados"), k=1)
    assert hits[0].file == "pagos/procesador.py"


def test_info_del_indice(client, repo_id, llm, settings):
    res = client.get(f"/api/repos/{repo_id}/index").json()
    # Sin GEMINI_API_KEY en la configuración de prueba
    assert res["status"] == "not_configured" and res["report_num"] == 4 and res["model"] == "Gemini 3.8 Flash"


# ─── Chat ───


def test_contexto_y_fuentes_validas(client, repo_id, llm):
    llm.reply = {"answer": "El límite se revisa en `procesar`.", "sources": [{"file": "pagos/procesador.py", "line": 20}, {"file": "inventado.py", "line": 3}, {"file": "pagos/procesador.py", "line": 9999}], "finding_id": None}
    body = ask(client, repo_id, "¿Dónde se valida el límite de los monto autorizado?").json()
    assert body["content"] == "El límite se revisa en `procesar`."
    # Las fuentes fuera del contexto se descartan
    assert body["sources"] == [{"file": "pagos/procesador.py", "line": 20}]
    assert body["model"] == "Gemini 3.8 Flash" and body["action"] is None
    ctx = context_of(llm)
    assert "REPORTE #4" in ctx and "FRAGMENTO pagos/procesador.py" in ctx and "PREGUNTA:" in ctx
    assert "B101" not in ctx  # las reglas ignoradas no llegan al modelo


def test_hallazgo_mencionado_lleva_su_codigo(client, repo_id, llm):
    ask(client, repo_id, "Explícame el hallazgo B602 en api.py:25")
    ctx = context_of(llm)
    assert "HALLAZGO MENCIONADO" in ctx and "B602" in ctx and "shell=True" in ctx and "  25| " in ctx


def test_accion_solo_para_hallazgos_con_correccion(client, repo_id, llm):
    report = client.get("/api/report/latest", params={"repo": repo_id}).json()
    fixable = next(f for f in report["findings"] if f["fix"])
    manual = next(f for f in report["findings"] if not f["fix"])
    llm.reply = {"answer": "Aplica la corrección.", "sources": [], "finding_id": fixable["id"]}
    assert ask(client, repo_id, "¿Cómo lo arreglo?").json()["action"] == {"finding_id": fixable["id"], "label": "Aplicar corrección automática"}
    llm.reply = {"answer": "Corrígelo a mano.", "sources": [], "finding_id": manual["id"]}
    assert ask(client, repo_id, "¿Y este?").json()["action"] is None


def test_historial_llega_al_modelo(client, repo_id, llm):
    history = [{"role": "user", "content": "¿Qué hace procesar?"}, {"role": "model", "content": "Procesa pagos."}]
    ask(client, repo_id, "¿Y cómo lo pruebo?", history)
    turns = llm.calls[-1]["turns"]
    assert [(t.role, t.text) for t in turns[:2]] == [("user", "¿Qué hace procesar?"), ("model", "Procesa pagos.")]
    assert turns[-1].role == "user"


@pytest.mark.parametrize(("kind", "code"), [("quota", "llm_rate_limited"), ("busy", "llm_busy"), (None, "llm_unavailable")])
def test_errores_del_modelo(client, repo_id, llm, kind, code):
    llm.fail = LlmError("falló", kind=kind)
    res = ask(client, repo_id, "hola")
    assert res.status_code == 503 and res.json()["error"]["code"] == code


def test_respuesta_vacia(client, repo_id, llm):
    llm.reply = {"answer": "   ", "sources": []}
    assert ask(client, repo_id, "hola").json()["error"]["code"] == "llm_empty"


def test_sin_indice_responde_con_el_reporte(client, repo_id, llm, monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda *_a, **_k: (_ for _ in ()).throw(LlmError("sin cuota", kind="quota")))
    assert ask(client, repo_id, "¿Cuál es el score?").status_code == 200
    assert "REPORTE #4" in context_of(llm) and "FRAGMENTO" not in context_of(llm)


def test_sin_clave_no_esta_configurado(client, repo_id):
    res = ask(client, repo_id, "hola")
    assert res.status_code == 503 and res.json()["error"]["code"] == "llm_not_configured"


def test_otro_usuario_no_puede_preguntar(client, anon, fake, repo_id, llm):
    fake.user = fake.user.__class__(id=99, login="eve", name=None, email=None, avatar_url=None)
    from tests.conftest import login

    login(anon)
    assert ask(anon, repo_id, "hola").status_code == 404
    assert anon.get(f"/api/repos/{repo_id}/index").status_code == 404


def test_mensaje_demasiado_largo(client, repo_id, llm):
    assert ask(client, repo_id, "x" * 2001).status_code == 422


# ─── Cliente HTTP ───


def transport(responses: dict[str, list[int]], seen: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        model = request.url.path.rsplit("/", 1)[-1].split(":")[0] if "generativelanguage" in request.url.host else "groq"
        seen.append(model)
        status = responses[model].pop(0) if responses.get(model) else 200
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "x"}})
        if model == "groq":
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"answer": "de groq", "sources": []}'}}]})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"answer": "ok", "sources": []}'}]}}]})

    return httpx.MockTransport(handler)


def make_llm(settings, responses, seen):
    s = settings.model_copy(update={"gemini_api_key": "k", "gemini_model": "m1"})
    return LLM(s, httpx.Client(transport=transport(responses, seen)))


def test_503_reintenta_el_mismo_modelo(settings, monkeypatch):
    monkeypatch.setattr(llm_mod, "BUSY_RETRY_WAIT_S", 0)
    seen: list[str] = []
    result = make_llm(settings, {"m1": [503]}, seen).answer("s", [], {})
    assert seen == ["m1", "m1"] and result.model == "M1"


def test_error_no_recuperable_no_se_reintenta(settings):
    seen: list[str] = []
    with pytest.raises(LlmError):
        make_llm(settings, {"m1": [400]}, seen).answer("s", [], {})
    assert seen == ["m1"]


def test_embeddings_normalizados(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        n = len(request.read().decode().split('"taskType"')) - 1
        return httpx.Response(200, json={"embeddings": [{"values": [3.0, 4.0] + [0.0] * (EMBED_DIM - 2)}] * n})

    s = settings.model_copy(update={"gemini_api_key": "k"})
    m = LLM(s, httpx.Client(transport=httpx.MockTransport(handler))).embed(["a", "b"])
    assert m.shape == (2, EMBED_DIM) and np.allclose(np.linalg.norm(m, axis=1), 1) and np.isclose(m[0, 0], 0.6)


def test_indexacion_en_segundo_plano_sin_duplicados_ni_bucle(client, settings, monkeypatch):
    """Si indexar falla, el estado pasa a "error" (no "building" para siempre) y no se lanzan indexaciones en paralelo."""
    repo_id = seed("ana", settings)
    configured = settings.model_copy(update={"gemini_api_key": "clave"})
    client.app.dependency_overrides[get_settings] = lambda: configured
    calls: list[str] = []

    class Broken:
        def __init__(self, _settings) -> None:
            pass

        def embed(self, texts, task="RETRIEVAL_DOCUMENT"):
            calls.append(task)
            raise LlmError("La clave de Gemini no es válida o no tiene permiso")

    monkeypatch.setattr(index, "LLM", Broken)
    # Simula una indexación ya en curso: la consulta no debe lanzar otra
    assert index.start_background(repo_id)
    assert client.get(f"/api/repos/{repo_id}/index").json()["status"] == "building"
    assert calls == []
    index.refresh_in_background(configured, repo_id)
    assert calls == ["RETRIEVAL_DOCUMENT"]

    res = client.get(f"/api/repos/{repo_id}/index").json()
    assert res["status"] == "error" and "no es válida" in res["error"]
    client.get(f"/api/repos/{repo_id}/index")
    assert calls == ["RETRIEVAL_DOCUMENT"]  # no reintenta antes de RETRY_AFTER_S

    # Pasado el minuto se reintenta y, si funciona, queda listo
    monkeypatch.setattr(index, "RETRY_AFTER_S", 0)
    monkeypatch.setattr(index, "LLM", lambda _s: FakeLLM())
    assert client.get(f"/api/repos/{repo_id}/index").json()["status"] in ("building", "ready")
    assert client.get(f"/api/repos/{repo_id}/index").json()["status"] == "ready"


# ─── Streaming (SSE) ───


def sse_events(text: str) -> list[tuple[str, dict]]:
    import json

    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_chat_stream_entrega_trozos_y_respuesta_final(client, repo_id, llm):
    llm.reply = {"answer": "La clave está en auth.py y se debe leer del entorno.", "sources": [], "finding_id": None}
    res = client.post("/api/chat/stream", json={"repo_id": repo_id, "message": "¿Qué pasa con la clave?"})
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/event-stream")
    events = sse_events(res.text)
    deltas = [d["text"] for e, d in events if e == "delta"]
    assert len(deltas) > 1 and "".join(deltas) == llm.reply["answer"]
    kind, final = events[-1]
    assert kind == "done" and final["content"] == llm.reply["answer"] and final["model"] == "Gemini 3.8 Flash"


def test_chat_stream_error_del_modelo(client, repo_id, llm):
    llm.fail = LlmError("cuota", kind="quota")
    events = sse_events(client.post("/api/chat/stream", json={"repo_id": repo_id, "message": "hola"}).text)
    assert events == [("error", {"code": "llm_rate_limited", "message": "El asistente alcanzó su límite de uso. Intenta de nuevo en un minuto."})]


def test_chat_stream_repo_ajeno_es_404_normal(client, llm):
    res = client.post("/api/chat/stream", json={"repo_id": "r-ajeno", "message": "hola"})
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"


def gemini_sse(*texts: str) -> bytes:
    import json

    return b"".join(f"data: {json.dumps({'candidates': [{'content': {'parts': [{'text': t}]}}]})}\r\n\r\n".encode() for t in texts)


def test_gemini_stream_extrae_el_campo_answer(settings):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=gemini_sse('{"answer": "Ho', 'la\\n\\"mundo\\"','", "sources": [{"file": "a.py", "line": 3}]}'))

    s = settings.model_copy(update={"gemini_api_key": "k", "gemini_model": "m1"})
    deltas: list[str] = []
    result = LLM(s, httpx.Client(transport=httpx.MockTransport(handler))).answer("s", [], {}, on_delta=deltas.append)
    assert seen[0].endswith("/models/m1:streamGenerateContent?alt=sse")
    assert deltas == ["Ho", 'la\n"mundo"']
    assert result.data == {"answer": 'Hola\n"mundo"', "sources": [{"file": "a.py", "line": 3}]}
