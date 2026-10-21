"""Score: penalización escalada por tamaño y Bandit fuera de las pruebas."""

from app.analyses.analyzers import is_test_path, static_findings
from app.analyses.scoring import category_scores


def test_proyecto_chico_no_escala():
    findings = [("prac", "media")] * 10  # 10 × 3 = 30 puntos
    assert category_scores(findings, 80, 0, code_lines=400)["prac"] == 70
    assert category_scores(findings, 80, 0, code_lines=0)["prac"] == 70  # reportes anteriores


def test_proyecto_grande_escala_por_cada_mil_lineas():
    findings = [("prac", "media")] * 60 + [("seg", "alta")] * 5  # 180 y 60 puntos
    cats = category_scores(findings, 80, 0, code_lines=10_000)
    assert cats["prac"] == 82.0  # 180 / 10
    assert cats["seg"] == 94.0  # 60 / 10


def test_es_prueba():
    assert is_test_path("tests/test_api.py") and is_test_path("pkg/tests/util.py")
    assert is_test_path("test_x.py") and is_test_path("pkg/x_test.py")
    assert not is_test_path("pkg/testing.py") and not is_test_path("contest.py")


CODE = 'import requests\nPASSWORD = "secreto123"\nrequests.get("https://x")\n'


def test_bandit_no_revisa_pruebas():
    assert any(f.tool == "Bandit" for f in static_findings(CODE, "app/cliente.py", None))
    assert not any(f.tool == "Bandit" for f in static_findings(CODE, "tests/test_cliente.py", None))
