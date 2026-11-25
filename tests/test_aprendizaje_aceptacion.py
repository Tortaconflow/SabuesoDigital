"""
Pruebas de aceptación — Fase de aprendizaje basado en errores reales.

Cada prueba reproduce un error observado en interacciones reales (ver APRENDIZAJE_ERRORES.md).
Los 7 casos ya pasan (Fases 1, 2 y 3).
"""
import re
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import copilot
import db

RE_HOSPEDAJE = re.compile(r"habitaci|hu[eé]sped|hospedaje|reservaci", re.IGNORECASE)
CAMPOS_MENSAJE = ("mensaje_personalizado", "mensaje_calido", "mensaje_seguimiento")

MUEBLERIA = {
    "id": 101,
    "nombre": "Muebles Rústicos del Valle",
    "sector": "Mobiliario",
    "municipio": "Oaxaca de Juárez",
    "web": "https://mueblesrusticos.example",
    "whatsapp": "529511234567",
    "whatsapp_estado": "WHATSAPP_COMPROBADO",
    "telefono": "9511234567",
    "email": "ventas@mueblesrusticos.example",
    "redes_sociales": "https://facebook.com/mueblesrusticos",
}


def _sin_vocabulario_de_hospedaje(res):
    textos = [res[k] for k in CAMPOS_MENSAJE] + [res["hipotesis_comercial"], res["pregunta_comercial"]]
    return not any(RE_HOSPEDAJE.search(t or "") for t in textos)


# ---------------------------------------------------------------------------
# Caso 1. Una empresa de mobiliario nunca debe recibir una propuesta sobre habitaciones.
# Error real: «catálogos y fichas ligeras de habitaciones y tarifas» y «WhatsApp para reservaciones».
# ---------------------------------------------------------------------------
def test_caso1_mobiliario_no_recibe_propuesta_de_habitaciones():
    res = copilot.generate_cidiks_messages(dict(MUEBLERIA))
    assert not res["bloqueado_envio"]
    assert _sin_vocabulario_de_hospedaje(res), res["mensaje_personalizado"]
    assert res["sector_id"] == "mobiliario"


def test_caso1_mueble_encontrado_en_busqueda_de_hoteles_va_a_revision():
    # La búsqueda era «Turismo y hospedaje» pero el negocio es una mueblería.
    p = dict(MUEBLERIA, sector="Turismo y hospedaje")
    res = copilot.generate_cidiks_messages(p)
    assert res["bloqueado_envio"] is True or _sin_vocabulario_de_hospedaje(res)
    assert res["identidad_verificada"] is True  # revisión humana, no invalidación
    codigos = {h["codigo"] for h in res["revision"]["identidad"]}
    assert "IDENT_SECTOR_DISCREPANCIA" in codigos


def test_caso1_revisor_detecta_propuesta_de_otro_giro():
    import validacion
    msg = "Hola, equipo de Muebles Rústicos del Valle. Les escribo de CÍDIKS. ¿Comparten tarifas de habitaciones por WhatsApp?"
    r = validacion.revisar_mensaje(msg, dict(MUEBLERIA))
    codigos = {h["codigo"]: h["severidad"] for h in r["hallazgos"]}
    assert codigos.get("MSG_VOCABULARIO_OTRO_GIRO") == "revision"
    assert r["requiere_aprobacion"] is True


def test_caso1_contexto_y_evidencia_permiten_el_termino():
    # Corrección 1: no prohibir palabras de forma absoluta; si el negocio lo respalda, se permite.
    import validacion
    p = dict(MUEBLERIA, observacion_verificada="Fabrican muebles para habitaciones de hotel y cabañas.")
    msg = "Hola, equipo de Muebles Rústicos del Valle. Les escribo de CÍDIKS. ¿Venden sus muebles para habitaciones de hotel por WhatsApp?"
    r = validacion.revisar_mensaje(msg, p)
    assert "MSG_VOCABULARIO_OTRO_GIRO" not in {h["codigo"] for h in r["hallazgos"]}


# ---------------------------------------------------------------------------
# Caso 2. El nombre de otro negocio debe bloquear la generación del mensaje.
# Error real: «Hotel Casa Azul» con el sitio de otro hotel generó un mensaje listo para enviar.
# ---------------------------------------------------------------------------
CASA_AZUL = {
    "id": 202,
    "nombre": "Hotel Casa Azul",
    "sector": "Turismo y hospedaje",
    "municipio": "Puerto Escondido",
    "web": "https://hotelmarbella-pxm.example",
    "whatsapp": "529547778899",
    "whatsapp_estado": "WHATSAPP_COMPROBADO",
}


def test_caso2_nombre_distinto_al_sitio_bloquea_y_pide_revision_humana():
    res = copilot.generate_cidiks_messages(dict(CASA_AZUL))
    assert res["bloqueado_envio"] is True
    assert res["mensaje_personalizado"].startswith("[REVISIÓN HUMANA REQUERIDA]")
    # Corrección 2: revisión humana, NO invalidación automática.
    assert res["identidad_verificada"] is True
    assert res["servicio_sugerido"] not in ("no_contactar",)
    assert "IDENT_NOMBRE_DOMINIO" in {h["codigo"] for h in res["revision"]["identidad"]}


def test_caso2_tras_confirmacion_humana_si_genera_mensaje():
    import validacion
    p = dict(CASA_AZUL)
    p["identidad_revisada_firma"] = validacion.firma_identidad(p)
    res = copilot.generate_cidiks_messages(p)
    assert res["bloqueado_envio"] is False
    assert "Hotel Casa Azul" in res["mensaje_personalizado"]


def test_caso2_mensaje_dirigido_a_otro_negocio_se_bloquea():
    import validacion
    msg = "Hola, equipo de Hotel Marbella. Les escribo de CÍDIKS. ¿Atienden reservaciones por WhatsApp?"
    r = validacion.revisar_mensaje(msg, dict(CASA_AZUL))
    assert r["bloqueado"] is True
    assert "MSG_SALUDO_OTRO_NOMBRE" in {h["codigo"] for h in r["hallazgos"]}


def test_caso2_mensaje_que_menciona_otro_prospecto_se_bloquea():
    import validacion
    otro = {"id": 303, "nombre": "Posada Mar Azul", "web": "https://posadamarazul.example"}
    msg = "Hola, equipo de Hotel Casa Azul. Les escribo de CÍDIKS; trabajamos con Posada Mar Azul. ¿Atienden por WhatsApp?"
    r = validacion.revisar_mensaje(msg, dict(CASA_AZUL), contexto=[otro])
    assert r["bloqueado"] is True
    assert "MSG_OTRO_NEGOCIO" in {h["codigo"] for h in r["hallazgos"]}


# ---------------------------------------------------------------------------
# Caso 7. Las necesidades confirmadas por el prospecto prevalecen sobre las inferencias.
# Error real: «necesidad_expresada» se guardaba pero nunca se usaba para decidir.
# ---------------------------------------------------------------------------
def test_caso7_necesidad_confirmada_determina_la_solucion():
    p = {
        "id": 404, "nombre": "Hotel Las Palmas", "sector": "Turismo y hospedaje", "municipio": "Mazunte",
        "web": "", "telefono": "9581112222",
        "necesidad_expresada": "Necesitamos un CRM para dar seguimiento a nuestros clientes",
        "servicio_sugerido": "web", "_force_explicit": True,  # la inferencia/elección previa decía «web»
    }
    res = copilot.generate_cidiks_messages(p)
    assert res["servicio_sugerido"] == "crm"
    assert res["fuente_servicio"] == "necesidad_confirmada"
    assert "CRM" in res["hipotesis_comercial"] or "crm" in res["hipotesis_comercial"].lower()


# ---------------------------------------------------------------------------
# Fase 2 (casos 3, 4 y 6) y Fase 3 (caso 5, QR local).
# ---------------------------------------------------------------------------
def test_caso3_si_quiere_conservar_su_pagina_no_se_insiste():
    p = {"id": 505, "nombre": "Hotel Las Palmas", "sector": "Turismo y hospedaje", "municipio": "Puerto Escondido",
         "web": "https://laspalmas.example", "telefono": "9541112222", "servicio_sugerido": "web",
         "respuesta": "Gracias, estamos contentos con nuestra página y queremos conservarla."}
    res = copilot.generate_cidiks_messages(p)
    assert res["servicio_sugerido"] != "web"
    assert not re.search(r"p[aá]gina|sitio|web", res["mensaje_seguimiento"], re.IGNORECASE)


def test_caso4_respuesta_automatica_no_cuenta_como_oportunidad(isolated_sqlite_db):
    n = db.save_or_update_negocio({"nombre": "Posada Sol", "municipio": "Mazunte", "whatsapp": "529581112233"})
    db.record_human_contact(n["id"], "whatsapp", "")
    db.save_or_update_negocio({"id": n["id"], "respuesta": "¡Hola! Gracias por comunicarte con Posada Sol. En breve te atenderemos."})
    m = db.get_dashboard_metrics()
    assert m["respuestas_recibidas"] == 0


def test_caso5_qr_recibido_se_interpreta_antes_de_recomendar():
    p = {"id": 606, "nombre": "Restaurante La Palapa", "sector": "Restaurante", "municipio": "Mazunte",
         "web": "https://lapalapa.example", "whatsapp": "529581239876", "whatsapp_estado": "WHATSAPP_COMPROBADO",
         "qr_recibidos": [{"tipo": "menu_digital", "dominio": "menu.example"}]}
    res = copilot.generate_cidiks_messages(p)
    assert res["servicio_sugerido"] != "catalogos"
    assert "ya cuenta con menú digital" in res["observacion_verificada"].lower()


def test_caso6_rechazo_explicito_cierra_la_prospeccion():
    p = {"id": 707, "nombre": "Cabañas Luna", "sector": "Turismo y hospedaje", "municipio": "Zipolite",
         "web": "https://lunaz.example", "whatsapp": "529583334455", "estado_comercial": "contactado",
         "respuesta": "No nos interesa, por favor no vuelvan a escribir."}
    res = copilot.generate_cidiks_messages(p)
    assert res["bloqueado_envio"] is True
    assert res["mensaje_seguimiento"].startswith("[BLOQUEADO")
