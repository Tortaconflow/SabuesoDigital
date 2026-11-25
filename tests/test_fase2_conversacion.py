"""
Fase 2: intenciones, memoria comercial, recursos gratuitos, consentimiento y cierre por rechazo.
Todo corre sobre bases SQLite temporales (conftest.py).
"""
import inspect
import io
import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import conversacion as C
import copilot
import db
import validacion as V
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    backups.mkdir()
    monkeypatch.setattr(db, "BACKUPS_DIR", backups)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


HOTEL = {"id": 1, "nombre": "Posada del Sol", "sector": "Turismo y hospedaje", "municipio": "Puerto Escondido",
         "web": "https://posadadelsol.com", "whatsapp": "529541240793", "whatsapp_estado": "WHATSAPP_COMPROBADO"}


def _negocio(**extra):
    base = {k: v for k, v in HOTEL.items() if k != "id"}
    base.update(extra)
    return db.save_or_update_negocio(base)


# ---------------------------------------------------------------------------
# 1 y 5. Intenciones: educativa, orientación, retroalimentación, contratación…
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("texto,esperada", [
    ("¡Hola! Gracias por comunicarte con Posada Sol. En breve te atenderemos.", "automatica"),
    ("No nos interesa, gracias.", "rechazo"),
    ("Número equivocado, no somos un hotel.", "correccion"),
    ("Me sirvió mucho la guía, gracias", "retroalimentacion"),
    ("Quiero aprender a vender por WhatsApp", "educativa"),
    ("Quiero aprender a hacer mi página, ¿cuánto cuesta el curso?", "educativa"),
    ("¿Por dónde empiezo para tener catálogo?", "orientacion"),
    ("¿Cuánto cobran por una página web?", "contratacion"),
    ("Les comparto nuestro menú", "informativa"),
    ("Me interesa, platiquemos", "humana"),
])
def test_clasificacion_de_intenciones(texto, esperada):
    assert C.clasificar_respuesta(texto)["categoria"] == esperada


def test_solo_contratacion_es_oportunidad_comercial():
    for cid in ("automatica", "rechazo", "correccion", "retroalimentacion", "educativa", "orientacion", "informativa", "humana"):
        assert C.info_categoria(cid)["oportunidad_comercial"] is False, cid
    assert C.info_categoria("contratacion")["oportunidad_comercial"] is True


# ---------------------------------------------------------------------------
# 3. Memoria literal (sin inventar necesidades ni presupuestos)
# ---------------------------------------------------------------------------
def test_memoria_literal_del_prospecto():
    m = C.extraer_memoria("Estamos contentos con nuestra página y queremos conservarla. Solo nos interesa algo para Instagram. No tenemos presupuesto este mes.")
    tipos = {(x["tipo"], x["servicio"]) for x in m}
    assert ("servicio_conservado", "web") in tipos and ("necesidad", "redes_sociales") in tipos
    restriccion = next(x for x in m if x["tipo"] == "restriccion")
    assert restriccion["texto"] == "No tenemos presupuesto este mes"  # literal, sin montos inventados
    assert C.extraer_memoria("Hola, buen día") == []


def test_necesidad_del_prospecto_prevalece_y_lo_conservado_no_se_propone():
    p = dict(HOTEL, web="", servicio_sugerido="web", _force_explicit=True,
             memoria=[{"tipo": "necesidad", "servicio": "crm", "texto": "Necesitamos ordenar clientes", "fuente": "prospecto"}])
    res = copilot.generate_cidiks_messages(p)
    assert res["servicio_sugerido"] == "crm" and res["fuente_servicio"] == "necesidad_confirmada"
    p2 = dict(HOTEL, respuesta="Queremos conservar nuestra página web.", servicio_sugerido="web", _force_explicit=True)
    assert copilot.generate_cidiks_messages(p2)["servicio_sugerido"] != "web"


def test_revisor_avisa_si_se_insiste_en_lo_rechazado():
    p = dict(HOTEL, memoria=[{"tipo": "servicio_conservado", "servicio": "web", "texto": "conservar", "fuente": "prospecto"}])
    r = V.revisar_mensaje("Hola, equipo de Posada del Sol. Les escribo de CÍDIKS. ¿Les hacemos una página web nueva?", p)
    assert {h["codigo"]: h["severidad"] for h in r["hallazgos"]}.get("MSG_SERVICIO_EXCLUIDO") == "revision"


# ---------------------------------------------------------------------------
# 2. Recursos gratuitos pertinentes y vigentes
# ---------------------------------------------------------------------------
def test_recursos_gratuitos_pertinentes_y_vigentes():
    recs = C.recursos_sugeridos("educativa", ["catalogos"], hoy="2026-11-25")
    assert [x["id"] for x in recs] == ["cidiks_comunidad", "meta_whatsapp"]  # empate: primero lo propio de CÍDIKS
    assert all(x["url"].startswith("https://") for x in recs)
    assert C.recursos_sugeridos("educativa", ["catalogos"], hoy="2027-03-01") == []  # vencidos: no se recomiendan
    assert all(x["origen"] == "cidiks" for x in C.recursos_sugeridos("orientacion", ["diseno"], hoy="2026-11-25"))
    # Lo que la persona pidió con sus palabras también cuenta (sin servicio detectado)
    a = C.analizar_respuesta("¿Tienen algún curso gratis de WhatsApp Business?", {"sector": "Turismo y hospedaje"}, hoy="2026-11-25")
    assert a["recursos"][0]["id"] == "meta_whatsapp"
    b = C.analizar_respuesta("Quiero aprender inteligencia artificial", {}, hoy="2026-11-25")
    assert "microsoft_ia" in [x["id"] for x in b["recursos"]]


def test_respuestas_sugeridas_breves_sin_precios_ni_propuestas():
    a = C.analizar_respuesta("Quiero aprender a vender por WhatsApp con catálogo", dict(HOTEL), hoy="2026-11-25")
    assert a["clasificacion"]["categoria"] == "educativa" and a["recursos"]
    assert a["recursos"][0]["url"] in a["respuesta_sugerida"]
    c = C.analizar_respuesta("¿Cuánto cobran por una página?", dict(HOTEL), hoy="2026-11-25")
    assert c["recursos"] == [] and "$" not in c["respuesta_sugerida"] and len(c["respuesta_sugerida"]) <= 180
    assert C.analizar_respuesta("Gracias por comunicarte, en breve te atenderemos", dict(HOTEL))["respuesta_sugerida"] == ""


# ---------------------------------------------------------------------------
# Consentimiento: un solo seguimiento manual, desde el día 5
# ---------------------------------------------------------------------------
def test_politica_de_seguimiento_unico():
    base = dict(HOTEL, fecha_contacto_confirmada="2026-11-20T10:00:00", primer_contacto_fecha="2026-11-20T10:00:00", contactos_confirmados_n=1)
    assert not C.estado_seguimiento(dict(HOTEL), hoy="2026-11-30")["permitido"]
    antes = C.estado_seguimiento(base, hoy="2026-11-22")
    assert not antes["permitido"] and antes["desde"] == "2026-11-25"
    assert C.estado_seguimiento(base, hoy="2026-11-26")["permitido"]
    assert C.estado_seguimiento(dict(base, respuesta="Gracias por comunicarte, en breve te atenderemos"), hoy="2026-11-26")["permitido"]
    assert not C.estado_seguimiento(dict(base, respuesta="Hola, ¿qué ofrecen?"), hoy="2026-11-26")["permitido"]
    assert not C.estado_seguimiento(dict(base, contactos_confirmados_n=2), hoy="2026-11-26")["permitido"]
    r = V.revisar_mensaje("Hola de nuevo, equipo de Posada del Sol. Les escribí hace unos días.", dict(base, _hoy="2026-11-22"), tipo="seguimiento")
    assert r["bloqueado"] and "SEG_NO_PERMITIDO" in {h["codigo"] for h in r["hallazgos"]}


# ---------------------------------------------------------------------------
# PC: confirmar respuestas, cierre/reapertura, relación educativa, retroalimentación
# ---------------------------------------------------------------------------
def _confirmar(client, nid, texto, clasificacion, **extra):
    return client.post("/api/interacciones/confirmar", json={"id": nid, "texto": texto, "clasificacion": clasificacion, **extra})


def test_rechazo_cierra_y_solo_se_reabre_con_solicitud_expresa(client):
    n = _negocio()
    analisis = client.post("/api/interacciones/analizar", json={"id": n["id"], "texto": "No nos interesa, no vuelvan a escribir"}).get_json()
    assert analisis["clasificacion"]["categoria"] == "rechazo"
    d = _confirmar(client, n["id"], "No nos interesa, no vuelvan a escribir", "rechazo").get_json()["prospecto"]
    assert d["prospeccion_cerrada"] == 1 and d["estado_comercial"] == "no_interesa"
    assert d["mensaje_personalizado"].startswith("[BLOQUEADO — PROSPECCIÓN CERRADA]")
    r = client.post("/api/mensajes/revisar", json={"id": n["id"], "texto": "Hola, equipo de Posada del Sol. ¿Platicamos?"}).get_json()
    assert r["bloqueado"]
    assert client.post("/api/prospects/reabrir", json={"id": n["id"], "nota": "corto"}).status_code == 400
    d2 = client.post("/api/prospects/reabrir", json={"id": n["id"], "nota": "Nos escribió de nuevo pidiendo una cotización"}).get_json()["prospecto"]
    assert d2["prospeccion_cerrada"] == 0 and not d2["mensaje_personalizado"].startswith("[BLOQUEADO")


def test_usuario_educativo_no_se_convierte_en_prospecto_comercial(client):
    n = _negocio()
    d = _confirmar(client, n["id"], "Quiero aprender a vender por WhatsApp", "educativa", recursos=["meta_whatsapp", "inexistente"]).get_json()["prospecto"]
    assert d["tipo_relacion"] == "educativa" and d["estado_comercial"] == "investigado"
    assert json.loads(d["interacciones"][0]["recursos_json"]) == ["meta_whatsapp"]
    assert "Conversación educativa" in d["hipotesis_comercial"]
    m = client.get("/api/metrics").get_json()
    assert m["conversaciones_educativas"] == 1 and m["oportunidades_comerciales"] == 0
    d2 = _confirmar(client, n["id"], "¿Cuánto cobran por un catálogo?", "contratacion").get_json()["prospecto"]
    assert d2["tipo_relacion"] == "comercial" and d2["estado_comercial"] == "interesado"
    assert client.get("/api/metrics").get_json()["oportunidades_comerciales"] == 1


def test_retroalimentacion_registrada_y_redactada(client):
    n = _negocio()
    _confirmar(client, n["id"], "No entendí la guía; escríbanme a ana@correo.com o al 954 123 4567", "retroalimentacion")
    fb = client.get("/api/retroalimentacion").get_json()
    assert fb["total"] == 1
    item = fb["items"][0]
    assert "ana@correo.com" not in item["texto"] and "954 123 4567" not in item["texto"]
    assert "[correo]" in item["texto"] and "[teléfono]" in item["texto"]
    assert "nombre" not in item and "Posada" not in json.dumps(item, ensure_ascii=False)


def test_correccion_vuelve_a_pedir_revision_de_identidad(client):
    n = _negocio()
    import validacion
    with db.get_db() as conn:
        conn.execute("UPDATE negocios SET identidad_revisada_firma = 'abc12345' WHERE id = ?", (n["id"],))
        conn.commit()
    _confirmar(client, n["id"], "Número equivocado, aquí no es ese hotel", "correccion")
    assert db.get_negocio_detail(n["id"])["identidad_revisada_firma"] == ""


def test_eventos_del_celular_interaccion_y_reapertura(client):
    n = _negocio()
    eventos = [
        {"id": "evt-int-00000001", "tipo": "interaccion", "uid": f"pc-{n['id']}", "fecha": "2026-11-25T10:00:00",
         "datos": {"texto": "Estamos contentos con nuestra página. No nos interesa.", "clasificacion": "rechazo",
                   "memoria": [{"tipo": "servicio_conservado", "servicio": "web", "texto": "contentos con nuestra página"},
                               {"tipo": "inventado", "servicio": "web"}]}},
        {"id": "evt-int-00000002", "tipo": "reabrir_prospeccion", "uid": f"pc-{n['id']}", "fecha": "2026-11-26T10:00:00",
         "datos": {"nota": "Nos pidieron por WhatsApp retomar la plática"}},
    ]
    data = {"file": (io.BytesIO(json.dumps({"formato": "sabueso-movil-avances", "version": 1, "eventos": eventos}).encode()), "a.json")}
    res = client.post("/api/movil/import", data=data, content_type="multipart/form-data").get_json()["resumen"]
    assert res["aplicados"] == 2, res
    d = db.get_negocio_detail(n["id"])
    assert d["prospeccion_reabierta"] == 1 and [m["tipo"] for m in d["memoria"]] == ["servicio_conservado"]
    exp = next(p for p in json.loads(client.get("/api/movil/export").data)["prospectos"] if p["id"] == n["id"])
    assert exp["memoria"][0]["servicio"] == "web" and exp["ultima_clasificacion"] == "rechazo" and exp["prospeccion_reabierta"] == 1


def test_motor_de_conversacion_sin_ia_ni_red():
    fuente = inspect.getsource(C)
    for prohibido in ("generativeai", "import requests", "urlopen", "openai", "anthropic"):
        assert prohibido not in fuente
