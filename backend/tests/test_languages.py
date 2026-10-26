"""Lenguajes del repo: IA voy analiza solo Python (app.analysis.languages)."""

from pathlib import Path

from app.analysis import clone as clone_mod
from app.analysis.clone import CloneResult
from app.analysis.languages import detect, summary
from tests.test_analysis import URL, wait_done


def write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")


def test_detecta_y_ordena_lenguajes(tmp_path):
    write(tmp_path, {
        "app.js": "", "src/a.ts": "", "src/b.tsx": "", "lib/c.js": "", "main.py": "", "index.html": "",
        # Se ignoran: dependencias, entornos y carpetas ocultas
        "node_modules/x/y.js": "", "venv/lib/z.py": "", ".github/s.py": "",
    })
    langs = detect(tmp_path)
    assert [(lang.name, lang.files) for lang in langs] == [("JavaScript", 2), ("TypeScript", 2), ("HTML", 1), ("Python", 1)]
    assert summary(langs) == "JavaScript 2 · TypeScript 2 · HTML 1 · Python 1"


class FilesCloner:
    """Como el FakeCloner de conftest, pero con los archivos que pida la prueba."""

    def __init__(self, files: dict[str, str]):
        self.files = files

    def clone(self, settings, repo_id, url, branch, token, attempt) -> CloneResult:
        tmp = clone_mod.clones_root(settings) / f"{repo_id}.tmp-{attempt}"
        write(tmp, self.files)
        return CloneResult(py_files=sum(f.endswith(".py") for f in self.files), seconds=0.1, commit="abc1234")

    promote = staticmethod(clone_mod.promote)


def use_files(client, files: dict[str, str]) -> None:
    from app.analysis import router as analysis_router

    analysis_router_jobs = client.app.dependency_overrides[analysis_router.get_jobs]()
    analysis_router_jobs.cloner = FilesCloner(files)


def test_repo_sin_python_se_detiene_con_mensaje_claro(client):
    use_files(client, {"index.js": "console.log(1)\n", "src/app.ts": "export {}\n", "index.html": "<p></p>\n"})
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "error"
    assert job["error"]["title"] == "El repositorio no tiene código Python"
    assert "HTML 1 · JavaScript 1 · TypeScript 1" in job["error"]["detail"]
    [repo] = client.get("/api/repos").json()
    assert repo["status"] == "error" and repo["last_report_id"] is None


def test_python_minoritario_avisa_y_el_reporte_lo_dice(client):
    use_files(client, {"main.py": "print(1)\n", **{f"web/{i}.js": "" for i in range(5)}})
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "done"
    logs = "\n".join(job["logs"])
    assert "lenguajes: JavaScript 5 · Python 1" in logs
    assert "aviso: solo 1 de 6 archivos de código son Python; el resto no se analiza" in logs
    report = client.get(f"/api/report/{job['report_id']}").json()
    assert report["languages"] == [{"name": "JavaScript", "files": 5}, {"name": "Python", "files": 1}]


def test_proyecto_python_con_html_no_avisa(client):
    use_files(client, {"app.py": "x = 1\n", "views.py": "y = 2\n", "templates/a.html": "", "templates/b.html": "", "static/s.css": ""})
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "done"
    assert not any("aviso: solo" in line for line in job["logs"])
