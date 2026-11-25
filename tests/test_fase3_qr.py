"""
Fase 3: lectura local de QR (caso 5). La imagen se decodifica en el navegador (jsQR incluido);
aquí se prueba la interpretación del texto, lo que se guarda y su efecto en la recomendación.
"""
import inspect
import io
import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import copilot
import db
import qr_local as Q
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    backups.mkdir()
    monkeypatch.setattr(db, "BACKUPS_DIR", backups)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


RESTAURANTE = {"nombre": "Restaurante La Palapa", "sector": "Restaurante", "municipio": "Mazunte",
               "web": "https://lapalapa.example", "whatsapp": "529581239876", "whatsapp_estado": "WHATSAPP_COMPROBADO"}


@pytest.mark.parametrize("texto,tipo,dominio", [
    ("https://wa.me/5219581234567?text=hola", "whatsapp", "wa.me"),
    ("https://wa.me/c/5219581234567", "menu_digital", "wa.me"),
    ("https://menu.example/la-palapa", "menu_digital", "menu.example"),
    ("https://lapalapa.example/carta", "menu_digital", "lapalapa.example"),
    ("https://www.instagram.com/lapalapa", "redes", "instagram.com"),
    ("https://maps.app.goo.gl/abc", "mapa", "maps.app.goo.gl"),
    ("geo:15.66,-96.55", "mapa", ""),
    ("BEGIN:VCARD\nFN:Ana Pérez\nTEL:9541234567\nEND:VCARD", "contacto", ""),
    ("WIFI:T:WPA;S:Palapa Clientes;P:secreta123;;", "wifi", ""),
    ("https://lapalapa.example/", "enlace", "lapalapa.example"),
    ("Gracias por su visita", "texto", ""),
])
def test_tipos_de_qr(texto, tipo, dominio):
    res = Q.interpretar_qr(texto)
    assert (res["tipo"], res["dominio"]) == (tipo, dominio)


def test_nunca_guarda_contrasenas_ni_datos_personales():
    wifi = Q.interpretar_qr("WIFI:T:WPA;S:Palapa Clientes;P:secreta123;;")
    assert "secreta123" not in json.dumps(wifi, ensure_ascii=False)
    assert wifi["entrada"] == {"tipo": "wifi", "dominio": ""}
    vc = Q.interpretar_qr("BEGIN:VCARD\nFN:Ana Pérez\nTEL:9541234567\nEMAIL:ana@correo.com\nEND:VCARD")
    assert not any(x in json.dumps(vc, ensure_ascii=False) for x in ("Ana", "9541234567", "ana@correo.com"))
    wa = Q.interpretar_qr("https://wa.me/5219581234567?text=Hola%20soy%20Ana")
    assert "5219581234567" not in json.dumps(wa["entrada"]) and "Ana" not in wa["vista"]
    # Lo que llega de fuera se sanea: tipos inventados fuera, dominio solo si el tipo lo admite
    assert Q.sanear_qr({"tipo": "wifi", "dominio": "P:secreta"}) == {"tipo": "wifi", "dominio": ""}
    assert Q.sanear_qr({"tipo": "inventado"}) is None and Q.sanear_qr({"tipo": "texto"}) is None
    assert Q.sanear_qr({"tipo": "enlace", "dominio": "javascript:alert(1)"}) == {"tipo": "enlace", "dominio": ""}


def test_qr_vacio_o_ilegible():
    assert Q.interpretar_qr("") is None and Q.interpretar_qr("   ") is None


def test_caso5_menu_digital_se_interpreta_antes_de_recomendar():
    sin_qr = copilot.generate_cidiks_messages(dict(RESTAURANTE, id=1))
    con_qr = copilot.generate_cidiks_messages(dict(RESTAURANTE, id=1, qr_recibidos=[{"tipo": "menu_digital", "dominio": "menu.example"}]))
    assert sin_qr["servicio_sugerido"] == "catalogos"
    assert con_qr["servicio_sugerido"] != "catalogos"
    assert "ya cuenta con menú digital (QR: menu.example)" in con_qr["observacion_verificada"]
    mem = con_qr["conversacion"]["memoria"]
    assert "catalogos" in mem["excluidos"]


def test_api_interpretar_y_registrar_qr(client):
    n = db.save_or_update_negocio(dict(RESTAURANTE))
    r = client.post("/api/qr/interpretar", json={"texto": "https://menu.example/la-palapa"}).get_json()
    assert r["tipo"] == "menu_digital" and r["guardable"]
    assert client.post("/api/qr/interpretar", json={"texto": " "}).status_code == 400
    d = client.post("/api/qr/registrar", json={"id": n["id"], "entrada": r["entrada"]}).get_json()["prospecto"]
    assert Q.lista_qr(d) == [{"tipo": "menu_digital", "dominio": "menu.example"}]
    assert d["servicio_sugerido"] != "catalogos" and "ya cuenta con menú digital" in d["observacion_verificada"]
    # repetido: no se duplica; texto libre: no se guarda
    client.post("/api/qr/registrar", json={"id": n["id"], "entrada": r["entrada"]})
    assert len(Q.lista_qr(db.get_negocio_detail(n["id"]))) == 1
    assert client.post("/api/qr/registrar", json={"id": n["id"], "entrada": {"tipo": "texto"}}).status_code == 400


def test_qr_desde_el_celular_y_export(client):
    n = db.save_or_update_negocio(dict(RESTAURANTE))
    eventos = [{"id": "evt-qr-000000001", "tipo": "qr_recibido", "uid": f"pc-{n['id']}", "fecha": "2026-11-25T10:00:00",
                "datos": {"tipo": "redes", "dominio": "instagram.com"}},
               {"id": "evt-qr-000000002", "tipo": "qr_recibido", "uid": f"pc-{n['id']}", "fecha": "2026-11-25T10:01:00",
                "datos": {"tipo": "inventado"}}]
    data = {"file": (io.BytesIO(json.dumps({"formato": "sabueso-movil-avances", "version": 1, "eventos": eventos}).encode()), "a.json")}
    res = client.post("/api/movil/import", data=data, content_type="multipart/form-data").get_json()["resumen"]
    assert res["aplicados"] == 1 and len(res["errores"]) == 1
    exp = next(p for p in json.loads(client.get("/api/movil/export").data)["prospectos"] if p["id"] == n["id"])
    assert exp["qr_recibidos"] == [{"tipo": "redes", "dominio": "instagram.com"}]


def test_jsqr_incluido_sin_red_y_motor_sin_ia():
    for ruta in ("docs/vendor/jsQR.js", "static/js/vendor/jsQR.js"):
        js = (BASE_DIR / ruta).read_text(encoding="utf-8")
        assert "XMLHttpRequest" not in js and "fetch(" not in js
    assert "./vendor/jsQR.js" in (BASE_DIR / "docs" / "sw.js").read_text(encoding="utf-8")
    fuente = inspect.getsource(Q)
    for prohibido in ("generativeai", "import requests", "urlopen", "openai", "anthropic", "webbrowser"):
        assert prohibido not in fuente
