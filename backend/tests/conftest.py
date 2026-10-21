import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.analysis import clone as clone_mod
from app.analysis.clone import CloneError, CloneResult
from app.assistant.llm import Answer, LlmError
from app.config import Settings, get_settings
from app.diagnostico import router as diagnostico_router
from app.main import create_app


class FakeCloner:
    """Sustituye a git: escribe un repo pequeño en la carpeta temporal del intento."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.files = {
            "main.py": "print('hola')\n",
            "app/__init__.py": "",
            "app/core/servicio.py": 'import os\n\nCLAVE = "secreto123"\n\n\ndef suma(a, b):\n    return a + b\n',
            "tests/test_servicio.py": "from app.core.servicio import suma\n\n\ndef test_suma():\n    assert suma(1, 2) == 3\n",
            "README.md": "# demo\n",
        }

    def clone(self, settings: Settings, repo_id: str, url: str, branch: str, token: str | None, attempt: str) -> CloneResult:
        self.calls.append({"url": url, "branch": branch, "token": token})
        if branch == "no-existe":
            raise CloneError("La rama no existe", "fatal: Remote branch no-existe not found in upstream origin", "Revisa la rama.")
        tmp = clone_mod.clones_root(settings) / f"{repo_id}.tmp-{attempt}"
        for rel, text in self.files.items():
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(text, encoding="utf-8")
        return CloneResult(py_files=len(clone_mod.python_files(tmp)), seconds=0.1, commit="abc1234")

    promote = staticmethod(clone_mod.promote)


class FakeLLM:
    """Sustituye a Gemini: sin red ni cuota, con la respuesta que pida cada prueba."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.reply: dict = {
            "resumen": "Hay una clave escrita en el código.",
            "score": 72,
            "hallazgos": [
                {"categoria": "seg", "severidad": "alta", "linea": 3, "regla": "HARDCODED-SECRET", "mensaje": "Clave secreta en el código", "recomendacion": "Léela de una variable de entorno."},
                {"categoria": "prac", "severidad": "baja", "linea": 1, "regla": "UNUSED-IMPORT", "mensaje": "Import sin usar: os", "recomendacion": "Elimina el import."},
            ],
        }
        self.fail: LlmError | None = None

    def answer(self, system: str, turns: list, schema: dict) -> Answer:
        self.calls.append({"system": system, "turns": turns, "schema": schema})
        if self.fail:
            raise self.fail
        return Answer(self.reply, "Gemini 3.8 Flash")


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        secret_key="clave-de-prueba",
        token_encryption_key=Fernet.generate_key().decode(),
        database_path=str(tmp_path / "test.db"),
        clones_path=str(tmp_path / "repos"),
        gemini_api_key="clave-de-prueba",
    )


@pytest.fixture
def cloner() -> FakeCloner:
    return FakeCloner()


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(settings, cloner, llm):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[diagnostico_router.get_cloner] = lambda: cloner
    app.dependency_overrides[diagnostico_router.get_llm] = lambda: llm
    with TestClient(app) as c:
        yield c
