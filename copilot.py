"""
Copiloto ético CÍDIKS — Generador de conversaciones comerciales verificables (WhatsApp-first)
Diseñado para turismo y hospedaje en la Costa de Oaxaca.
Reglas:
1. Bloquea mensajes listos para enviar cuando la identidad comercial no está verificada.
2. Diversifica la orientación de servicios según la evidencia real del negocio (no ofrece catálogos a todos).
3. Separa explícitamente: Observación verificada, Hipótesis comercial y Pregunta exploratoria.
4. Elimina cumplidos genéricos no sustentados.
5. Adapta las preguntas al negocio, al canal disponible (WhatsApp vs. Teléfono/Correo/Redes) y a la capacidad CÍDIKS.
6. Permite recomendar «Investigar más» o «No contactar todavía» cuando falta contexto o hay desalineación.
"""
import re
import json
import hashlib
from urllib.parse import urlparse
from config import GEMINI_API_KEY

CIDIKS_CAPACIDADES = {
    "catalogos": {
        "nombre": "Catálogos digitales para WhatsApp",
        "descripcion": "catálogos digitales y fichas ligeras de habitaciones y tarifas para responder consultas en WhatsApp"
    },
    "web": {
        "nombre": "Presencia web con reserva directa",
        "descripcion": "páginas web rápidas conectadas a WhatsApp para facilitar consultas y reservaciones directas"
    },
    "flyers": {
        "nombre": "Flyers y promociones de temporada",
        "descripcion": "diseño de promociones, paquetes de temporada y piezas visuales para estados de WhatsApp y redes"
    },
    "redes_sociales": {
        "nombre": "Contenido digital y redes sociales",
        "descripcion": "organización visual de perfiles en Instagram y Facebook orientados a convertir visitas en consultas directas"
    },
    "diseno": {
        "nombre": "Diseño gráfico comercial",
        "descripcion": "diseño de menús, guías para huéspedes, mapas locales y materiales de presentación del hospedaje"
    },
    "investigar_mas": {
        "nombre": "Investigar más antes de contactar",
        "descripcion": "Requiere identificar primero al tomador de decisiones o validar el modelo operativo antes de escribir."
    },
    "no_contactar": {
        "nombre": "No contactar todavía",
        "descripcion": "Identidad comercial o canales de contacto no verificados en fuentes públicas."
    }
}

INVALID_URL_MARKERS = (
    ".pdf", "pdfjsviewer", "/plugins/generic/", "viewer.html", "jmcs.org.mx",
    "localhost", "127.0.0.1"
)

CORPORATE_LUXURY_MARKERS = (
    "hotelescondido.com", "grupohabita", "fourseasons", "banyantree", "camino real",
    "fiesta americana", "marriott", "hilton", "hyatt"
)


def clean_business_name(raw_nombre: str) -> str:
    if not raw_nombre:
        return "Equipo"
    nombre = re.split(r"[\-|•–|:]", raw_nombre)[0].strip()
    if len(nombre) < 3:
        nombre = raw_nombre.strip()
    return nombre


def extract_domain_clean(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def verify_commercial_identity(prospect: dict) -> tuple[bool, str]:
    """
    Determina si la identidad comercial del negocio está suficientemente verificada
    para permitir generar un borrador comercial.
    Retorna (identidad_verificada: bool, motivo: str).
    """
    if prospect.get("identidad_verificada") is False or prospect.get("identidad_verificada") == 0:
        return False, "Marcado manualmente como identidad no verificada."

    web = (prospect.get("web") or prospect.get("Web") or "").strip()
    web_lower = web.lower()
    wa = (prospect.get("whatsapp") or prospect.get("WhatsApp") or "").strip()
    tel = (prospect.get("telefono") or prospect.get("Teléfono") or "").strip()
    email = (prospect.get("email") or prospect.get("Email") or "").strip()
    redes = (prospect.get("redes_sociales") or prospect.get("Redes sociales") or "").strip()
    nombre = (prospect.get("nombre") or prospect.get("Nombre del negocio") or "").strip()

    # 1. URL corrupta, visor de PDF o artículo académico
    if web and any(m in web_lower for m in INVALID_URL_MARKERS):
        return False, f"El enlace registrado ({extract_domain_clean(web) or web[:40]}) corresponde a un visor de documentos o sitio ajeno al giro hotelero, y no cuenta con canales verificados."

    # 2. Sin nombre válido
    if not nombre or nombre.lower() in ("sin nombre", "desconocido", "test"):
        return False, "Nombre comercial ausente o inválido."

    # 3. Sin sitio web válido Y sin ningún canal de contacto comprobable
    if not web and not wa and not tel and not email and not redes:
        return False, "No cuenta con sitio web oficial ni ningún canal público verificable (WhatsApp, teléfono, correo o redes)."

    return True, "Identidad respaldada por fuente pública."


def needs_more_investigation(prospect: dict) -> tuple[bool, str]:
    """
    Detecta si un negocio verificado requiere más investigación antes de contactar en frío
    (ej. hoteles corporativos/de lujo de grupo sin canal directo, o sitios web sin ningún canal extraído).
    """
    web = (prospect.get("web") or prospect.get("Web") or "").strip().lower()
    nombre = (prospect.get("nombre") or prospect.get("Nombre del negocio") or "").strip().lower()
    wa = (prospect.get("whatsapp") or prospect.get("WhatsApp") or "").strip()
    tel = (prospect.get("telefono") or prospect.get("Teléfono") or "").strip()
    email = (prospect.get("email") or prospect.get("Email") or "").strip()
    redes = (prospect.get("redes_sociales") or prospect.get("Redes sociales") or "").strip()

    if any(m in web or m in nombre for m in CORPORATE_LUXURY_MARKERS) and not wa:
        return True, "Propiedad perteneciente a grupo hotelero o segmento de lujo con reservas centralizadas y sin WhatsApp público."

    # Tiene sitio web pero no se encontró WhatsApp, ni teléfono, ni correo, ni redes sociales
    if web and not wa and not tel and not email and not redes:
        return True, "Sitio web activo, pero sin WhatsApp, teléfono directo ni correo publicados (solo formulario cerrado o sin datos visibles)."

    return False, ""


def select_suggested_service(prospect: dict, honor_explicit: bool = True) -> str:
    """
    Selecciona una capacidad CÍDIKS diferenciada según la evidencia real del negocio.
    No asigna automáticamente 'catalogos' a todos los hospedajes.
    """
    is_verified, _ = verify_commercial_identity(prospect)
    if not is_verified:
        return "no_contactar"

    explicit = prospect.get("servicio_sugerido")
    if honor_explicit and explicit in ("no_contactar", "investigar_mas"):
        return explicit

    investigate, _ = needs_more_investigation(prospect)
    if investigate and not (honor_explicit and explicit in ("catalogos", "web", "flyers", "redes_sociales", "diseno") and prospect.get("_force_explicit")):
        return "investigar_mas"

    if honor_explicit and prospect.get("_force_explicit") and explicit in CIDIKS_CAPACIDADES:
        return explicit

    web = (prospect.get("web") or prospect.get("Web") or "").strip()
    wa = (prospect.get("whatsapp") or prospect.get("WhatsApp") or "").strip()
    wa_estado = (prospect.get("whatsapp_estado") or "").strip()
    has_wa = bool(wa) or wa_estado in ("WHATSAPP_COMPROBADO", "confirmado", "WHATSAPP_PENDIENTE_VERIFICACION")
    tel = (prospect.get("telefono") or prospect.get("Teléfono") or "").strip()
    email = (prospect.get("email") or prospect.get("Email") or "").strip()
    redes = (prospect.get("redes_sociales") or prospect.get("Redes sociales") or "").strip()
    nombre_lower = (prospect.get("nombre") or prospect.get("Nombre del negocio") or "").lower()
    problemas_lower = (prospect.get("problemas_detectados") or prospect.get("Problemas detectados") or "").lower()

    # Caso 1: Sin sitio web o sitio inaccesible -> Presencia web con reserva directa
    if not web or "inaccesible" in problemas_lower or "sin sitio web" in problemas_lower:
        return "web"

    # Caso 2: Con sitio web, pero SIN WhatsApp comprobable (solo teléfono, correo o redes)
    if not has_wa:
        if redes or any(k in nombre_lower for k in ("surf", "rockaway", "zicatela", "hostal", "beach", "playa", "camp")):
            return "redes_sociales"
        return "web"

    # Caso 3: Con WhatsApp comprobable -> diversificar según el tipo de hospedaje/operación
    # 3a. Hoteles grandes, resorts, villas o posadas familiares consolidadas (con teléfono fijo, correo y web completa)
    if any(k in nombre_lower for k in ("posada real", "resort", "villas", "suites", "club", "plaza", "aldeas")):
        return "flyers"

    # 3b. Tours, experiencias, surf camps o agencias
    if any(k in nombre_lower for k in ("tour", "surf", "experiencia", "viaje", "aventura", "mezcal", "ecoturismo")):
        return "flyers"

    # 3c. Restaurantes, clubes de playa, eco-hoteles o negocios con gastronomía/servicios complementarios
    if any(k in nombre_lower for k in ("restaurante", "cafe", "café", "palapa", "eco", "bistro", "bar", "mirador")):
        return "diseno"

    # 3d. Cabañas, glamping, hostales o casas de playa con presencia social
    if any(k in nombre_lower for k in ("cabaña", "cabana", "bungalow", "hostal", "hostel", "glamping")) and redes:
        return "redes_sociales"

    # 3e. Hoteles boutique, casas de huéspedes o posadas donde WhatsApp es la recepción directa
    if any(k in nombre_lower for k in ("boutique", "raíz", "raiz", "casa", "hotel", "hospedaje", "posada")):
        if tel and email and redes and "boutique" not in nombre_lower and "raíz" not in nombre_lower and "raiz" not in nombre_lower:
            return "diseno"
        return "catalogos"

    return "catalogos"


def infer_specific_locality(prospect: dict) -> str:
    """Extrae la localidad específica real a partir de los datos del prospecto sin inventar."""
    raw_loc = (prospect.get("municipio") or prospect.get("Ubicación") or "").strip()
    nombre = (prospect.get("nombre") or prospect.get("Nombre del negocio") or "").lower()
    web = (prospect.get("web") or prospect.get("Web") or "").lower()
    combined = f"{raw_loc.lower()} {nombre} {web}"

    if "zicatela" in combined:
        return "Playa Zicatela, Puerto Escondido"
    if "bacocho" in combined:
        return "Playa Bacocho, Puerto Escondido"
    if "carrizalillo" in combined:
        return "Carrizalillo, Puerto Escondido"
    if "chahué" in combined or "chahue" in combined or "santa cruz" in combined or "huatulco" in combined:
        return "Bahías de Huatulco"
    if "mazunte" in combined:
        return "Mazunte, Oaxaca"
    if "zipolite" in combined:
        return "Zipolite, Oaxaca"
    if "san agustinillo" in combined or "agustinillo" in combined:
        return "San Agustinillo, Oaxaca"
    if "puerto angel" in combined or "puerto ángel" in combined:
        return "Puerto Ángel, Oaxaca"
    if "puerto escondido" in combined or "puertoescondido" in combined or "pxm" in combined:
        return "Puerto Escondido"
    if raw_loc and raw_loc.lower() not in ("", "costa de oaxaca"):
        return raw_loc
    return "la Costa de Oaxaca"


def build_verified_observation(prospect: dict, evidencias: list = None) -> str:
    """
    Construye la observación estrictamente verificada a partir de hechos reales
    (dominio web, estado de WhatsApp, teléfono, correo, redes y evidencia visual si existe).
    """
    is_verified, reason = verify_commercial_identity(prospect)
    if not is_verified:
        return f"Identidad no verificada: {reason}"

    web = (prospect.get("web") or prospect.get("Web") or "").strip()
    domain = extract_domain_clean(web)
    wa = (prospect.get("whatsapp") or prospect.get("WhatsApp") or "").strip()
    wa_estado = (prospect.get("whatsapp_estado") or "").strip()
    fuente_wa = (prospect.get("fuente_whatsapp") or "").strip()
    tel = (prospect.get("telefono") or prospect.get("Teléfono") or "").strip()
    email = (prospect.get("email") or prospect.get("Email") or "").strip()
    redes = (prospect.get("redes_sociales") or prospect.get("Redes sociales") or "").strip()

    parts = []
    if domain:
        parts.append(f"Sitio web oficial activo ({domain})")
    else:
        parts.append("Sin sitio web propio registrado")

    if wa and wa_estado in ("WHATSAPP_COMPROBADO", "confirmado"):
        src_label = f" vía {fuente_wa}" if fuente_wa else " en su sitio oficial"
        parts.append(f"WhatsApp público comprobado (+{wa}){src_label}")
    elif wa_estado in ("WHATSAPP_PENDIENTE_VERIFICACION", "declarado"):
        parts.append(f"mención de WhatsApp pendiente de verificar ({wa or 'sin enlace wa.me directo'})")
    else:
        parts.append("sin enlace directo de WhatsApp en su web")

    other_channels = []
    if tel:
        other_channels.append(f"teléfono ({tel.split(',')[0].strip()})")
    if email:
        other_channels.append(f"correo ({email.split(',')[0].strip()})")
    if redes:
        other_channels.append("perfiles en redes sociales")

    if other_channels:
        parts.append("publica " + ", ".join(other_channels))
    elif not wa:
        parts.append("únicamente dispone de formulario web general")

    verificadas = [ev for ev in (evidencias or []) if ev.get("estado_comprobacion") == "VERIFICADA_VISIBLE"]
    if verificadas and verificadas[0].get("elemento_observado"):
        parts.append(f"evidencia visual comprobada: {verificadas[0]['elemento_observado']}")

    obs = "; ".join(parts)
    return obs[0].upper() + obs[1:] + "."


def build_commercial_hypothesis(prospect: dict, servicio_key: str) -> str:
    """
    Formula la hipótesis comercial explícita (nunca afirmada como falla técnica)
    conectando los canales observados con la capacidad seleccionada de CÍDIKS.
    """
    if servicio_key == "no_contactar":
        return "Sin fuente pública legítima confirmada; no debe iniciarse contacto comercial."
    if servicio_key == "investigar_mas":
        _, reason = needs_more_investigation(prospect)
        return reason or "Estructura operativa sin contacto directo de recepción; conviene identificar primero al encargado de comercialización."

    wa = (prospect.get("whatsapp") or prospect.get("WhatsApp") or "").strip()
    wa_estado = (prospect.get("whatsapp_estado") or "").strip()
    is_wa_comprobado = bool(wa) and wa_estado in ("WHATSAPP_COMPROBADO", "confirmado")
    is_wa_pendiente = wa_estado in ("WHATSAPP_PENDIENTE_VERIFICACION", "declarado")
    web = (prospect.get("web") or prospect.get("Web") or "").strip()

    if servicio_key == "catalogos":
        if is_wa_comprobado:
            return "Hipótesis: Al atender reservaciones directas por WhatsApp, contar con un catálogo o ficha digital ligera de habitaciones y tarifas puede agilizar la respuesta a viajeros."
        elif is_wa_pendiente:
            return "Hipótesis: Su sitio publica un teléfono en contacto; si reciben consultas por mensaje, una ficha digital facilitaría responder tarifas sin depender de llamadas."
        return "Hipótesis: Si reciben consultas de hospedaje por mensaje o teléfono, una ficha digital de habitaciones facilitaría compartir tarifas y disponibilidad."
    elif servicio_key == "flyers":
        if is_wa_comprobado:
            return "Hipótesis: Como hospedaje activo con WhatsApp directo, podrían requerir piezas visuales y flyers de paquetes para promocionar puentes y temporadas en la costa."
        return "Hipótesis: Al mantener canales de recepción y correo activos, podrían aprovechar piezas visuales y flyers para difundir paquetes de temporada en medios digitales."
    elif servicio_key == "redes_sociales":
        if not is_wa_comprobado:
            return "Hipótesis: Su sitio web muestra teléfono y redes sociales pero no botón directo de WhatsApp; es probable que gran parte de las dudas de viajeros entren por Instagram o Facebook."
        return "Hipótesis: Podrían fortalecer la conversión de visitantes en Instagram y Facebook hacia su WhatsApp de reservaciones mediante contenido visual estructurado."
    elif servicio_key == "web":
        if not web:
            return "Hipótesis: Al no contar con sitio web oficial visible, dependen de redes o buscadores externos; una página ligera conectada a WhatsApp facilitaría reservas directas sin comisiones."
        return "Hipótesis: Su sitio web actual no muestra un acceso directo a WhatsApp; integrar una vía rápida de consulta móvil podría facilitar el contacto directo con viajeros."
    elif servicio_key == "diseno":
        return "Hipótesis: Por su perfil de hospedaje, podrían aprovechar diseño gráfico comercial actualizado (guía digital para huéspedes, menús o fichas de servicios complementarios)."
    return "Hipótesis exploratoria sujeta a validación con el negocio."


def build_adapted_question(prospect: dict, servicio_key: str) -> str:
    """
    Construye una pregunta exploratoria adaptada al negocio, al canal realmente disponible
    y a la capacidad CÍDIKS seleccionada.
    """
    if servicio_key in ("no_contactar", "investigar_mas"):
        return ""

    wa = (prospect.get("whatsapp") or prospect.get("WhatsApp") or "").strip()
    wa_estado = (prospect.get("whatsapp_estado") or "").strip()
    is_wa_comprobado = bool(wa) and wa_estado in ("WHATSAPP_COMPROBADO", "confirmado")
    is_wa_pendiente = wa_estado in ("WHATSAPP_PENDIENTE_VERIFICACION", "declarado")

    if servicio_key == "catalogos":
        if is_wa_comprobado:
            return "¿Actualmente comparten sus tipos de habitación y tarifas por WhatsApp mediante algún catálogo digital o los detallan en cada mensaje?"
        elif is_wa_pendiente:
            return "Revisé los datos de contacto en su sitio; ¿acostumbran compartir tarifas de habitación por WhatsApp o atienden principalmente por llamada y recepción?"
        return "¿Actualmente manejan algún número de WhatsApp con catálogo de habitaciones para enviar informes a quienes llaman o escriben?"

    if servicio_key == "flyers":
        if is_wa_comprobado:
            return "¿Suelen preparar flyers o paquetes promocionales para puentes y temporadas en la costa para compartir por WhatsApp y redes?"
        elif is_wa_pendiente:
            return "Revisé su sección de contacto; ¿suelen difundir promociones o paquetes de temporada para puentes en la costa mediante piezas digitales?"
        return "¿Manejan promociones de temporada o paquetes especiales en sus canales digitales durante el año?"

    if servicio_key == "redes_sociales":
        if not is_wa_comprobado:
            return "Revisé en su página su teléfono y redes sociales; ¿prefieren recibir las consultas de hospedaje por mensaje en redes o manejan también WhatsApp?"
        return "¿Actualmente las consultas de viajeros les llegan más desde sus redes sociales hacia WhatsApp o directo desde su sitio web?"

    if servicio_key == "web":
        if not is_wa_comprobado:
            return "¿Tienen previsto incorporar atención por WhatsApp en su página web o prefieren centralizar las reservaciones por teléfono y correo?"
        return "¿Les resulta práctico cómo su sitio actual dirige las consultas a WhatsApp o tienen planeado renovar la presentación de sus habitaciones?"

    if servicio_key == "diseno":
        return "¿Cuentan actualmente con guías digitales para huéspedes, menús o fichas de servicios actualizadas para esta temporada?"

    return "¿Qué canal les resulta hoy más práctico para atender las consultas directas de sus huéspedes?"


def generate_cidiks_messages(prospect: dict, evidencias: list = None, use_ai: bool = False, api_key: str = None) -> dict:
    """
    Genera borradores comerciales verificables, sin cumplidos genéricos y adaptados al negocio y canal.
    Si la identidad no está verificada o requiere investigación previa, bloquea el mensaje listo para enviar.
    """
    raw_nombre = prospect.get("nombre") or prospect.get("Nombre del negocio") or "Equipo"
    nombre = clean_business_name(raw_nombre)
    localidad = infer_specific_locality(prospect)

    is_verified, verif_reason = verify_commercial_identity(prospect)
    servicio_key = select_suggested_service(prospect, honor_explicit=True)
    capacidad = CIDIKS_CAPACIDADES.get(servicio_key, CIDIKS_CAPACIDADES["catalogos"])

    observacion = build_verified_observation(prospect, evidencias)
    hipotesis = build_commercial_hypothesis(prospect, servicio_key)
    pregunta = build_adapted_question(prospect, servicio_key)

    checks = prospect.get("checks") or {}
    if isinstance(checks, str):
        try:
            checks = json.loads(checks)
        except Exception:
            checks = {}
    verificadas = [ev for ev in (evidencias or []) if ev.get("estado_comprobacion") == "VERIFICADA_VISIBLE"]
    has_verified_issue = len(verificadas) > 0 or (checks and (checks.get("responsive") is False or checks.get("whatsapp") is False))
    modalidad = "A_PROBLEMA_VERIFICADO" if has_verified_issue else "B_OPORTUNIDAD_EXPLORATORIA"

    # =========================================================================
    # BLOQUEO DE SEGURIDAD COMERCIAL: Identidad no verificada o Investigar más
    # =========================================================================
    if not is_verified or servicio_key == "no_contactar":
        blocked_msg = (
            f"[BLOQUEADO — NO CONTACTAR TODAVÍA]\n"
            f"Motivo: {verif_reason}\n"
            f"Acción recomendada: Verificar primero que {nombre} opere activamente y confirmar un canal oficial antes de redactar un mensaje."
        )
        return {
            "identidad_verificada": False,
            "bloqueado_envio": True,
            "modalidad": modalidad,
            "tipo_observacion": "IDENTIDAD_NO_VERIFICADA",
            "servicio_sugerido": "no_contactar",
            "servicio_nombre": CIDIKS_CAPACIDADES["no_contactar"]["nombre"],
            "observacion_verificada": observacion,
            "hipotesis_comercial": hipotesis,
            "pregunta_comercial": "",
            "mensaje_personalizado": blocked_msg,
            "mensaje_calido": blocked_msg,
            "mensaje_seguimiento": blocked_msg,
            "evidencia_origen": observacion
        }

    if servicio_key == "investigar_mas":
        inv_msg = (
            f"[RECOMENDACIÓN: INVESTIGAR MÁS ANTES DE CONTACTAR]\n"
            f"Observación: {observacion}\n"
            f"Nota comercial: {hipotesis}\n"
            f"Si decides contactar a {nombre}, selecciona manualmente una capacidad específica de CÍDIKS en el selector superior."
        )
        return {
            "identidad_verificada": True,
            "bloqueado_envio": True,
            "modalidad": modalidad,
            "tipo_observacion": "REQUIERE_INVESTIGACION",
            "servicio_sugerido": "investigar_mas",
            "servicio_nombre": CIDIKS_CAPACIDADES["investigar_mas"]["nombre"],
            "observacion_verificada": observacion,
            "hipotesis_comercial": hipotesis,
            "pregunta_comercial": "",
            "mensaje_personalizado": inv_msg,
            "mensaje_calido": inv_msg,
            "mensaje_seguimiento": inv_msg,
            "evidencia_origen": observacion
        }

    # =========================================================================
    # REDACCIÓN CONVERSACIONAL SOBRIA (Sin cumplidos genéricos no sustentados)
    # =========================================================================
    web = (prospect.get("web") or prospect.get("Web") or "").strip()
    domain = extract_domain_clean(web)
    wa = (prospect.get("whatsapp") or prospect.get("WhatsApp") or "").strip()
    wa_estado = (prospect.get("whatsapp_estado") or "").strip()
    is_wa_comprobado = bool(wa) and wa_estado in ("WHATSAPP_COMPROBADO", "confirmado")
    is_wa_pendiente = wa_estado in ("WHATSAPP_PENDIENTE_VERIFICACION", "declarado")
    tel = (prospect.get("telefono") or prospect.get("Teléfono") or "").strip()

    # Contexto concreto basado en la fuente pública real consultada (cero halagos y sin ambigüedad de visitas físicas)
    if domain and is_wa_comprobado:
        hecho_apertura = f"Revisé la página oficial de {nombre} ({domain}) en {localidad} y vi que cuentan con enlace directo de WhatsApp para reservaciones."
    elif domain and is_wa_pendiente:
        hecho_apertura = f"Revisé la sección de contacto en la página de {nombre} ({domain}) en {localidad}, donde encontré su teléfono de atención (+{wa}) y correo."
    elif domain and tel:
        hecho_apertura = f"Revisé la página oficial de {nombre} ({domain}) en {localidad}, donde publican su teléfono (+{tel.split(',')[0].strip()}) y canales de contacto."
    elif domain:
        hecho_apertura = f"Revisé la página oficial de {nombre} ({domain}) en {localidad}."
    elif is_wa_comprobado:
        hecho_apertura = f"Ubicamos el WhatsApp oficial de {nombre} en {localidad} a través de sus canales públicos de atención."
    elif is_wa_pendiente or tel:
        hecho_apertura = f"Ubicamos los datos de contacto de {nombre} en {localidad} a través de sus canales públicos."
    else:
        hecho_apertura = f"Consultamos la información pública de {nombre} en {localidad}."

    negocio_id = prospect.get("id") or int(hashlib.md5(nombre.encode("utf-8")).hexdigest(), 16) % 100
    estilo_idx = negocio_id % 3

    if estilo_idx == 0:
        msg_frio = (
            f"Hola, buen día al equipo de {nombre}. Les saludo desde CÍDIKS en Oaxaca.\n\n"
            f"{hecho_apertura} En CÍDIKS colaboramos con hospedajes de la costa en {capacidad['descripcion']}.\n\n"
            f"{pregunta}"
        )
    elif estilo_idx == 1:
        msg_frio = (
            f"Hola, equipo de {nombre}. Les escribo de CÍDIKS aquí en Oaxaca.\n\n"
            f"{hecho_apertura} Apoyamos a hoteles y proyectos turísticos locales con {capacidad['descripcion']}.\n\n"
            f"{pregunta}"
        )
    else:
        msg_frio = (
            f"Buen día al equipo de {nombre}, les saludo de CÍDIKS en Oaxaca.\n\n"
            f"{hecho_apertura} Trabajamos con negocios de hospedaje en la región desarrollando {capacidad['descripcion']}.\n\n"
            f"{pregunta}"
        )

    msg_calido = (
        f"Hola, equipo de {nombre}, buen día desde CÍDIKS en Oaxaca.\n\n"
        f"{hecho_apertura} Desarrollamos {capacidad['descripcion']} para negocios turísticos de la costa.\n\n"
        f"{pregunta}"
    )

    msg_seg = (
        f"Hola de nuevo al equipo de {nombre}, espero que vaya muy bien la semana en {localidad}.\n\n"
        f"Les escribí hace unos días respecto a {capacidad['nombre'].lower()}. "
        f"Si en este momento tienen cubierto el tema no hay ningún inconveniente; quedo a la orden si más adelante desean revisar algún ejemplo."
    )

    return {
        "identidad_verificada": True,
        "bloqueado_envio": False,
        "modalidad": modalidad,
        "tipo_observacion": "OBSERVACION_COMPROBADA" if len(verificadas) > 0 else "HIPOTESIS_COMERCIAL",
        "servicio_sugerido": servicio_key,
        "servicio_nombre": capacidad["nombre"],
        "observacion_verificada": observacion,
        "hipotesis_comercial": hipotesis,
        "pregunta_comercial": pregunta,
        "mensaje_personalizado": msg_frio.strip(),
        "mensaje_calido": msg_calido.strip(),
        "mensaje_seguimiento": msg_seg.strip(),
        "evidencia_origen": observacion
    }
