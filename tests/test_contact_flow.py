"""
Flujo Pendientes -> Abiertos -> Contactados y prospectos repetidos por número de WhatsApp.
Cada prueba usa una base SQLite temporal (conftest.py).
"""
import io
import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import app as app_module
import contact_identity as ci
import db
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
        "telefono": "",
        "whatsapp": "+52 (954) 123-4567",
        "whatsapp_estado": "WHATSAPP_COMPROBADO",
        "mensaje_personalizado": "Hola, equipo de Posada Mar Azul.",
    }
    base.update(extra)
    return db.save_or_update_negocio(base)


def _lista(client):
    return {p["id"]: p for p in client.get("/api/prospects").get_json()}


def _pendientes_visibles(client):
    return [p for p in client.get("/api/prospects").get_json() if p["bandeja"] == "pendiente" and not p["oculto_en_pendientes"]]


# ---------------------------------------------------------------------------
# 3/4. Normalización: dos formatos del mismo número son el mismo contacto
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,pais,es_wa", [
    ("+52 (954) 123-4567", "", False),
    ("954 123 4567", "MX", False),
    ("954-123-4567", "MX", False),
    ("529541234567", "", True),
    ("5219541234567", "", False),
    ("+52 1 954 123 4567", "", False),
    ("0052 954 123 4567", "", False),
])
def test_formatos_del_mismo_numero_son_iguales(raw, pais, es_wa):
    r = ci.normalizar_telefono(raw, pais, es_whatsapp=es_wa)
    assert r == {"estado": "valido", "e164": "+529541234567", "motivo": ""}


def test_numero_sin_pais_conocido_es_ambiguo_e_invalidos_no_cuentan():
    assert ci.normalizar_telefono("954 123 4567", "")["estado"] == "ambiguo"
    assert ci.normalizar_telefono("954 123 4567", "US")["estado"] == "ambiguo"
    assert ci.normalizar_telefono("1234", "MX")["estado"] == "invalido"
    assert ci.normalizar_telefono("0000000000", "MX")["estado"] == "invalido"
    assert ci.normalizar_telefono("954-FLORES", "MX")["estado"] == "invalido"


def test_pais_del_prospecto_por_ubicacion():
    assert ci.pais_del_prospecto({"municipio": "Puerto Escondido"}) == "MX"
    assert ci.pais_del_prospecto({"municipio": "Oaxaca de Juárez"}) == "MX"
    assert ci.pais_del_prospecto({"municipio": ""}) == ""
    assert ci.pais_del_prospecto({"municipio": "Santa Fe, Nuevo México"}) == ""
    assert ci.pais_del_prospecto({"pais": "México", "municipio": ""}) == "MX"


# ---------------------------------------------------------------------------
# 1/2. Abrir en WhatsApp registra el intento y mueve a Abiertos, sin confirmar envío
# ---------------------------------------------------------------------------
def test_abrir_whatsapp_mueve_a_abiertos_sin_marcar_contactado(client):
    n = _negocio()
    res = client.post("/api/prospects/whatsapp-open", json={"id": n["id"], "mensaje": "Borrador editado"})
    assert res.status_code == 200
    p = res.get_json()["prospecto"]
    assert p["bandeja"] == "abierto"
    assert p["estado_comercial"] == "investigado"
    assert p["fecha_contacto_confirmada"] is None
    assert p["intentos_whatsapp"] == 1
    assert p["intentos_contacto"][0]["telefono_e164"] == "+529541234567"
    # La ficha y el borrador se conservan
    d = db.get_negocio_detail(n["id"])
    assert d["mensaje_personalizado"] == "Hola, equipo de Posada Mar Azul."
    with db.get_db() as conn:
        assert conn.execute("SELECT mensaje FROM intentos_contacto").fetchone()["mensaje"] == "Borrador editado"

    # Volver a abrir desde Abiertos: otro intento, sigue en Abiertos y sin contacto
    p2 = client.post("/api/prospects/whatsapp-open", json={"id": n["id"]}).get_json()["prospecto"]
    assert p2["bandeja"] == "abierto" and p2["intentos_whatsapp"] == 2
    assert p2["estado_comercial"] == "investigado"


def test_bloqueado_no_registra_apertura(client):
    n = _negocio(servicio_sugerido="no_contactar")
    res = client.post("/api/prospects/whatsapp-open", json={"id": n["id"]})
    assert res.status_code == 400
    assert _lista(client)[n["id"]]["bandeja"] == "pendiente"


def test_regresar_a_pendientes_conserva_historial_y_aparece_una_vez(client):
    n = _negocio()
    legado = _negocio(nombre="Mar Azul (registro viejo)", web="https://otra.example", whatsapp="954 123 4567")
    client.post("/api/prospects/whatsapp-open", json={"id": n["id"]})
    assert [p["id"] for p in _pendientes_visibles(client)] == []  # el legado queda oculto

    res = client.post("/api/prospects/return-pending", json={"id": n["id"]})
    assert res.status_code == 200
    p = res.get_json()["prospecto"]
    assert p["bandeja"] == "pendiente" and p["intentos_whatsapp"] == 1
    acciones = [i["accion"] for i in p["intentos_contacto"]]
    assert acciones == ["whatsapp_abierto", "regresado_a_pendientes"]

    visibles = _pendientes_visibles(client)
    assert [x["id"] for x in visibles] == [n["id"]]  # una sola vez, el que regresaste
    lista = _lista(client)
    assert lista[legado["id"]]["oculto_en_pendientes"] is True
    assert lista[legado["id"]]["duplicado_de"] == n["id"]


def test_confirmar_usa_flujo_existente_y_no_regresa_a_pendientes(client):
    n = _negocio()
    client.post("/api/prospects/whatsapp-open", json={"id": n["id"]})
    res = client.post("/api/prospects/contact-confirm", json={"id": n["id"], "canal": "whatsapp", "notas": "Enviado"})
    assert res.status_code == 200
    assert _lista(client)[n["id"]]["bandeja"] == "contactado"
    # Un contactado no puede volver a Pendientes
    assert client.post("/api/prospects/return-pending", json={"id": n["id"]}).status_code == 400
    # «Recargar»: el estado está en SQLite, no en memoria
    assert db.get_negocio_detail(n["id"])["estado_comercial"] == "contactado"
    assert _lista(client)[n["id"]]["bandeja"] == "contactado"


# ---------------------------------------------------------------------------
# 3/4. Números en Abiertos/Contactados no reaparecen en las próximas listas
# ---------------------------------------------------------------------------
def _buscar_con(monkeypatch, client, resultados):
    monkeypatch.setattr(app_module, "DDGS_AVAILABLE", True)
    monkeypatch.setattr(app_module, "search_ddg", lambda q, limit, depth: ([dict(r) for r in resultados], len(resultados)))

    def canales(url, max_subpages=2):
        r = next(x for x in resultados if x["web"] == url)
        return {
            "whatsapp": r["_wa"], "whatsapp_estado": "WHATSAPP_COMPROBADO", "fuente_whatsapp": "enlace_wa_me",
            "tipo_canal_principal": "whatsapp", "url_origen": url, "telefono": r.get("_tel", ""), "email": "",
            "redes_sociales": "",
        }
    monkeypatch.setattr(app_module, "discover_contact_channels_level1", canales)
    return client.post("/api/search", json={"category": "hotel", "location": "Puerto Escondido, Oaxaca", "limit": 5})


def test_busqueda_no_repite_numero_contactado_con_otro_formato(client, monkeypatch):
    n = _negocio()
    client.post("/api/prospects/whatsapp-open", json={"id": n["id"]})
    client.post("/api/prospects/contact-confirm", json={"id": n["id"], "canal": "whatsapp", "notas": ""})

    res = _buscar_con(monkeypatch, client, [
        {"nombre": "Posada Mar Azul (Facebook)", "web": "https://facebook-mirror.example/marazul", "_wa": "5219541234567"},
        {"nombre": "Hotel Nuevo", "web": "https://hotelnuevo.example", "_wa": "529547654321"},
        {"nombre": "Hotel Nuevo (otra página)", "web": "https://hotelnuevo-mirror.example", "_wa": "+52 954 765 4321"},
    ]).get_json()
    nombres = [p["nombre"] for p in res["prospects"]]
    assert nombres == ["Hotel Nuevo"]
    assert res["debug_info"]["excluidos_mismo_numero"] == 2
    assert n["id"] not in [p["id"] for p in _pendientes_visibles(client)]


def test_busqueda_no_repite_numero_abierto(client, monkeypatch):
    n = _negocio()
    client.post("/api/prospects/whatsapp-open", json={"id": n["id"]})
    res = _buscar_con(monkeypatch, client, [
        {"nombre": "Mar Azul", "web": "https://marazul-directorio.example", "_wa": "529541234567"},
    ]).get_json()
    assert res["prospects"] == []


def test_registros_viejos_repetidos_no_reaparecen_en_pendientes(client):
    contactado = _negocio()
    client.post("/api/prospects/contact-confirm", json={"id": contactado["id"], "canal": "whatsapp", "notas": ""})
    viejo = _negocio(nombre="Registro viejo", web="https://viejo.example", whatsapp="", telefono="954.123.4567")
    lista = _lista(client)
    assert lista[viejo["id"]]["oculto_en_pendientes"] is True
    assert lista[viejo["id"]]["duplicado_de"] == contactado["id"]
    assert db.get_negocio_detail(viejo["id"]) is not None  # no se borró ni se fusionó


def test_numeros_ambiguos_no_se_fusionan(client):
    a = _negocio(nombre="Sin ubicación A", municipio="", web="https://a.example", whatsapp="", telefono="954 123 4567")
    b = _negocio(nombre="Sin ubicación B", municipio="", web="https://b.example", whatsapp="", telefono="954-123-4567")
    lista = _lista(client)
    for x in (a, b):
        assert lista[x["id"]]["telefono_estado"] == "ambiguo"
        assert lista[x["id"]]["oculto_en_pendientes"] is False
        assert lista[x["id"]]["claves_contacto"] == []


# ---------------------------------------------------------------------------
# Celular -> PC: los intentos y regresos llegan por el archivo de avances
# ---------------------------------------------------------------------------
def _avances(eventos):
    return {"formato": "sabueso-movil-avances", "version": 1, "generado_en": "2026-11-25T10:00:00", "eventos": eventos}


def _post_avances(client, payload):
    data = {"file": (io.BytesIO(json.dumps(payload).encode("utf-8")), "avances.json")}
    return client.post("/api/movil/import", data=data, content_type="multipart/form-data").get_json()["resumen"]


def test_eventos_del_celular_abrir_y_regresar(client):
    n = _negocio()
    r = _post_avances(client, _avances([
        {"id": "evt-wa-000000001", "tipo": "whatsapp_abierto", "uid": f"pc-{n['id']}", "fecha": "2026-11-25T09:00:00",
         "datos": {"telefono_e164": "+529541234567", "mensaje": "Hola", "plantilla": "mensaje_personalizado"}},
    ]))
    assert r["aplicados"] == 1, r
    d = _lista(client)[n["id"]]
    assert d["bandeja"] == "abierto" and d["estado_comercial"] == "investigado" and d["intentos_whatsapp"] == 1

    paquete = json.loads(client.get("/api/movil/export").data)
    exp = next(p for p in paquete["prospectos"] if p["id"] == n["id"])
    assert exp["bandeja_contacto"] == "abierto" and exp["intentos_whatsapp"] == 1

    r2 = _post_avances(client, _avances([
        {"id": "evt-wa-000000002", "tipo": "regresar_pendientes", "uid": f"pc-{n['id']}", "fecha": "2026-11-25T09:05:00", "datos": {}},
    ]))
    assert r2["aplicados"] == 1
    assert _lista(client)[n["id"]]["bandeja"] == "pendiente"
