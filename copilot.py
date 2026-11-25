"""
Copiloto ético CÍDIKS — Generador de conversaciones comerciales verificables (WhatsApp-first).

CÍDIKS es un proyecto de digitalización integral (web, marketing, CRM, automatizaciones,
inteligencia artificial y consultoría). Las capacidades, los giros comerciales, las preguntas y
las plantillas viven en docs/reglas/sabueso_reglas.json (compartido con Sabueso Móvil).

Reglas:
1. Bloquea mensajes listos para enviar cuando la identidad comercial no está verificada.
2. Una discrepancia de identidad (nombre vs sitio, giro, contacto compartido) pide REVISIÓN
   HUMANA antes de generar el mensaje; no invalida al prospecto (validacion.py).
3. La solución se decide en este orden: necesidad confirmada por el prospecto > elección humana
   > reglas del giro. El giro del negocio manda sobre las palabras sueltas de su nombre.
4. Mensajes iniciales cortos (objetivo 80–180 caracteres) con una sola pregunta.
5. Separa explícitamente: Observación verificada, Hipótesis comercial y Pregunta exploratoria.
6. 100 % determinista: consumo de tokens de IA = 0. `use_ai`/`api_key` se aceptan solo por
   compatibilidad y se ignoran a propósito.
"""
import json

import conversacion
import reglas as R
import validacion

# Compatibilidad: ahora viven en las reglas compartidas (identidad.marcadores_*).
INVALID_URL_MARKERS = tuple(R.cargar_reglas()["identidad"]["marcadores_url_invalida"])
CORPORATE_LUXURY_MARKERS = tuple(R.cargar_reglas()["identidad"]["marcadores_corporativos"])

_ESPECIALES = {
    "investigar_mas": {
        "nombre": "Investigar más antes de contactar",
        "descripcion": "Requiere identificar primero al tomador de decisiones o validar el modelo operativo antes de escribir."
    },
    "no_contactar": {
        "nombre": "No contactar todavía",
        "descripcion": "Identidad comercial o canales de contacto no verificados en fuentes públicas."
    },
}


def _capacidades() -> dict:
    caps = {sid: {"nombre": s["nombre"], "descripcion": s["hipotesis"]} for sid, s in R.cargar_reglas()["servicios"].items()}
    caps.update(_ESPECIALES)
    return caps


# Compatibilidad: diccionario de capacidades (se construye desde las reglas).
CIDIKS_CAPACIDADES = _capacidades()


def clean_business_name(raw_nombre: str) -> str:
    import re
    if not raw_nombre:
        return "Equipo"
    nombre = re.split(r"[\-|•–|:]", raw_nombre)[0].strip()
    if len(nombre) < 3:
        nombre = raw_nombre.strip()
    return nombre


def extract_domain_clean(url: str) -> str:
    return validacion.dominio_de(url)


def verify_commercial_identity(prospect: dict) -> tuple:
    """
    Determina si la identidad comercial del negocio está suficientemente verificada
    para permitir generar un borrador comercial. Retorna (identidad_verificada, motivo).
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

    if web and any(m in web_lower for m in R.cargar_reglas()["identidad"]["marcadores_url_invalida"]):
        return False, f"El enlace registrado ({extract_domain_clean(web) or web[:40]}) corresponde a un visor de documentos o sitio ajeno al negocio, y no cuenta con canales verificados."

    if not nombre or nombre.lower() in ("sin nombre", "desconocido", "test"):
        return False, "Nombre comercial ausente o inválido."

    if not web and not wa and not tel and not email and not redes:
        return False, "No cuenta con sitio web oficial ni ningún canal público verificable (WhatsApp, teléfono, correo o redes)."

    return True, "Identidad respaldada por fuente pública."


def needs_more_investigation(prospect: dict) -> tuple:
    """
    Detecta si un negocio verificado requiere más investigación antes de contactar en frío
    (ej. grupos corporativos sin canal directo, o sitios web sin ningún canal extraído).
    """
    web = (prospect.get("web") or prospect.get("Web") or "").strip().lower()
    nombre = (prospect.get("nombre") or prospect.get("Nombre del negocio") or "").strip().lower()
    wa = (prospect.get("whatsapp") or prospect.get("WhatsApp") or "").strip()
    tel = (prospect.get("telefono") or prospect.get("Teléfono") or "").strip()
    email = (prospect.get("email") or prospect.get("Email") or "").strip()
    redes = (prospect.get("redes_sociales") or prospect.get("Redes sociales") or "").strip()

    if any(m in web or m in nombre for m in R.cargar_reglas()["identidad"]["marcadores_corporativos"]) and not wa:
        return True, "Propiedad perteneciente a grupo corporativo o segmento de lujo con atención centralizada y sin WhatsApp público."

    if web and not wa and not tel and not email and not redes:
        return True, "Sitio web activo, pero sin WhatsApp, teléfono directo ni correo publicados (solo formulario cerrado o sin datos visibles)."

    return False, ""


def _seleccionar_servicio(prospect: dict, honor_explicit: bool = True) -> tuple:
    """Devuelve (servicio, fuente). Fuente: necesidad_confirmada, eleccion_humana, reglas_sector…"""
    is_verified, _ = verify_commercial_identity(prospect)
    if not is_verified:
        return "no_contactar", "identidad_no_verificada"

    explicit = prospect.get("servicio_sugerido")
    if honor_explicit and explicit in ("no_contactar", "investigar_mas"):
        return explicit, "eleccion_humana"

    # La necesidad confirmada por el prospecto determina la solución.
    necesidad = (prospect.get("necesidad_expresada") or "").strip()
    if necesidad:
        por_necesidad = R.servicio_por_necesidad(necesidad)
        if por_necesidad:
            return por_necesidad, "necesidad_confirmada"

    # Memoria del prospecto: sus necesidades mandan; lo que rechazó o quiere conservar no se propone.
    memoria = conversacion.memoria_efectiva(prospect)
    if memoria["necesidades"]:
        return memoria["necesidades"][0], "necesidad_confirmada"
    excluidos = memoria["excluidos"]

    forzado = bool(honor_explicit and prospect.get("_force_explicit")
                   and explicit in R.servicios_validos() and explicit not in _ESPECIALES
                   and explicit not in excluidos)
    investigate, _ = needs_more_investigation(prospect)
    if investigate and not forzado:
        return "investigar_mas", "reglas"
    if forzado:
        return explicit, "eleccion_humana"

    sector = R.sector_de_prospecto(prospect)["sector"]
    return R.servicio_por_reglas(sector, prospect, excluidos), "reglas_sector"


def select_suggested_service(prospect: dict, honor_explicit: bool = True) -> str:
    """Selecciona la capacidad CÍDIKS según necesidad confirmada, elección humana o reglas del giro."""
    return _seleccionar_servicio(prospect, honor_explicit)[0]


def infer_specific_locality(prospect: dict) -> str:
    """Compatibilidad: localidad real o «la Costa de Oaxaca» si no hay dato (solo para textos internos)."""
    return R.localidad(prospect) or "la Costa de Oaxaca"


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


def _sector_para_redactar(prospect: dict, identidad: dict) -> dict:
    """Con una discrepancia de giro sin revisar se usa el giro general (neutral) para no suponer."""
    info = R.sector_de_prospecto(prospect)
    if info["conflicto"] and not identidad.get("confirmada_por_humano"):
        return R.cargar_reglas()["sector_general"]
    return info["sector"]


def build_commercial_hypothesis(prospect: dict, servicio_key: str, sector: dict = None, fuente: str = "") -> str:
    """Hipótesis explícita (nunca afirmada como falla). La necesidad confirmada no es hipótesis."""
    if servicio_key == "no_contactar":
        return "Sin fuente pública legítima confirmada; no debe iniciarse contacto comercial."
    if servicio_key == "investigar_mas":
        _, reason = needs_more_investigation(prospect)
        return reason or "Estructura operativa sin contacto directo; conviene identificar primero al encargado."
    r = R.cargar_reglas()
    servicio = r["servicios"].get(servicio_key)
    necesidad = (prospect.get("necesidad_expresada") or "").strip()
    if fuente == "relacion_educativa":
        return "Conversación educativa: no es una oportunidad comercial. Se comparten recursos gratuitos."
    if fuente == "necesidad_confirmada" and servicio:
        if not necesidad:
            frases = [m["texto"] for m in conversacion.memoria_efectiva(prospect)["items"]
                      if m.get("tipo") == "necesidad" and m.get("servicio") == servicio_key]
            necesidad = frases[0] if frases else servicio["nombre"]
        return f"Necesidad confirmada por el negocio: «{necesidad}». Solución a conversar: {servicio['nombre']}."
    if necesidad:
        return f"Necesidad confirmada por el negocio: «{necesidad}». No se reconoció automáticamente la solución; revísala antes de proponer."
    sector = sector or R.sector_de_prospecto(prospect)["sector"]
    texto = sector.get("hipotesis", {}).get(servicio_key) or (servicio or {}).get("hipotesis")
    return f"Hipótesis: {texto}" if texto else "Hipótesis exploratoria sujeta a validación con el negocio."


def build_adapted_question(prospect: dict, servicio_key: str, sector: dict = None) -> str:
    """Una sola pregunta exploratoria, adaptada al giro, al servicio y al canal disponible."""
    if servicio_key in ("no_contactar", "investigar_mas"):
        return ""
    sector = sector or R.sector_de_prospecto(prospect)["sector"]
    return R.pregunta(sector, servicio_key, R.estado_contacto(servicio_key, R.senales(prospect)))


def _clave_hecho(s: dict) -> str:
    if s["web"] and s["wa_comprobado"]:
        return "web_whatsapp"
    if s["web"] and s["wa_pendiente"]:
        return "whatsapp_pendiente"
    if s["web"] and s["telefono"]:
        return "web_telefono"
    if s["web"]:
        return "web"
    if s["wa_comprobado"]:
        return "solo_whatsapp"
    return "sin_web"


def _fuente_alta(prospect: dict) -> str:
    """Dónde encontró la persona al negocio (altas manuales desde el celular: maps, facebook…)."""
    fuente = (prospect.get("fuente") or "").strip()
    if not fuente:
        desc = (prospect.get("fuente_descubrimiento") or "").strip()
        fuente = desc[len("movil_"):] if desc.startswith("movil_") else ""
    return fuente


def indice_estilo(prospect: dict, total: int) -> int:
    """Variante de saludo estable por prospecto (misma regla en app.js)."""
    try:
        base = int(prospect.get("id"))
    except (TypeError, ValueError):
        base = sum(ord(c) for c in (prospect.get("nombre") or ""))
    return base % max(total, 1)


def componer_mensajes(prospect: dict, sector: dict, servicio_key: str, fuente: str) -> dict:
    """Arma frío, cálido y seguimiento con las plantillas de la modalidad (idéntico en app.js)."""
    r = R.cargar_reglas()
    mod = r["modalidades"][r["modalidad_predeterminada"]]
    obj_max = r["mensajes"]["objetivo_max"]
    servicio = r["servicios"][servicio_key]
    nombre = clean_business_name(prospect.get("nombre") or prospect.get("Nombre del negocio") or "Equipo")
    loc = R.localidad(prospect)
    plantilla_saludo = mod["saludos"][indice_estilo(prospect, len(mod["saludos"]))]
    saludo = R.rellenar(plantilla_saludo, nombre=nombre, en_localidad=f" en {loc}" if loc else "")
    saludo_corto = R.rellenar(plantilla_saludo, nombre=nombre, en_localidad="")

    def unir(partes):
        return " ".join(p for p in partes if p).strip()

    if fuente == "necesidad_confirmada":
        preg = mod["pregunta_con_necesidad"]
        cuerpo = R.rellenar(mod["con_necesidad"], servicio=servicio["nombre"])
        candidatos = [unir([saludo, cuerpo, preg]), unir([saludo_corto, cuerpo, preg])]
        frio = next((c for c in candidatos if len(c) <= obj_max), candidatos[-1])
    else:
        s = R.senales(prospect)
        preg = R.pregunta(sector, servicio_key, R.estado_contacto(servicio_key, s), r)
        fuente_alta = _fuente_alta(prospect)
        hecho = (mod.get("hechos_fuente", {}).get(fuente_alta) if fuente_alta else "") or mod["hechos"].get(_clave_hecho(s), "")
        # Para acortar se quita primero la ubicación y después el hecho observado (el hecho evita lo genérico).
        candidatos = [unir([saludo, mod["presentacion"], hecho, preg]),
                      unir([saludo_corto, mod["presentacion"], hecho, preg]),
                      unir([saludo, mod["presentacion"], preg]),
                      unir([saludo_corto, mod["presentacion"], preg])]
        frio = next((c for c in candidatos if len(c) <= obj_max), candidatos[-1])
    return {
        "pregunta": preg,
        "mensaje_personalizado": frio,
        "mensaje_calido": R.rellenar(mod["calido"], nombre=nombre, pregunta=preg).strip(),
        "mensaje_seguimiento": R.rellenar(mod["seguimiento"], nombre=nombre, tema=servicio["tema_seguimiento"]).strip(),
    }


def componer_educativo(prospect: dict, servicio_key: str) -> dict:
    """Relación educativa: saludo breve + un recurso gratuito pertinente. Nunca una propuesta comercial."""
    r = R.cargar_reglas()
    mod = r["modalidades"]["orientacion_educativa"]
    nombre = clean_business_name(prospect.get("nombre") or prospect.get("Nombre del negocio") or "Equipo")
    loc = R.localidad(prospect)
    plantilla = mod["saludos"][indice_estilo(prospect, len(mod["saludos"]))]
    saludo = R.rellenar(plantilla, nombre=nombre, en_localidad=f" en {loc}" if loc else "")
    recursos = conversacion.recursos_sugeridos("educativa", [servicio_key], prospect.get("_hoy"), maximo=1)
    if recursos:
        cuerpo = R.rellenar(mod["recurso"], recurso=f"{recursos[0]['titulo']} {recursos[0]['url']}")
        frio = " ".join([saludo, mod["presentacion"], cuerpo, mod["pregunta"]])
        preg = mod["pregunta"]
    else:
        preg = mod["pregunta_sin_recurso"]
        frio = " ".join([saludo, mod["presentacion"], preg])
    return {
        "pregunta": preg,
        "mensaje_personalizado": frio.strip(),
        "mensaje_calido": R.rellenar(mod["calido"], nombre=nombre, pregunta=preg).strip(),
        "mensaje_seguimiento": R.rellenar(mod["seguimiento"], nombre=nombre).strip(),
        "recursos": recursos,
    }


def generate_cidiks_messages(prospect: dict, evidencias: list = None, use_ai: bool = False,
                             api_key: str = None, contexto: list = None, indice: dict = None) -> dict:
    """
    Genera borradores comerciales verificables, cortos y adaptados al giro y al canal.
    `contexto`: otros prospectos (para detectar contactos compartidos y menciones a otros negocios).
    `use_ai` y `api_key` se ignoran: el copiloto es determinista (0 tokens).
    """
    r = R.cargar_reglas()
    raw_nombre = prospect.get("nombre") or prospect.get("Nombre del negocio") or "Equipo"
    nombre = clean_business_name(raw_nombre)

    is_verified, verif_reason = verify_commercial_identity(prospect)
    identidad = validacion.analizar_identidad(prospect, contexto, r, indice)
    sector = _sector_para_redactar(prospect, identidad)
    servicio_key, fuente = _seleccionar_servicio(prospect, honor_explicit=True)
    educativa = (prospect.get("tipo_relacion") or "") == "educativa" and servicio_key not in _ESPECIALES
    if educativa:
        fuente = "relacion_educativa"
    servicio_nombre = (r["servicios"].get(servicio_key) or _ESPECIALES.get(servicio_key) or {}).get("nombre", "")

    observacion = build_verified_observation(prospect, evidencias)
    hipotesis = build_commercial_hypothesis(prospect, servicio_key, sector, fuente)

    checks = prospect.get("checks") or {}
    if isinstance(checks, str):
        try:
            checks = json.loads(checks)
        except Exception:
            checks = {}
    verificadas = [ev for ev in (evidencias or []) if ev.get("estado_comprobacion") == "VERIFICADA_VISIBLE"]
    has_verified_issue = len(verificadas) > 0 or (checks and (checks.get("responsive") is False or checks.get("whatsapp") is False))
    modalidad = "A_PROBLEMA_VERIFICADO" if has_verified_issue else "B_OPORTUNIDAD_EXPLORATORIA"

    base = {
        "identidad_verificada": True,
        "modalidad": modalidad,
        "modalidad_comunicacion": r["modalidad_predeterminada"],
        "servicio_sugerido": servicio_key,
        "servicio_nombre": servicio_nombre,
        "fuente_servicio": fuente,
        "sector_id": sector["id"],
        "sector_nombre": sector["nombre"],
        "observacion_verificada": observacion,
        "hipotesis_comercial": hipotesis,
        "evidencia_origen": observacion,
        "consumo_tokens": 0,
        "motor": "reglas_deterministas",
        "conversacion": {
            "ultima_clasificacion": conversacion.ultima_clasificacion(prospect, r),
            "tipo_relacion": "educativa" if educativa else "comercial",
            "prospeccion": conversacion.estado_prospeccion(prospect, r),
            "memoria": {k: v for k, v in conversacion.memoria_efectiva(prospect, r).items() if k != "items"},
        },
        "seguimiento": conversacion.estado_seguimiento(prospect, r=r),
        "recursos_sugeridos": [],
        "revision": {
            "identidad": identidad["hallazgos"],
            "identidad_requiere_revision": identidad["requiere_revision"],
            "identidad_confirmada": identidad["confirmada_por_humano"],
            "firma_identidad": identidad["firma"],
            "mensajes": {},
        },
    }

    def bloqueado(msg, tipo_obs, ident_ok=True, pregunta=""):
        base.update({
            "identidad_verificada": ident_ok, "bloqueado_envio": True, "tipo_observacion": tipo_obs,
            "pregunta_comercial": pregunta, "mensaje_personalizado": msg, "mensaje_calido": msg, "mensaje_seguimiento": msg,
        })
        return base

    if not is_verified or servicio_key == "no_contactar":
        base["servicio_sugerido"] = "no_contactar"
        base["servicio_nombre"] = _ESPECIALES["no_contactar"]["nombre"]
        return bloqueado(
            f"[BLOQUEADO — NO CONTACTAR TODAVÍA]\nMotivo: {verif_reason}\n"
            f"Acción recomendada: Verificar primero que {nombre} opere activamente y confirmar un canal oficial antes de redactar un mensaje.",
            "IDENTIDAD_NO_VERIFICADA", ident_ok=is_verified)

    cierre = conversacion.estado_prospeccion(prospect, r)
    if cierre["cerrada"]:
        return bloqueado(
            f"[BLOQUEADO — PROSPECCIÓN CERRADA]\nMotivo: {cierre['motivo']}\n"
            f"No se envían mensajes comerciales ni seguimientos a {nombre}. Solo se reabre si el negocio lo solicita expresamente.",
            "PROSPECCION_CERRADA")

    if servicio_key == "investigar_mas":
        return bloqueado(
            f"[RECOMENDACIÓN: INVESTIGAR MÁS ANTES DE CONTACTAR]\nObservación: {observacion}\nNota comercial: {hipotesis}\n"
            f"Si decides contactar a {nombre}, selecciona manualmente una capacidad específica de CÍDIKS en el selector superior.",
            "REQUIERE_INVESTIGACION")

    if identidad["requiere_revision"]:
        motivos = "; ".join(h["mensaje"] for h in identidad["hallazgos"] if h["severidad"] == "revision")
        return bloqueado(
            f"[REVISIÓN HUMANA REQUERIDA]\nAntes de escribir a {nombre}, confirma: {motivos}\n"
            "En la ficha: «Confirmar identidad» o corrige el nombre o el giro.",
            "REQUIERE_REVISION_HUMANA", pregunta=build_adapted_question(prospect, servicio_key, sector))

    if educativa:
        mensajes = componer_educativo(prospect, servicio_key)
        base["recursos_sugeridos"] = mensajes["recursos"]
    else:
        mensajes = componer_mensajes(prospect, sector, servicio_key, fuente)
    revision_msgs = {}
    for campo, tipo in (("mensaje_personalizado", "inicial"), ("mensaje_calido", "inicial"), ("mensaje_seguimiento", "seguimiento")):
        revision_msgs[campo] = validacion.revisar_mensaje(mensajes[campo], prospect, contexto, tipo, r)
    base["revision"]["mensajes"] = revision_msgs
    base.update({
        # El envío se evalúa sobre el primer mensaje; el seguimiento tiene su propia regla (base["seguimiento"]).
        "bloqueado_envio": revision_msgs["mensaje_personalizado"]["bloqueado"],
        "tipo_observacion": "OBSERVACION_COMPROBADA" if verificadas else "HIPOTESIS_COMERCIAL",
        "pregunta_comercial": mensajes["pregunta"],
        "mensaje_personalizado": mensajes["mensaje_personalizado"],
        "mensaje_calido": mensajes["mensaje_calido"],
        "mensaje_seguimiento": mensajes["mensaje_seguimiento"],
    })
    return base
