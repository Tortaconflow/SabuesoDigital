"""
Fase 1 — Validación de identidad comercial y revisión de borradores (determinista, 0 tokens).

Principios (decisiones del 25-nov):
- Una discrepancia (nombre vs dominio, giro, contacto compartido) genera REVISIÓN HUMANA,
  nunca invalidación automática: no se borra nada ni se marca «no contactar».
- No hay palabras prohibidas de forma absoluta: un término de otro giro solo se señala si no
  está respaldado por la evidencia del prospecto ni por el contexto propio de su giro.
- La longitud nunca bloquea por sí sola: objetivo 80–180 caracteres, aviso desde 200.
- La aprobación humana sigue siendo obligatoria: esto solo informa, bloquea o pide revisión.

Severidades: «bloqueo» (no se puede enviar hasta corregir), «revision» (requiere aprobación
humana explícita), «advertencia» y «info» (solo informan).
La versión de bolsillo (docs/app.js) replica estas reglas; las pruebas de paridad lo verifican.
"""
from urllib.parse import urlparse

import contact_identity
import conversacion
import reglas as R

SUFIJOS_DOMINIO = {"com", "mx", "net", "org", "info", "biz", "example", "travel", "co", "site", "online",
                   "store", "shop", "app", "io", "gob", "edu", "www"}


def _h(codigo, severidad, mensaje, **detalle):
    return {"codigo": codigo, "severidad": severidad, "mensaje": mensaje, "detalle": detalle}


def dominio_de(url: str) -> str:
    if not url:
        return ""
    try:
        host = (urlparse(url if "://" in url else f"https://{url}").netloc or "").lower()
    except ValueError:
        return ""
    host = host.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def etiqueta_dominio(dominio: str) -> str:
    partes = [p for p in dominio.split(".") if p and p not in SUFIJOS_DOMINIO]
    return "".join(ch for ch in (partes[-1] if partes else "") if ch.isalnum()).lower()


def tokens_distintivos(nombre: str, r=None) -> list:
    r = r or R.cargar_reglas()
    genericas = set(r["identidad"]["palabras_genericas_nombre"])
    return [t for t in R.tokens(nombre) if len(t) >= 3 and t not in genericas]


def comparar_nombre_dominio(nombre: str, dominio: str, municipio: str = "", r=None) -> str:
    """'coincide', 'descriptivo' (dominio genérico tipo hotelenpuertoescondido), 'sin_dato' o 'no_coincide'."""
    r = r or R.cargar_reglas()
    etiqueta = etiqueta_dominio(dominio)
    todos = R.tokens(nombre)
    if not etiqueta or not todos:
        return "sin_dato"
    distintivos = tokens_distintivos(nombre, r)
    concatenado = "".join(todos)
    if any(t in etiqueta for t in distintivos):
        return "coincide"
    if (len(etiqueta) >= 4 and etiqueta in concatenado) or concatenado in etiqueta:
        return "coincide"
    acronimo = "".join(t[0] for t in todos)
    if len(acronimo) >= 3 and etiqueta.startswith(acronimo):
        return "coincide"
    # ¿El dominio solo describe giro + lugar? Entonces no permite comparar nombres.
    quitar = set(r["identidad"]["palabras_genericas_nombre"]) | set(R.tokens(municipio))
    for loc in r["localidades"]:
        for pat in loc["patrones"]:
            quitar |= set(R.tokens(pat))
    for s in r["sectores"]:
        quitar |= {t for k in s["palabras_clave"]["fuertes"] for t in R.tokens(k)}
    resto = etiqueta
    for palabra in sorted((w for w in quitar if len(w) >= 2), key=lambda w: (-len(w), w)):
        resto = resto.replace(palabra, "")
    if len(resto) <= 2:
        return "descriptivo"
    if not distintivos:
        return "sin_dato"
    return "no_coincide"


def nombres_compatibles(a: str, b: str, r=None) -> bool:
    ta, tb = set(tokens_distintivos(a, r)), set(tokens_distintivos(b, r))
    if ta & tb:
        return True
    ca, cb = "".join(R.tokens(a)), "".join(R.tokens(b))
    return bool(ca and cb and (ca in cb or cb in ca))


def firma_identidad(p: dict, r=None) -> str:
    """Huella de los datos de identidad revisados. Si cambian, la revisión humana se vuelve a pedir."""
    r = r or R.cargar_reglas()
    claves = sorted(contact_identity.claves_contacto(p)["claves"])
    sec = R.sector_de_prospecto(p, r)
    base = "|".join([
        " ".join(R.tokens(p.get("nombre") or "")),
        dominio_de(p.get("web") or ""),
        ",".join(claves),
        sec["id"],
        (sec["conflicto"] or {}).get("por_nombre", ""),
    ])
    return R.fnv1a(base)


def indice_claves(prospectos) -> dict:
    """Número normalizado -> [(id, nombre)] para revisar contactos compartidos en O(n)."""
    indice = {}
    for o in prospectos or []:
        for k in contact_identity.claves_contacto(o)["claves"]:
            indice.setdefault(k, []).append((o.get("id"), o.get("nombre") or ""))
    return indice


def analizar_identidad(p: dict, contexto=None, r=None, indice=None) -> dict:
    """Hallazgos de identidad. Nunca invalida: las discrepancias piden revisión humana."""
    r = r or R.cargar_reglas()
    hallazgos = []
    nombre = p.get("nombre") or p.get("Nombre del negocio") or ""
    dominio = dominio_de(p.get("web") or p.get("Web") or "")

    sec = R.sector_de_prospecto(p, r)
    if sec["conflicto"]:
        c = sec["conflicto"]
        hallazgos.append(_h(
            "IDENT_SECTOR_DISCREPANCIA", "revision",
            f"El giro registrado es «{R.sector_por_id(c['registrado'], r)['nombre']}», pero el nombre sugiere "
            f"«{R.sector_por_id(c['por_nombre'], r)['nombre']}» ({', '.join(c['palabras_nombre'])}). Confirma el giro antes de escribir.",
            registrado=c["registrado"], por_nombre=c["por_nombre"]))
    elif sec["fuente"] == "general":
        hallazgos.append(_h("IDENT_SECTOR_DESCONOCIDO", "info",
                            "No se reconoció el giro; se usarán preguntas generales.", sector="general"))

    if dominio:
        if any(dominio == d or dominio.endswith("." + d) for d in r["identidad"]["dominios_redes"]):
            hallazgos.append(_h("IDENT_FUENTE_RED_SOCIAL", "info",
                                f"La fuente es una red social o enlace ({dominio}); no se compara el nombre con el dominio.", dominio=dominio))
        elif any(d in dominio for d in r["identidad"]["dominios_directorio"]):
            hallazgos.append(_h("IDENT_SITIO_DIRECTORIO", "revision",
                                f"El sitio ({dominio}) es un directorio: el nombre o el contacto pueden ser de otro negocio.", dominio=dominio))
        else:
            comp = comparar_nombre_dominio(nombre, dominio, p.get("municipio") or "", r)
            if comp == "no_coincide":
                hallazgos.append(_h("IDENT_NOMBRE_DOMINIO", "revision",
                                    f"El nombre «{nombre}» no coincide con el sitio {dominio}. ¿Es el mismo negocio?",
                                    nombre=nombre, dominio=dominio))
            elif comp == "descriptivo":
                hallazgos.append(_h("IDENT_DOMINIO_DESCRIPTIVO", "info",
                                    f"El dominio {dominio} es descriptivo; no permite confirmar el nombre.", dominio=dominio))

    if contexto or indice:
        indice = indice if indice is not None else indice_claves(contexto)
        encontrado = None
        for k in contact_identity.claves_contacto(p)["claves"]:
            for otro_id, otro_nombre in indice.get(k, []):
                if p.get("id") is not None and otro_id == p.get("id"):
                    continue
                if otro_id is None and otro_nombre == nombre:
                    continue
                if not nombres_compatibles(nombre, otro_nombre, r):
                    encontrado = (otro_id, otro_nombre)
                    break
            if encontrado:
                break
        if encontrado:
            hallazgos.append(_h(
                "IDENT_CONTACTO_COMPARTIDO", "revision",
                f"El mismo número aparece en «{encontrado[1]}». Puede ser de una agencia o directorio, no de este negocio.",
                otro_id=encontrado[0], otro_nombre=encontrado[1]))

    firma = firma_identidad(p, r)
    pide_revision = any(h["severidad"] == "revision" for h in hallazgos)
    confirmada = pide_revision and (p.get("identidad_revisada_firma") or "") == firma
    return {
        "hallazgos": hallazgos,
        "firma": firma,
        "requiere_revision": pide_revision and not confirmada,
        "confirmada_por_humano": confirmada,
        "sector_id": sec["id"],
        "sector_fuente": sec["fuente"],
    }


# ---------------------------------------------------------------------------
# Revisión de borradores
# ---------------------------------------------------------------------------
_RE_SALUDO = None
_CONECTORES = {"de", "del", "la", "el", "los", "las", "y", "&"}


def _sin_acentos_conserva_mayusculas(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if not unicodedata.combining(c))


def _candidatos_saludo(texto: str) -> list:
    """
    Destinatarios explícitos del saludo: solo nombres propios (con mayúscula) después de
    «Hola», «Buen día» o «equipo de». «Hola, les escribo…» o «Hola, soy Ana…» no son destinatarios.
    """
    import re
    global _RE_SALUDO
    if _RE_SALUDO is None:
        _RE_SALUDO = re.compile(
            r"(?:\b[Ee]quipo del?|\b[Hh]ola,?|\b[Bb]uen dia,?|\b[Bb]uenos dias,?|\b[Bb]uenas tardes,?)\s+"
            r"((?:[A-Z0-9][A-Za-z0-9'&]*)(?:\s+(?:de|del|la|el|los|las|y|&|[A-Z0-9][A-Za-z0-9'&]*))*)")
    out = []
    for m in _RE_SALUDO.finditer(_sin_acentos_conserva_mayusculas(texto)):
        palabras = m.group(1).split()
        while palabras and palabras[-1].lower() in _CONECTORES:
            palabras.pop()
        if palabras:
            out.append(" ".join(palabras))
    return out


def _texto_evidencia(p: dict) -> str:
    campos = ("nombre", "sector", "observacion_verificada", "problemas_detectados", "necesidad_expresada",
              "respuesta", "notas", "redes_sociales")
    return R.texto_comparable(" ".join(str(p.get(c) or "") for c in campos))


def _metricas(texto: str) -> dict:
    t = (texto or "").strip()
    return {"caracteres": len(t), "palabras": len(t.split()), "preguntas": t.count("?")}


def revisar_mensaje(texto: str, p: dict, contexto=None, tipo: str = "inicial", r=None) -> dict:
    r = r or R.cargar_reglas()
    cfg = r["mensajes"]
    hallazgos = []
    t = (texto or "").strip()
    met = _metricas(t)

    if t.startswith("[BLOQUEADO") or t.startswith("[RECOMENDACIÓN") or t.startswith("[REVISIÓN"):
        return {"hallazgos": [_h("MSG_NO_ENVIABLE", "bloqueo", "Este texto es un aviso interno, no un mensaje para enviar.")],
                "bloqueado": True, "requiere_aprobacion": False, "metricas": met, "en_objetivo": False}

    comp = R.texto_comparable(t)
    nombre = p.get("nombre") or p.get("Nombre del negocio") or ""
    propios = set(tokens_distintivos(nombre, r)) | set(R.tokens(nombre))

    # 1. ¿Saluda a otro negocio?
    saludo_palabras = set(r["identidad"]["palabras_saludo"]) | set(r["identidad"]["palabras_genericas_nombre"])
    for cand in _candidatos_saludo(t):
        dist = [w for w in R.tokens(cand) if w not in saludo_palabras and len(w) >= 3]
        if dist and not (set(dist) & propios):
            hallazgos.append(_h("MSG_SALUDO_OTRO_NOMBRE", "bloqueo",
                                f"El saludo va dirigido a «{cand.strip()}», que no es «{nombre}».", saludo=cand.strip()))
            break

    # 2. ¿Menciona a otro prospecto conocido?
    nombre_comp = R.texto_comparable(nombre)
    for otro in contexto or []:
        if p.get("id") is not None and otro.get("id") == p.get("id"):
            continue
        dist = tokens_distintivos(otro.get("nombre") or "", r)
        frase = " ".join(dist)
        if frase and (len(dist) >= 2 or len(frase) >= 6) and R.contiene_frase(comp, frase) and not R.contiene_frase(nombre_comp, frase):
            hallazgos.append(_h("MSG_OTRO_NEGOCIO", "bloqueo",
                                f"El mensaje menciona a otro prospecto: «{otro.get('nombre')}».", otro_id=otro.get("id")))
            break
        etiqueta = etiqueta_dominio(dominio_de(otro.get("web") or ""))
        if len(etiqueta) >= 6 and f" {etiqueta} " in comp and etiqueta not in "".join(R.tokens(nombre)):
            hallazgos.append(_h("MSG_OTRO_NEGOCIO", "bloqueo",
                                f"El mensaje menciona el sitio de otro prospecto: «{otro.get('nombre')}».", otro_id=otro.get("id")))
            break

    # 3. Vocabulario de otro giro (contextual, no prohibición absoluta)
    sec = R.sector_de_prospecto(p, r)
    sector = sec["sector"]
    if sector["id"] != "general":
        evidencia = _texto_evidencia(p)
        propio = {R.texto_comparable(v).strip() for v in sector["vocabulario"]}
        frases_propias = [R.texto_comparable(f).strip() for f in sector["frases_propias"]]
        frases_en_msg = [f for f in frases_propias if f and f" {f} " in comp]
        for otro_sector in r["sectores"]:
            if otro_sector["id"] == sector["id"]:
                continue
            for termino in otro_sector["vocabulario"]:
                tc = R.texto_comparable(termino).strip()
                if not tc or tc in propio or f" {tc} " not in comp:
                    continue
                if f" {tc} " in evidencia or any(tc in f for f in frases_en_msg):
                    continue
                hallazgos.append(_h(
                    "MSG_VOCABULARIO_OTRO_GIRO", "revision",
                    f"«{termino}» es propio de «{otro_sector['nombre']}» y este negocio es de «{sector['nombre']}». "
                    "Revisa que la propuesta corresponda a su giro.",
                    termino=termino, giro_termino=otro_sector["id"], giro_negocio=sector["id"]))
                break
            if any(h["codigo"] == "MSG_VOCABULARIO_OTRO_GIRO" for h in hallazgos):
                break

    # 4. Conversación: prospección cerrada, seguimiento único y lo que el prospecto rechazó o conserva
    cierre = conversacion.estado_prospeccion(p, r)
    if cierre["cerrada"]:
        hallazgos.append(_h("MSG_PROSPECCION_CERRADA", "bloqueo",
                            f"Prospección cerrada: {cierre['motivo']} Solo se reabre si el negocio lo solicita expresamente."))
    elif tipo == "seguimiento":
        seg = conversacion.estado_seguimiento(p, r=r)
        if not seg["permitido"]:
            hallazgos.append(_h("SEG_NO_PERMITIDO", "bloqueo", f"Seguimiento no disponible: {seg['motivo']}", desde=seg["desde"]))
    for servicio_id in conversacion.memoria_efectiva(p, r)["excluidos"]:
        serv = r["servicios"].get(servicio_id) or {}
        frases = [serv.get("nombre", "")] + [f for f in serv.get("palabras_necesidad", []) if len(R.tokens(f)) >= 2]
        if any(f and R.contiene_frase(comp, f) for f in frases):
            hallazgos.append(_h("MSG_SERVICIO_EXCLUIDO", "revision",
                                f"El negocio dijo que no quiere o que conserva «{serv.get('nombre', servicio_id)}». No insistas.",
                                servicio=servicio_id))
            break

    # 5. Calidad: longitud (nunca bloquea), preguntas, genérico, nombre, jerga
    if met["caracteres"] >= cfg["advertencia_desde"]:
        hallazgos.append(_h("MSG_LARGO", "advertencia",
                            f"Mensaje largo: {met['caracteres']} caracteres (objetivo {cfg['objetivo_min']}–{cfg['objetivo_max']}).",
                            caracteres=met["caracteres"]))
    elif met["caracteres"] > cfg["objetivo_max"] or met["caracteres"] < cfg["objetivo_min"]:
        hallazgos.append(_h("MSG_FUERA_OBJETIVO", "info",
                            f"{met['caracteres']} caracteres; el objetivo experimental es {cfg['objetivo_min']}–{cfg['objetivo_max']}.",
                            caracteres=met["caracteres"]))
    if tipo != "seguimiento" and met["preguntas"] > cfg["max_preguntas"]:
        hallazgos.append(_h("MSG_PREGUNTAS", "advertencia",
                            f"Tiene {met['preguntas']} preguntas; conviene una sola.", preguntas=met["preguntas"]))
    genericas = [f for f in cfg["frases_genericas"] if R.contiene_frase(comp, f)]
    if genericas:
        hallazgos.append(_h("MSG_GENERICO", "advertencia",
                            "Frases genéricas: " + ", ".join(f"«{g}»" for g in genericas) + ".", frases=genericas))
    dist_propios = tokens_distintivos(nombre, r)
    if nombre and not (R.contiene_frase(comp, nombre) or any(R.contiene_frase(comp, d) for d in dist_propios)):
        hallazgos.append(_h("MSG_SIN_NOMBRE", "advertencia", "El mensaje no menciona al negocio por su nombre."))
    jerga = [j for j in cfg["jerga_tecnica"] if R.contiene_frase(comp, j)]
    if jerga:
        hallazgos.append(_h("MSG_JERGA", "advertencia", "Jerga técnica: " + ", ".join(jerga) + ".", terminos=jerga))

    return {
        "hallazgos": hallazgos,
        "bloqueado": any(h["severidad"] == "bloqueo" for h in hallazgos),
        "requiere_aprobacion": any(h["severidad"] == "revision" for h in hallazgos),
        "metricas": met,
        "en_objetivo": cfg["objetivo_min"] <= met["caracteres"] <= cfg["objetivo_max"],
    }
