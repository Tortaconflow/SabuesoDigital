import pytest
import re
import db
import app
import copilot


def test_normalize_mexican_phone_formats():
    """Prueba normalización de formatos válidos mexicanos."""
    # 10 dígitos nacionales
    res1 = app.normalize_mexican_phone("9541240793")
    assert res1["valid"] is True
    assert res1["e164"] == "+529541240793"
    assert res1["wa_digits"] == "529541240793"

    # Con espacios y guiones
    res2 = app.normalize_mexican_phone("+52 (954) 124-0793")
    assert res2["valid"] is True
    assert res2["e164"] == "+529541240793"
    assert res2["wa_digits"] == "529541240793"

    # 13 dígitos con prefijo histórico 521 (móvil México)
    res3 = app.normalize_mexican_phone("5219541240793")
    assert res3["valid"] is True
    assert res3["e164"] == "+529541240793"
    assert res3["wa_digits"] == "529541240793"


def test_normalize_phone_rejects_corrupted_and_years():
    """Prueba el rechazo estricto de años y concatenaciones de dígitos."""
    # Año 1990 (caso ID 2)
    assert app.normalize_mexican_phone("1990")["valid"] is False

    # Números concatenados del DOM (caso ID 1)
    assert app.normalize_mexican_phone("777344 31 796875 15 011719 13")["valid"] is False

    # Cadenas repetitivas
    assert app.normalize_mexican_phone("0000000000")["valid"] is False

    # Vacíos
    assert app.normalize_mexican_phone("")["valid"] is False
    assert app.normalize_mexican_phone(None)["valid"] is False


def test_extract_wa_links_and_widgets():
    """Prueba detección de enlaces wa.me, api.whatsapp y widgets DOM."""
    # Enlace wa.me con +52
    html1 = '<a href="https://wa.me/+529541240793?text=Hola">Escríbenos</a>'
    res1 = app.extract_and_classify_channels(html1, "https://ejemplo.com")
    assert res1["whatsapp_estado"] == "WHATSAPP_COMPROBADO"
    assert res1["whatsapp"] == "529541240793"
    assert res1["fuente_whatsapp"] == "enlace_directo_wa"

    # Enlace api.whatsapp.com/send/?phone=52...
    html2 = '<a href="https://api.whatsapp.com/send/?phone=529541240793&text=Info">WhatsApp</a>'
    res2 = app.extract_and_classify_channels(html2, "https://ejemplo.com")
    assert res2["whatsapp_estado"] == "WHATSAPP_COMPROBADO"
    assert res2["whatsapp"] == "529541240793"

    # Atributo de widget WordPress Joinchat
    html3 = '<div class="joinchat" data-phone="9541240793" data-message="Hola"></div>'
    res3 = app.extract_and_classify_channels(html3, "https://ejemplo.com")
    assert res3["whatsapp_estado"] == "WHATSAPP_COMPROBADO"
    assert res3["whatsapp"] == "529541240793"
    assert res3["fuente_whatsapp"] == "widget_whatsapp_dom"


def test_no_false_positive_when_whatsapp_word_has_no_number():
    """Verifica que la simple palabra 'whatsapp' en texto NO marque WhatsApp comprobado."""
    html = '<p>Síguenos en redes o contáctanos por WhatsApp para más informes.</p>'
    res = app.extract_and_classify_channels(html, "https://ejemplo.com")
    assert res["whatsapp_estado"] == "SIN_WHATSAPP_COMPROBABLE"
    assert res["whatsapp"] == ""
    assert res["has_whatsapp"] is False


def test_contextual_text_mention_marked_pending():
    """Verifica que una mención textual con número sea clasificada como pendiente."""
    html = '<p>Reservaciones directas por WhatsApp: 954 124 0793</p>'
    res = app.extract_and_classify_channels(html, "https://ejemplo.com")
    assert res["whatsapp_estado"] == "WHATSAPP_PENDIENTE_VERIFICACION"
    assert res["whatsapp"] == "529541240793"
    assert res["fuente_whatsapp"] == "mencion_texto_whatsapp"


def test_filter_fake_library_emails():
    """Verifica que falsos correos como select2@4.1.0-rc.0 sean descartados."""
    html = '<p>Contacto: info@hotelreal.com y script select2@4.1.0-rc.0 cargado</p>'
    res = app.extract_and_classify_channels(html, "https://ejemplo.com")
    assert "info@hotelreal.com" in res["email"]
    assert "select2" not in res["email"]


def test_copilot_conversational_messages_no_technical_jargon():
    """Verifica que los mensajes CÍDIKS no incluyan jerga técnica, errores afirmados ni cumplidos genéricos."""
    prospect = {
        "id": 1,
        "nombre": "Posada del Sol",
        "municipio": "Puerto Escondido",
        "sector": "Turismo y hospedaje",
        "web": "https://posadadelsol.com",
        "whatsapp": "529541240793",
        "whatsapp_estado": "WHATSAPP_COMPROBADO",
        "servicio_sugerido": "catalogos",
        "_force_explicit": True
    }
    res = copilot.generate_cidiks_messages(prospect)
    msg = res["mensaje_personalizado"]

    # No jerga técnica
    forbidden = ["http", "406", "ssl", "responsive", "meta", "viewport", "dom", "auditoría"]
    for term in forbidden:
        assert term not in msg.lower(), f"El término técnico '{term}' no debe aparecer en el mensaje."

    # Sin cumplidos genéricos vacíos
    flattery = [
        "nos gustó mucho la propuesta de su negocio",
        "estancia agradable en la costa",
        "se nota el cuidado que le ponen",
        "excelente opción de hospedaje"
    ]
    for f in flattery:
        assert f not in msg.lower()

    # Debe contener CÍDIKS, referencia verificable y pregunta abierta
    assert "CÍDIKS" in msg
    assert "Puerto Escondido" in msg
    assert "?" in msg
    assert res["observacion_verificada"] != ""
    assert res["hipotesis_comercial"] != ""
    assert res["pregunta_comercial"] != ""


def test_copilot_service_catalog_orientation():
    """Prueba que el catálogo de capacidades CÍDIKS oriente el mensaje al servicio y canal real."""
    p_web = {
        "id": 1,
        "nombre": "Hotel A",
        "municipio": "Mazunte",
        "web": "https://hotela.com",
        "telefono": "+52 958 111 2233",
        "whatsapp_estado": "SIN_WHATSAPP_COMPROBABLE",
        "servicio_sugerido": "web",
        "_force_explicit": True
    }
    res_web = copilot.generate_cidiks_messages(p_web)
    assert "web" in res_web["mensaje_personalizado"].lower()
    # Como NO tiene WhatsApp, la pregunta debe preguntar si planean incorporar WhatsApp o prefieren teléfono/correo
    assert "teléfono" in res_web["pregunta_comercial"].lower() or "incorporar" in res_web["pregunta_comercial"].lower()

    p_cat = {
        "id": 2,
        "nombre": "Hotel B Boutique",
        "municipio": "Mazunte",
        "web": "https://hotelb.com",
        "whatsapp": "529581234567",
        "whatsapp_estado": "WHATSAPP_COMPROBADO",
        "servicio_sugerido": "catalogos",
        "_force_explicit": True
    }
    res_cat = copilot.generate_cidiks_messages(p_cat)
    assert "catálogo" in res_cat["mensaje_personalizado"].lower() or "tarifa" in res_cat["mensaje_personalizado"].lower()


def test_copilot_blocks_unverified_identity():
    """Verifica el bloqueo de mensajes listos para enviar cuando la identidad comercial no está verificada."""
    # Caso Monte Casino con visor PDF ajeno al giro y sin canales
    p_unverified = {
        "id": 2,
        "nombre": "Hotel Monte Casino",
        "web": "https://www.jmcs.org.mx/plugins/generic/pdfJsViewer/pdf.js/web/viewer.html?file=test",
        "whatsapp": "",
        "telefono": "",
        "email": ""
    }
    res = copilot.generate_cidiks_messages(p_unverified)
    assert res["identidad_verificada"] is False
    assert res["bloqueado_envio"] is True
    assert res["servicio_sugerido"] == "no_contactar"
    assert "[BLOQUEADO" in res["mensaje_personalizado"]


def test_copilot_recommends_investigate_more_for_corporate_luxury():
    """Verifica que hoteles de grupo/lujo sin WhatsApp directo reciban recomendación 'investigar_mas'."""
    p_corp = {
        "id": 4,
        "nombre": "Hotel Escondido",
        "web": "https://www.hotelescondido.com/",
        "whatsapp": "",
        "whatsapp_estado": "SIN_WHATSAPP_COMPROBABLE",
        "telefono": "",
        "email": ""
    }
    res = copilot.generate_cidiks_messages(p_corp)
    assert res["identidad_verificada"] is True
    assert res["bloqueado_envio"] is True
    assert res["servicio_sugerido"] == "investigar_mas"
    assert "INVESTIGAR MÁS" in res["mensaje_personalizado"]


def test_copilot_differentiates_services_across_profiles():
    """Verifica que no se asigne automáticamente 'catalogos' a todos los hospedajes."""
    # 1. Resort/Posada grande -> flyers
    s1 = copilot.select_suggested_service({
        "nombre": "Hotel Posada Real Resort",
        "web": "https://hotelenpuertoescondido.com",
        "whatsapp": "529541639198",
        "whatsapp_estado": "WHATSAPP_COMPROBADO"
    }, honor_explicit=False)
    # 2. Hotel de surf sin WA pero con redes y teléfono -> redes_sociales
    s2 = copilot.select_suggested_service({
        "nombre": "Hotel Rockaway Surf Zicatela",
        "web": "https://hotelrockaway.com",
        "telefono": "+52 954 148 8948",
        "redes_sociales": "instagram.com/hotelrockaway",
        "whatsapp_estado": "SIN_WHATSAPP_COMPROBABLE"
    }, honor_explicit=False)
    # 3. Hotel boutique pequeño con WA directo -> catalogos
    s3 = copilot.select_suggested_service({
        "nombre": "Raíz Hotel Boutique",
        "web": "https://raiz-hotel.com",
        "whatsapp": "529541240793",
        "whatsapp_estado": "WHATSAPP_COMPROBADO"
    }, honor_explicit=False)

    assert s1 == "flyers"
    assert s2 == "redes_sociales"
    assert s3 == "catalogos"
    assert len({s1, s2, s3}) == 3


def test_database_tray_metrics_and_persistence(isolated_sqlite_db):
    """Verifica que la base guarde las dos bandejas y calcule métricas correctamente."""
    # 1. Prospecto con WhatsApp comprobado
    p1 = db.save_or_update_negocio({
        "nombre": "Hotel Con WA",
        "municipio": "Puerto Escondido",
        "whatsapp": "529541240793",
        "whatsapp_estado": "WHATSAPP_COMPROBADO",
        "fuente_whatsapp": "enlace_directo_wa",
        "servicio_sugerido": "catalogos"
    })

    # 2. Prospecto sin WhatsApp (solo teléfono fijo)
    p2 = db.save_or_update_negocio({
        "nombre": "Hotel Fijo",
        "municipio": "Puerto Escondido",
        "telefono": "+52 954 123 4567",
        "whatsapp": "",
        "whatsapp_estado": "SIN_WHATSAPP_COMPROBABLE",
        "tipo_canal_principal": "telefono",
        "servicio_sugerido": "web"
    })

    metrics = db.get_dashboard_metrics()
    assert metrics["prospectos_investigados"] == 2
    assert metrics["con_whatsapp_comprobado"] == 1
    assert metrics["otros_canales"] == 1

    detail1 = db.get_negocio_detail(p1["id"])
    assert detail1["whatsapp"] == "529541240793"
    assert detail1["whatsapp_estado"] == "WHATSAPP_COMPROBADO"
    assert detail1["servicio_sugerido"] == "catalogos"


def test_contact_confirmation_required_for_contacted_status(isolated_sqlite_db):
    """Verifica que el estado contactado solo se marque con confirmación humana explícita."""
    p = db.save_or_update_negocio({
        "nombre": "Hotel Test",
        "municipio": "Mazunte",
        "whatsapp": "529541240793"
    })
    negocio_id = p["id"]

    detail_before = db.get_negocio_detail(negocio_id)
    assert detail_before["estado_comercial"] != "contactado"
    assert detail_before["fecha_contacto_confirmada"] is None

    # Confirmación humana
    db.record_human_contact(negocio_id, "whatsapp", "Mensaje enviado a recepción")

    detail_after = db.get_negocio_detail(negocio_id)
    assert detail_after["estado_comercial"] == "contactado"
    assert detail_after["fecha_contacto_confirmada"] is not None


def test_copilot_pending_whatsapp_does_not_assert_direct_wa():
    """Verifica que un negocio con WhatsApp pendiente NUNCA afirme que atienden por WhatsApp."""
    prospect_pendiente = {
        "id": 29,
        "nombre": "Hotel El Alquimista Yoga Spa",
        "web": "https://elalquimistahotel.mx/contacto/",
        "telefono": "+52 958 587 8961",
        "whatsapp": "529585878961",
        "whatsapp_estado": "WHATSAPP_PENDIENTE_VERIFICACION",
        "fuente_whatsapp": "subpagina_contacto",
        "servicio_sugerido": "flyers"
    }

    res = copilot.generate_cidiks_messages(prospect_pendiente)
    msg = res["mensaje_personalizado"]

    # No debe afirmar que atienden por WhatsApp
    assert "atienden consultas directas por WhatsApp" not in msg
    assert "cuentan con enlace directo de WhatsApp" not in msg
    # Debe reflejar con prudencia los datos encontrados
    assert "encontré su teléfono de atención" in msg or "Revisé la sección de contacto" in msg
    # La pregunta debe ser exploratoria y no dar por sentado WhatsApp
    assert res["pregunta_comercial"] != ""


def test_dashboard_metrics_five_way_separation(isolated_sqlite_db):
    """Verifica la separación rigurosa de las 5 métricas comerciales en el dashboard."""
    # 1. Prospecto comprobado y no contactado (oportunidad revisable 1)
    p1 = db.save_or_update_negocio({
        "nombre": "Hotel Alfa",
        "municipio": "Puerto Escondido",
        "whatsapp": "529541240793",
        "whatsapp_estado": "WHATSAPP_COMPROBADO",
        "servicio_sugerido": "catalogos"
    })
    # 2. Prospecto comprobado y YA contactado manualmente
    p2 = db.save_or_update_negocio({
        "nombre": "Hotel Beta",
        "municipio": "Puerto Escondido",
        "whatsapp": "529541112233",
        "whatsapp_estado": "WHATSAPP_COMPROBADO",
        "servicio_sugerido": "catalogos"
    })
    db.record_human_contact(p2["id"], "whatsapp", "Envío manual confirmado", fecha_contacto="2026-11-01T18:40:00")

    # 3. Prospecto con WhatsApp pendiente (oportunidad revisable 2)
    p3 = db.save_or_update_negocio({
        "nombre": "Hotel Gamma",
        "municipio": "Mazunte",
        "telefono": "+52 958 123 4567",
        "whatsapp": "529581234567",
        "whatsapp_estado": "WHATSAPP_PENDIENTE_VERIFICACION",
        "servicio_sugerido": "flyers"
    })
    # 4. Prospecto bloqueado como NO_CONTACTAR (no debe ser revisable)
    p4 = db.save_or_update_negocio({
        "nombre": "Directorio Falso",
        "municipio": "Oaxaca",
        "servicio_sugerido": "no_contactar",
        "identidad_verificada": 0
    })

    metrics = db.get_dashboard_metrics()
    assert metrics["negocios_descubiertos"] == 4
    assert metrics["con_whatsapp_comprobado"] == 2
    assert metrics["con_whatsapp_pendiente"] == 1
    assert metrics["contactos_confirmados"] == 1
    # De 4 negocios: 1 contactado, 1 bloqueado -> Oportunidades revisables = 2
    assert metrics["oportunidades_revisables"] == 2


def test_backend_prevents_contacting_blocked_prospects(isolated_sqlite_db):
    """Verifica que el backend impida marcar 'contactado' a prospectos bloqueados sin justificación."""
    p_blocked = db.save_or_update_negocio({
        "nombre": "Negocio Incierto",
        "municipio": "Puerto Escondido",
        "servicio_sugerido": "no_contactar",
        "identidad_verificada": 0
    })
    nid = p_blocked["id"]

    # Intentar eludir mediante save_or_update_negocio
    db.save_or_update_negocio({"id": nid, "estado_comercial": "contactado"})
    det = db.get_negocio_detail(nid)
    assert det["estado_comercial"] != "contactado"

    # Intentar record_human_contact sin notas de justificación debe lanzar excepción
    with pytest.raises(ValueError, match="está bloqueado"):
        db.record_human_contact(nid, "whatsapp", notas="")

    # Con nota explícita de hecho histórico se permite registrar la actividad
    db.record_human_contact(nid, "whatsapp", notas="Hecho histórico verificado en auditoría anterior")
    det_after = db.get_negocio_detail(nid)
    assert det_after["estado_comercial"] == "contactado"

