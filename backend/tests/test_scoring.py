"""Score: penalización escalada por tamaño y Bandit fuera de las pruebas."""

from app.analyses.analyzers import is_test_path, static_findings
from app.analyses.scoring import business_score, category_scores, global_score


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


def test_neg_pondera_por_severidad_y_solo_cuenta_lo_medible():
    # alta 3, media 2, baja 1: cumple 3+2 de 3+2+1+3 (la que no cumple) = 5 de 9
    medidas = [("cumple", "alta"), ("cumple", "media"), ("no_cumple", "baja"), ("no_implementada", "alta")]
    assert business_score(medidas) == 55.6
    # Prueba rota, sin verificar y fuera del código no suben ni bajan la nota
    ruido = [("prueba_rota", "alta"), ("sin_verificar", "alta"), ("fuera_del_codigo", "media")]
    assert business_score(medidas + ruido) == 55.6


def test_neg_sin_reglas_medibles_no_existe():
    assert business_score([]) is None
    assert business_score([("prueba_rota", "alta"), ("sin_verificar", "baja")]) is None


def test_neg_pesa_cero_por_defecto_y_solo_mueve_el_global_con_peso():
    cats = {"seg": 100.0, "test": 100.0, "prac": 100.0, "neg": 0.0}
    base = {"seg": 50, "test": 30, "prac": 20, "neg": 0}
    assert global_score(base, cats) == 100.0
    assert global_score({**base, "neg": 20}, cats) == 83.3  # 100 × 100 / 120
    # Una configuración anterior no trae neg
    assert global_score({"seg": 50, "test": 30, "prac": 20}, cats) == 100.0


def test_global_ignora_neg_si_el_analisis_no_tiene_reglas_medibles():
    weights = {"seg": 50, "test": 30, "prac": 20, "neg": 20}
    assert global_score(weights, {"seg": 80.0, "test": 80.0, "prac": 80.0, "neg": None}) == 80.0
