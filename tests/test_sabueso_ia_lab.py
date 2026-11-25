import json
from copy import deepcopy

import pytest

from sabueso_ia_lab.core import Laboratorio, Simulador, sugerir_experimento
from sabueso_ia_lab.evaluar import CASOS, evaluar, fixture


def test_manual_y_sin_mutacion():
    caso = CASOS[0]
    p = {"respuesta": caso.respuesta}
    original = deepcopy(p)
    lab = Laboratorio(Simulador(fixture()))
    assert lab.analizar(p)["lectura"] is None
    resultado = lab.analizar(p, activar=True)
    assert resultado["lectura"]["certeza"] == "inferida"
    assert resultado["recursos"] and resultado["borrador"]
    assert resultado["revision"]["bloqueado"] is False
    assert resultado["aprobacion"] == "pendiente"
    assert p == original


@pytest.mark.parametrize("indice,estado", [(3, "cerrado"), (4, "abstencion"),
                                            (5, "cerrado"), (6, "restringido"),
                                            (7, "restringido")])
def test_prevalecen_los_limites(indice, estado):
    caso = CASOS[indice]
    salida = Laboratorio(Simulador(fixture())).analizar(
        {**caso.prospecto, "respuesta": caso.respuesta}, activar=True
    )
    assert salida["estado"] == estado
    assert not salida["borrador"] and not salida["recursos"]


@pytest.mark.parametrize("raw", [
    '{}', '[]', '{"cita":"evidencia válida","cita":"evidencia válida"}', 'a' * 2049,
    json.dumps(dict(categoria="orientacion", servicio="web", certeza="inferida", cita="falsa evidencia")),
    json.dumps(dict(categoria="orientacion", servicio="web", certeza="inferida",
                    cita="evidencia válida", enviar=True)),
])
def test_salida_invalida_retorna_al_motor(raw):
    texto = "Esto contiene evidencia válida."
    lab = Laboratorio(Simulador({texto: raw}))
    base = lab.analizar({"respuesta": texto})
    assert lab.analizar({"respuesta": texto}, activar=True) == {**base, "estado": "fallback"}


def test_minimizacion_y_limites(monkeypatch):
    import sabueso_ia_lab.core as core

    original = "Escríbeme a lab@example.invalid para recibir una guía."
    anonimo = original.replace("lab@example.invalid", "[correo]")
    lab = Laboratorio(Simulador({anonimo: json.dumps(dict(
        categoria="educativa", servicio="catalogos", certeza="inferida", cita="recibir una guía"
    ))}))
    reloj = [10]
    monkeypatch.setattr(core.time, "monotonic", lambda: reloj[0])
    for _ in range(20):
        assert lab.analizar({"respuesta": original}, activar=True)["estado"] == "simulado"
    assert lab.analizar({"respuesta": original}, activar=True)["estado"] == "limite"
    reloj[0] += 60
    for _ in range(10):
        assert lab.analizar({"respuesta": original}, activar=True)["estado"] == "simulado"
    assert lab.analizar({"respuesta": original}, activar=True)["estado"] == "limite"
    with pytest.raises(ValueError):
        lab.analizar({"respuesta": "x" * 601}, activar=True)


def test_evaluacion_y_agregados():
    assert len(evaluar()["casos"]) == 12
    assert sugerir_experimento(15, 2, 1)["experimento"] is None
    assert sugerir_experimento(50, 10, 4)["experimento"]
    with pytest.raises(ValueError):
        sugerir_experimento(10, 11, 0)
