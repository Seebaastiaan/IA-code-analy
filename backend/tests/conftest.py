import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.analysis import clone as clone_mod
from app.analysis import router as analysis_router
from app.analysis.clone import CloneError, CloneResult
from app.analysis.jobs import JobManager
from app.config import Settings, get_settings
from app.github import deps
from app.github.client import GithubAuthError, GithubError, GithubUser, TokenGrant
from app.main import create_app

GH_TOKEN = "gho_secreto123"


class FakeGithub:
    """Sustituye a GithubClient: sin red, con respuestas controladas por cada prueba."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.revoked = False
        self.user = GithubUser(id=42, login="ana", name="Ana López", email="ana@correo.dev", avatar_url="https://avatars/ana.png")
        self.repos = [
            {"full_name": "ana/api-pagos", "html_url": "https://github.com/ana/api-pagos", "default_branch": "main", "private": True, "description": "Cobros", "pushed_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z"},
            {"full_name": "ana/dotfiles", "html_url": "https://github.com/ana/dotfiles", "default_branch": "master", "private": False, "description": None, "pushed_at": None, "updated_at": "2026-09-01T00:00:00Z"},
        ]

    def authorize_url(self, state: str) -> str:
        return f"https://github.com/login/oauth/authorize?client_id={self.settings.github_client_id}&state={state}"

    async def exchange_code(self, code: str) -> TokenGrant:
        if code != "buen-code":
            raise GithubError(400, "The code passed is incorrect or expired.")
        return TokenGrant(access_token=GH_TOKEN, scope="repo,read:user,user:email")

    async def get_user(self, token: str) -> GithubUser:
        return self.user

    async def list_repos(self, token: str) -> list[dict]:
        if self.revoked:
            raise GithubAuthError()
        return self.repos

    async def list_branches(self, token: str, full_name: str) -> list[dict]:
        if full_name != "ana/api-pagos":
            raise GithubError(404, "Not Found")
        return [{"name": "main"}, {"name": "develop"}]


class FakeCloner:
    """Sustituye a git: escribe un repo pequeño en la carpeta temporal del intento."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def clone(self, settings: Settings, repo_id: str, url: str, branch: str, token: str | None, attempt: str) -> CloneResult:
        self.calls.append({"url": url, "branch": branch, "token": token})
        if branch == "no-existe":
            raise CloneError("La rama no existe", "fatal: Remote branch no-existe not found in upstream origin", "Revisa la rama.")
        tmp = clone_mod.clones_root(settings) / f"{repo_id}.tmp-{attempt}"
        (tmp / "app" / "core").mkdir(parents=True)
        (tmp / ".git").mkdir()
        (tmp / "main.py").write_text("print('hola')\n", encoding="utf-8")
        (tmp / "app" / "__init__.py").write_text("", encoding="utf-8")
        (tmp / "app" / "core" / "servicio.py").write_text("def suma(a, b):\n    return a + b\n", encoding="utf-8")
        (tmp / "README.md").write_text("# demo\n", encoding="utf-8")
        (tmp / ".git" / "oculto.py").write_text("x = 1\n", encoding="utf-8")
        return CloneResult(py_files=len(clone_mod.python_files(tmp)), seconds=0.1, commit="abc1234")

    promote = staticmethod(clone_mod.promote)


@pytest.fixture
def cloner() -> FakeCloner:
    return FakeCloner()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        secret_key="clave-de-prueba",
        token_encryption_key=Fernet.generate_key().decode(),
        github_client_id="cid",
        github_client_secret="csecret",
        database_path=str(tmp_path / "test.db"),
        clones_path=str(tmp_path / "repos"),
        job_step_seconds=0,
    )


@pytest.fixture
def fake(settings) -> FakeGithub:
    return FakeGithub(settings)


@pytest.fixture
def anon(settings, fake, cloner):
    """Cliente sin sesión. Como context manager, las tareas en segundo plano (jobs) siguen vivas."""
    app = create_app()
    jobs = JobManager(cloner)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[deps.get_client] = lambda: fake
    app.dependency_overrides[analysis_router.get_jobs] = lambda: jobs
    with TestClient(app) as c:
        yield c


def login(client: TestClient) -> dict:
    """Recorre el login con GitHub y deja el token de sesión en el cliente."""
    state = client.post("/api/auth/github/authorize").json()["state"]
    res = client.post("/api/auth/github/callback", json={"code": "buen-code", "state": state})
    assert res.status_code == 200, res.text
    body = res.json()
    client.headers["Authorization"] = f"Bearer {body['token']}"
    return body


@pytest.fixture
def client(anon) -> TestClient:
    login(anon)
    return anon
