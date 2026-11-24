"""
Pruebas de sincronización Sabueso PC <-> Sabueso Móvil (iPhone).
Cada prueba corre en una base SQLite temporal (ver conftest.py) y los respaldos
se redirigen a tmp_path para no tocar data/backups.
"""
import io
import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import db
import movil_sync
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    backups.mkdir()
    monkeypatch.setattr(db, "BACKUPS_DIR", backups)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _negocio(**extra):
    base = {
        "nombre": "Posada Mar Azul",
        "sector": "Hospedaje",
        "municipio": "Puerto Escondido",
        "web": "https://posadamarazul.example",
        "telefono": "9541234567",
        "whatsapp": "529541234567",
        "whatsapp_estado": "WHATSAPP_COMPROBADO",
        "mensaje_personalizado": "Hola, equipo de Posada Mar Azul.",
    }
    base.update(extra)
    return db.save_or_update_negocio(base)


def _avances(eventos):
    return {"formato": "sabueso-movil-avances", "version": 1, "generado_en": "2026-11-24T10:00:00", "eventos": eventos}


def _post(client, payload):
    data = {"file": (io.BytesIO(json.dumps(payload).encode("utf-8")), "avances.json")}
    return client.post("/api/movil/import", data=data, content_type="multipart/form-data")


def test_export_incluye_campos_para_celular(client):
    n = _negocio()
    res = client.get("/api/movil/export")
    assert res.status_code == 200
    assert "attachment" in res.headers["Content-Disposition"]
    paquete = json.loads(res.data.decode("utf-8"))
    assert paquete["formato"] == "sabueso-movil"
    assert paquete["version"] == 1
    p = paquete["prospectos"][0]
    assert p["id"] == n["id"]
    for campo in ("whatsapp", "servicio_sugerido", "identidad_verificada", "mensaje_personalizado",
                  "fecha_seguimiento", "ingreso_cobrado", "movil_uid"):
        assert campo in p


def test_export_excluye_cuarentena(client):
    a = _negocio(nombre="Activo")
    b = _negocio(nombre="En cuarentena", telefono="9547654321", whatsapp="")
    db.quarantine_records([b["id"]], "prueba")
    paquete = json.loads(client.get("/api/movil/export").data)
    ids = {p["id"] for p in paquete["prospectos"]}
    assert a["id"] in ids and b["id"] not in ids


def test_contacto_confirmado_desde_celular_y_acuse(client):
    n = _negocio()
    payload = _avances([{
        "id": "evt-contacto-0001", "tipo": "contacto_confirmado", "uid": f"pc-{n['id']}",
        "fecha": "2026-11-24T09:30:00", "datos": {"canal": "whatsapp", "notas": "Respondió la recepcionista"}
    }])
    res = _post(client, payload)
    assert res.status_code == 200
    resumen = res.get_json()["resumen"]
    assert resumen["aplicados"] == 1 and not resumen["errores"]
    assert Path(resumen["respaldo"]).exists()

    detalle = db.get_negocio_detail(n["id"])
    assert detalle["estado_comercial"] == "contactado"
    assert detalle["canal"] == "whatsapp"
    assert detalle["fecha_contacto_confirmada"] == "2026-11-24T09:30:00"
    assert "Sabueso Móvil" in detalle["notas_actividad"]

    paquete = json.loads(client.get("/api/movil/export").data)
    assert "evt-contacto-0001" in paquete["eventos_aplicados"]


def test_importar_dos_veces_no_duplica(client):
    n = _negocio()
    payload = _avances([
        {"id": "evt-nota-00000001", "tipo": "nota", "uid": f"pc-{n['id']}", "fecha": "2026-11-24T11:00:00",
         "datos": {"texto": "Llamar después de las 5"}},
    ])
    first = _post(client, payload).get_json()["resumen"]
    second = _post(client, payload).get_json()["resumen"]
    assert first["aplicados"] == 1
    assert second["aplicados"] == 0 and second["omitidos_ya_aplicados"] == 1
    assert db.get_negocio_detail(n["id"])["notas"].count("Llamar después de las 5") == 1


def test_no_se_puede_marcar_contactado_por_actualizacion(client):
    n = _negocio()
    payload = _avances([{
        "id": "evt-estado-000001", "tipo": "actualizacion", "uid": f"pc-{n['id']}",
        "fecha": "2026-11-24T11:00:00", "datos": {"estado_comercial": "contactado"}
    }])
    resumen = _post(client, payload).get_json()["resumen"]
    assert resumen["aplicados"] == 0 and len(resumen["errores"]) == 1
    assert db.get_negocio_detail(n["id"])["estado_comercial"] == "investigado"


def test_prospecto_bloqueado_exige_nota(client):
    n = _negocio(servicio_sugerido="no_contactar")
    sin_nota = _avances([{
        "id": "evt-bloq-0000001", "tipo": "contacto_confirmado", "uid": f"pc-{n['id']}",
        "fecha": "2026-11-24T11:00:00", "datos": {"canal": "whatsapp", "notas": ""}
    }])
    resumen = _post(client, sin_nota).get_json()["resumen"]
    assert resumen["aplicados"] == 0 and "nota" in resumen["errores"][0]["motivo"]
    assert db.get_negocio_detail(n["id"])["estado_comercial"] == "investigado"

    # El mismo evento corregido (mismo UUID) puede reintentarse tras un error
    con_nota = _avances([{
        "id": "evt-bloq-0000001", "tipo": "contacto_confirmado", "uid": f"pc-{n['id']}",
        "fecha": "2026-11-24T11:00:00", "datos": {"canal": "llamada", "notas": "El dueño me llamó primero"}
    }])
    resumen2 = _post(client, con_nota).get_json()["resumen"]
    assert resumen2["aplicados"] == 1
    assert db.get_negocio_detail(n["id"])["estado_comercial"] == "contactado"


def test_crm_venta_no_incrementa_ingreso(client):
    n = _negocio()
    payload = _avances([{
        "id": "evt-crm-00000001", "tipo": "actualizacion", "uid": f"pc-{n['id']}",
        "fecha": "2026-11-24T12:00:00",
        "datos": {"estado_comercial": "ganado", "respuesta": "Les interesa", "propuesta_enviada": True,
                  "propuesta_monto": 3500, "venta_acordada": True, "venta_monto": 3000,
                  "fecha_seguimiento": "2026-11-30"}
    }])
    resumen = _post(client, payload).get_json()["resumen"]
    assert resumen["aplicados"] == 1, resumen
    d = db.get_negocio_detail(n["id"])
    assert d["estado_comercial"] == "ganado"
    assert d["venta_monto"] == 3000 and d["ingreso_cobrado"] == 0
    assert d["propuesta_monto"] == 3500 and d["fecha_seguimiento"] == "2026-11-30"


def test_campo_no_permitido_rechazado(client):
    n = _negocio()
    payload = _avances([{
        "id": "evt-mal-00000001", "tipo": "actualizacion", "uid": f"pc-{n['id']}",
        "fecha": "2026-11-24T12:00:00", "datos": {"identidad_verificada": 1}
    }])
    resumen = _post(client, payload).get_json()["resumen"]
    assert resumen["aplicados"] == 0 and "no permitido" in resumen["errores"][0]["motivo"]


def test_prospecto_nuevo_del_celular_y_eventos_encadenados(client):
    uid = "m-1f2e3d4c-aaaa-bbbb-cccc-000000000001"
    payload = _avances([
        {"id": "evt-alta-0000001", "tipo": "nuevo_prospecto", "uid": uid, "fecha": "2026-11-24T13:00:00",
         "datos": {"nombre": "Cabañas Luna Nueva", "sector": "Hospedaje", "municipio": "Mazunte",
                   "whatsapp": "9581112233", "whatsapp_estado": "confirmado", "fuente": "maps",
                   "identidad_verificada": True, "servicio_sugerido": "web",
                   "mensaje_personalizado": "Hola, equipo de Cabañas Luna Nueva."}},
        {"id": "evt-alta-0000002", "tipo": "contacto_confirmado", "uid": uid, "fecha": "2026-11-24T13:05:00",
         "datos": {"canal": "whatsapp", "notas": ""}},
    ])
    resumen = _post(client, payload).get_json()["resumen"]
    assert resumen["aplicados"] == 2, resumen
    nuevo_id = resumen["prospectos_nuevos"][0]["negocio_id"]
    d = db.get_negocio_detail(nuevo_id)
    assert d["movil_uid"] == uid
    assert d["fuente_descubrimiento"] == "movil_maps"
    assert d["estado_comercial"] == "contactado"

    paquete = json.loads(client.get("/api/movil/export").data)
    exportado = next(p for p in paquete["prospectos"] if p["id"] == nuevo_id)
    assert exportado["movil_uid"] == uid


def test_prospecto_nuevo_sin_identidad_queda_bloqueado(client):
    payload = _avances([{
        "id": "evt-alta-sinid-01", "tipo": "nuevo_prospecto", "uid": "m-00000000-0000-0000-0000-000000000009",
        "fecha": "2026-11-24T13:00:00", "datos": {"nombre": "Negocio dudoso", "identidad_verificada": False}
    }])
    resumen = _post(client, payload).get_json()["resumen"]
    d = db.get_negocio_detail(resumen["prospectos_nuevos"][0]["negocio_id"])
    assert d["servicio_sugerido"] == "no_contactar"
    assert d["identidad_verificada"] == 0


def test_duplicado_por_telefono_queda_para_revision(client):
    existente = _negocio()
    payload = _avances([{
        "id": "evt-dup-00000001", "tipo": "nuevo_prospecto", "uid": "m-00000000-0000-0000-0000-00000000dup1",
        "fecha": "2026-11-24T14:00:00",
        "datos": {"nombre": "Mar Azul Posada", "telefono": "954 123 4567", "identidad_verificada": True}
    }])
    resumen = _post(client, payload).get_json()["resumen"]
    assert resumen["posibles_duplicados"][0]["existente_id"] == existente["id"]
    with db.get_db() as conn:
        rows = conn.execute("SELECT estado FROM duplicados_candidatos").fetchall()
    assert [r["estado"] for r in rows] == ["pendiente"]
    # No se fusionó: ambos siguen existiendo
    assert db.get_negocio_detail(existente["id"]) is not None


def test_archivo_invalido_rechazado_sin_respaldo(client, tmp_path):
    res = _post(client, {"formato": "otra-cosa", "version": 1, "eventos": []})
    assert res.status_code == 400
    assert not list((tmp_path / "backups").iterdir())

    bad = {"file": (io.BytesIO(b"esto no es json"), "x.json")}
    res2 = client.post("/api/movil/import", data=bad, content_type="multipart/form-data")
    assert res2.status_code == 400


def test_evento_de_prospecto_en_cuarentena_rechazado(client):
    n = _negocio()
    db.quarantine_records([n["id"]], "prueba")
    payload = _avances([{
        "id": "evt-cuar-0000001", "tipo": "nota", "uid": f"pc-{n['id']}", "fecha": "2026-11-24T15:00:00",
        "datos": {"texto": "hola"}
    }])
    resumen = _post(client, payload).get_json()["resumen"]
    assert resumen["aplicados"] == 0 and "cuarentena" in resumen["errores"][0]["motivo"]
