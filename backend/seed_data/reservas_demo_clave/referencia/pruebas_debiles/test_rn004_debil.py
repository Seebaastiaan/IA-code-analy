"""
Prueba DÉBIL sembrada a propósito (docs/PROPUESTA_REGLAS_VERIFICABLES.md §14, fase 5): pasa, pero no verifica la regla.

Es el tipo de prueba que una IA puede escribir y un equipo aprobar sin leer: reserva con menos de 2 horas de
anticipación y solo revisa que el servidor no falle. Pasa con el código correcto y seguiría pasando si se quitara la
regla. La prueba de fuerza (app.projects.reglas_fuerza) debe marcarla **débil**: ninguno de los cambios a
`citas.py:51-52` (la anticipación mínima) la hace fallar. La prueba buena de RN-004 está en tests/reglas/test_agenda.py.

No está en tests/: no corre con las demás ni cuenta en el veredicto del demo (referencia/ESPERADO.md).
"""

from datetime import datetime

import pytest


@pytest.mark.regla("RN-004")
def test_rn004_reserva_con_poca_anticipacion(como, reservar):
    r = reservar(como("cliente"), datetime(2026, 12, 1, 9, 30))   # ahora: martes 8:00 → 1 h 30 min antes
    assert r.status_code < 500, f"el servidor falló ({r.status_code})"
