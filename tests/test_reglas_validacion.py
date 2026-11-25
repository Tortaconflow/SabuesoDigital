"""
Fases 0 y 1: reglas compartidas, validación de identidad y revisión de borradores.
"""
import copy
import inspect
import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import copilot
import reglas as R
import validacion as V


@pytest.fixture
def reglas_base():
    return json.loads(R.RUTA_REGLAS.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def recargar_reglas():
    R.cargar_reglas(forzar=True)
    yield
    R.cargar_reglas(forzar=True)


# ---------------------------------------------------------------------------
# Fase 0: reglas extensibles y validadas
# ---------------------------------------------------------------------------
def test_reglas_oficiales_son_validas():
    r = R.cargar_reglas(forzar=True)
    assert {s["id"] for s in r["sectores"]} >= {"hospedaje", "mobiliario", "alimentos"}
    # CÍDIKS es digitalización integral, no solo hospedaje
    assert {"web", "marketing", "crm", "automatizacion", "ia", "consultoria"} <= set(r["servicios"])


@pytest.mark.parametrize("romper,esperado", [
    (lambda r: r.pop("servicios"), "servicios"),
    (lambda r: r["sectores"][0]["reglas_servicio"].append({"si": [], "servicio": "inexistente"}), "servicio desconocido"),
    (lambda r: r["sectores"][0]["reglas_servicio"].insert(0, {"si": ["llueve"], "servicio": "web"}), "condición desconocida"),
    (lambda r: r["sectores"][0]["preguntas"]["web"].update(default="¿Una? ¿Dos?"), "más de una pregunta"),
    (lambda r: r["sectores"].append(copy.deepcopy(r["sectores"][0])), "Sector repetido"),
    (lambda r: r["mensajes"].update(objetivo_max=500), "incoherentes"),
])
def test_reglas_invalidas_fallan_con_mensaje_claro(reglas_base, romper, esperado):
    romper(reglas_base)
    with pytest.raises(R.ReglasInvalidas, match=esperado):
        R.validar_reglas(reglas_base)


def test_giro_nuevo_sin_modificar_el_nucleo(reglas_base, tmp_path, monkeypatch):
    reglas_base["sectores"].append({
        "id": "veterinaria", "nombre": "Veterinarias",
        "palabras_clave": {"fuertes": ["veterinaria", "veterinario"], "debiles": ["mascotas"]},
        "vocabulario": ["mascotas", "consultas veterinarias"], "frases_propias": [],
        "reglas_servicio": [{"si": ["con_whatsapp"], "servicio": "automatizacion"}, {"si": [], "servicio": "web"}],
        "preguntas": {"automatizacion": {"default": "¿Agendan las consultas de sus mascotas por WhatsApp a mano?"}},
        "hipotesis": {},
    })
    ruta = tmp_path / "reglas.json"
    ruta.write_text(json.dumps(reglas_base, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("SABUESO_REGLAS_PATH", str(ruta))
    R.cargar_reglas(forzar=True)
    res = copilot.generate_cidiks_messages({
        "id": 9, "nombre": "Veterinaria Patitas", "sector": "Veterinaria", "municipio": "Oaxaca de Juárez",
        "web": "https://patitas.example", "whatsapp": "529511119999", "whatsapp_estado": "WHATSAPP_COMPROBADO"})
    assert res["sector_id"] == "veterinaria"
    assert res["servicio_sugerido"] == "automatizacion"
    assert "mascotas" in res["mensaje_personalizado"]


def test_texto_comparable_ignora_acentos_y_signos():
    assert R.texto_comparable("¡Cabañas—Mazunte!") == " cabanas mazunte "
    assert R.contiene_frase(R.texto_comparable("Muebles para HABITACIÓN"), "muebles para habitacion")
    assert not R.contiene_frase(R.texto_comparable("habitacional"), "habitacion")


# ---------------------------------------------------------------------------
# Fase 1: identidad (revisión humana, nunca invalidación)
# ---------------------------------------------------------------------------
def test_dominio_descriptivo_no_pide_revision():
    r = V.analizar_identidad({"nombre": "Hotel Posada Real Resort", "sector": "Hospedaje", "municipio": "Puerto Escondido",
                              "web": "https://hotelenpuertoescondido.com"})
    assert not r["requiere_revision"]
    assert "IDENT_DOMINIO_DESCRIPTIVO" in {h["codigo"] for h in r["hallazgos"]}


@pytest.mark.parametrize("nombre,web", [
    ("Posada del Sol", "https://posadadelsol.com"),
    ("Raíz Hotel Boutique", "https://raiz-hotel.com"),
    ("Hotel B Boutique", "https://hotelb.com"),
    ("Artesanías Don Benito", "https://artesaniasdonbenito.com"),
    ("Hotel El Alquimista Yoga Spa", "https://elalquimistahotel.mx/contacto/"),
])
def test_nombres_que_si_coinciden_con_su_dominio(nombre, web):
    assert V.comparar_nombre_dominio(nombre, V.dominio_de(web)) == "coincide"


def test_directorio_y_red_social():
    dire = V.analizar_identidad({"nombre": "Hotel Mar", "web": "https://www.tripadvisor.com.mx/Hotel_Review-x"})
    assert "IDENT_SITIO_DIRECTORIO" in {h["codigo"] for h in dire["hallazgos"]} and dire["requiere_revision"]
    red = V.analizar_identidad({"nombre": "Hotel Mar", "web": "https://facebook.com/hotelmar"})
    assert not red["requiere_revision"]


def test_contacto_compartido_con_otro_negocio_pide_revision():
    p = {"id": 1, "nombre": "Hotel Uno", "municipio": "Mazunte", "web": "https://hoteluno.example", "whatsapp": "529581112233"}
    agencia = {"id": 2, "nombre": "Diseños Web Costa", "municipio": "Mazunte", "web": "https://disenoscosta.example", "telefono": "958 111 2233"}
    r = V.analizar_identidad(p, contexto=[p, agencia])
    assert r["requiere_revision"]
    assert "IDENT_CONTACTO_COMPARTIDO" in {h["codigo"] for h in r["hallazgos"]}


def test_la_confirmacion_humana_caduca_si_cambian_los_datos():
    p = {"nombre": "Hotel Casa Azul", "sector": "Hospedaje", "web": "https://hotelmarbella-pxm.example"}
    p["identidad_revisada_firma"] = V.firma_identidad(p)
    assert V.analizar_identidad(p)["confirmada_por_humano"]
    p["web"] = "https://otro-sitio-distinto.example"
    assert V.analizar_identidad(p)["requiere_revision"]


def test_revision_no_invalida_ni_marca_no_contactar():
    res = copilot.generate_cidiks_messages({"id": 3, "nombre": "Hotel Casa Azul", "sector": "Hospedaje",
                                            "web": "https://hotelmarbella-pxm.example", "whatsapp": "529547778899"})
    assert res["identidad_verificada"] is True
    assert res["servicio_sugerido"] != "no_contactar"
    assert res["tipo_observacion"] == "REQUIERE_REVISION_HUMANA"


# ---------------------------------------------------------------------------
# Fase 1: revisión de borradores
# ---------------------------------------------------------------------------
HOTEL = {"id": 5, "nombre": "Posada del Sol", "sector": "Hospedaje", "municipio": "Puerto Escondido"}


def _codigos(r):
    return {h["codigo"]: h["severidad"] for h in r["hallazgos"]}


def test_longitud_nunca_bloquea_por_si_sola():
    base = "Hola, equipo de Posada del Sol. Les escribo de CÍDIKS. "
    en_objetivo = V.revisar_mensaje(base + "Vi su página. ¿Atienden por WhatsApp?", HOTEL)
    assert en_objetivo["en_objetivo"] and not en_objetivo["hallazgos"]
    largo = V.revisar_mensaje(base + "x " * 80 + "¿Atienden por WhatsApp?", HOTEL)
    assert _codigos(largo).get("MSG_LARGO") == "advertencia"
    assert not largo["bloqueado"] and not largo["requiere_aprobacion"]
    medio = V.revisar_mensaje(base + "x " * 55 + "¿Atienden por WhatsApp?", HOTEL)
    assert _codigos(medio).get("MSG_FUERA_OBJETIVO") == "info"


def test_mas_de_una_pregunta_genera_advertencia():
    r = V.revisar_mensaje("Hola, equipo de Posada del Sol. ¿Tienen WhatsApp? ¿Y página?", HOTEL)
    assert _codigos(r).get("MSG_PREGUNTAS") == "advertencia"


def test_mensaje_generico_y_sin_nombre():
    r = V.revisar_mensaje("Hola. Le ofrecemos soluciones integrales para llevar su negocio al siguiente nivel. ¿Le interesa?", HOTEL)
    c = _codigos(r)
    assert c.get("MSG_GENERICO") == "advertencia" and c.get("MSG_SIN_NOMBRE") == "advertencia"


def test_aviso_interno_no_es_enviable():
    r = V.revisar_mensaje("[REVISIÓN HUMANA REQUERIDA]\nConfirma el nombre.", HOTEL)
    assert r["bloqueado"]


def test_saludo_comun_no_es_otro_negocio():
    r = V.revisar_mensaje("Hola, buen día. Equipo de Posada del Sol: les escribo de CÍDIKS. ¿Atienden por WhatsApp?", HOTEL)
    assert "MSG_SALUDO_OTRO_NOMBRE" not in _codigos(r)


@pytest.mark.parametrize("texto", [
    "Hola, borrador editado antes de abrir WhatsApp. Equipo de Posada del Sol: ¿atienden por aquí?",
    "Hola, les escribo de CÍDIKS al equipo de Posada del Sol. ¿Atienden por WhatsApp?",
    "Hola, soy Ana de CÍDIKS. Vi la página de Posada del Sol. ¿Atienden por WhatsApp?",
    "Hola, Les escribo de CÍDIKS para Posada del Sol. ¿Atienden por WhatsApp?",
    "Hola de nuevo, equipo de Posada del Sol. Les escribí hace unos días.",
])
def test_saludos_comunes_no_son_otro_negocio(texto):
    assert "MSG_SALUDO_OTRO_NOMBRE" not in _codigos(V.revisar_mensaje(texto, HOTEL))


@pytest.mark.parametrize("texto", [
    "Hola, Hotel Marbella. Les escribo de CÍDIKS. ¿Atienden por WhatsApp?",
    "Buen día, equipo de Hotel Marbella de nuevo. ¿Atienden por WhatsApp?",
    "Hola, Equipo de Cabañas Luna. ¿Atienden por WhatsApp?",
])
def test_saludo_a_otro_nombre_propio_se_bloquea(texto):
    assert _codigos(V.revisar_mensaje(texto, HOTEL)).get("MSG_SALUDO_OTRO_NOMBRE") == "bloqueo"


def test_frase_propia_del_giro_permite_el_termino():
    mueble = {"id": 6, "nombre": "Muebles Rústicos del Valle", "sector": "Mobiliario"}
    r = V.revisar_mensaje("Hola, equipo de Muebles Rústicos del Valle. ¿Venden muebles para habitación por WhatsApp?", mueble)
    assert "MSG_VOCABULARIO_OTRO_GIRO" not in _codigos(r)


def test_mensajes_generados_cumplen_objetivo_en_todos_los_giros():
    r = R.cargar_reglas()
    for i, sector in enumerate(r["sectores"]):
        p = {"id": i, "nombre": f"Negocio Prueba {i}", "sector": sector["nombre"], "municipio": "Oaxaca de Juárez",
             "web": f"https://negocioprueba{i}.example", "whatsapp": "52951000000" + str(i),
             "whatsapp_estado": "WHATSAPP_COMPROBADO"}
        res = copilot.generate_cidiks_messages(p)
        assert not res["bloqueado_envio"], (sector["id"], res["mensaje_personalizado"])
        for campo in ("mensaje_personalizado", "mensaje_calido"):
            msg = res[campo]
            assert len(msg) < r["mensajes"]["advertencia_desde"], (sector["id"], msg)
            assert msg.count("?") == 1, (sector["id"], msg)
            assert not res["revision"]["mensajes"][campo]["hallazgos"] or all(
                h["severidad"] == "info" for h in res["revision"]["mensajes"][campo]["hallazgos"]), (sector["id"], res["revision"]["mensajes"][campo])


# ---------------------------------------------------------------------------
# Necesidad confirmada y consumo de tokens
# ---------------------------------------------------------------------------
def test_necesidad_no_reconocida_se_muestra_y_no_se_ignora():
    res = copilot.generate_cidiks_messages({"id": 7, "nombre": "Hotel Mar", "sector": "Hospedaje", "web": "https://hotelmar.example",
                                            "whatsapp": "529581110000", "whatsapp_estado": "WHATSAPP_COMPROBADO",
                                            "necesidad_expresada": "Queremos algo para el aniversario"})
    assert "Queremos algo para el aniversario" in res["hipotesis_comercial"]
    assert res["fuente_servicio"] != "necesidad_confirmada"


def test_consumo_de_tokens_es_cero_y_no_hay_llamadas_a_ia():
    res = copilot.generate_cidiks_messages({"id": 8, "nombre": "Posada del Sol", "web": "https://posadadelsol.com",
                                            "whatsapp": "529541240793"}, use_ai=True, api_key="clave-falsa")
    assert res["consumo_tokens"] == 0 and res["motor"] == "reglas_deterministas"
    fuente = inspect.getsource(copilot) + inspect.getsource(V) + inspect.getsource(R)
    for prohibido in ("generativeai", "import requests", "urlopen", "openai", "anthropic"):
        assert prohibido not in fuente


# ---------------------------------------------------------------------------
# Integración PC: API y sincronización con el celular
# ---------------------------------------------------------------------------
import io

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


def _casa_azul():
    return db.save_or_update_negocio({"nombre": "Hotel Casa Azul", "sector": "Turismo y hospedaje", "municipio": "Puerto Escondido",
                                      "web": "https://hotelmarbella-pxm.example", "whatsapp": "529547778899",
                                      "whatsapp_estado": "WHATSAPP_COMPROBADO"})


def test_api_revisar_mensaje(client):
    n = _casa_azul()
    r = client.post("/api/mensajes/revisar", json={"id": n["id"], "texto": "Hola, equipo de Hotel Marbella. ¿Atienden por WhatsApp?"}).get_json()
    assert r["bloqueado"] and "MSG_SALUDO_OTRO_NOMBRE" in {h["codigo"] for h in r["hallazgos"]}


def test_api_revision_identidad_confirmar_regenera_y_audita(client):
    n = _casa_azul()
    det = client.get(f"/api/prospects/{n['id']}").get_json()
    assert det["revision_identidad"]["requiere_revision"] is True
    r = client.post("/api/prospects/identity-review", json={"id": n["id"], "decision": "confirmar", "nota": "Llamé y es el mismo"}).get_json()
    assert r["success"] and r["prospecto"]["revision_identidad"]["confirmada_por_humano"] is True
    assert r["copilot"]["bloqueado_envio"] is False
    assert db.get_negocio_detail(n["id"])["mensaje_personalizado"].startswith("Hola") or "Hotel Casa Azul" in db.get_negocio_detail(n["id"])["mensaje_personalizado"]
    assert any(a["operacion"] == "REVISION_HUMANA_IDENTIDAD" for a in db.get_audit_log(n["id"]))


def test_api_revision_identidad_corregir_nombre(client):
    n = _casa_azul()
    r = client.post("/api/prospects/identity-review", json={"id": n["id"], "decision": "corregir", "nombre": "Hotel Marbella"}).get_json()
    assert r["prospecto"]["nombre"] == "Hotel Marbella"
    assert "Hotel Marbella" in r["copilot"]["mensaje_personalizado"]


def test_export_y_evento_revision_identidad_desde_el_celular(client):
    n = _casa_azul()
    paquete = json.loads(client.get("/api/movil/export").data)
    exp = next(p for p in paquete["prospectos"] if p["id"] == n["id"])
    assert exp["identidad_requiere_revision"] is True and exp["revision_identidad"]
    evento = {"id": "evt-ident-0000001", "tipo": "revision_identidad", "uid": f"pc-{n['id']}", "fecha": "2026-11-25T12:00:00",
              "datos": {"decision": "confirmar", "firma_vista": exp["firma_identidad"], "nota": "Confirmado por teléfono"}}
    data = {"file": (io.BytesIO(json.dumps({"formato": "sabueso-movil-avances", "version": 1, "eventos": [evento]}).encode()), "a.json")}
    res = client.post("/api/movil/import", data=data, content_type="multipart/form-data").get_json()["resumen"]
    assert res["aplicados"] == 1, res
    assert client.get(f"/api/prospects/{n['id']}").get_json()["revision_identidad"]["confirmada_por_humano"] is True


def test_evento_de_revision_rechazado_si_los_datos_cambiaron(client):
    n = _casa_azul()
    evento = {"id": "evt-ident-0000002", "tipo": "revision_identidad", "uid": f"pc-{n['id']}", "fecha": "2026-11-25T12:00:00",
              "datos": {"decision": "confirmar", "firma_vista": "00000000"}}
    data = {"file": (io.BytesIO(json.dumps({"formato": "sabueso-movil-avances", "version": 1, "eventos": [evento]}).encode()), "a.json")}
    res = client.post("/api/movil/import", data=data, content_type="multipart/form-data").get_json()["resumen"]
    assert res["aplicados"] == 0 and "cambiaron" in res["errores"][0]["motivo"]
