"""
Reglas deterministas compartidas (Fase 0 — aprendizaje basado en errores reales).

Fuente única: docs/reglas/sabueso_reglas.json. La misma copia la usa Sabueso Móvil (docs/app.js),
así que la PC y el celular aplican exactamente las mismas reglas. Agregar un giro comercial
nuevo = agregar un objeto a «sectores» en el JSON; este módulo no cambia.

Todas las comparaciones de texto usan `texto_comparable()`: sin acentos, minúsculas y con
cualquier signo convertido en espacio. Es idéntica en JavaScript (ver app.js) para que las
dos implementaciones no diverjan.
"""
import json
import os
import re
import unicodedata
from pathlib import Path

RUTA_REGLAS = Path(__file__).resolve().parent / "docs" / "reglas" / "sabueso_reglas.json"

CONDICIONES_SIMPLES = {"sin_web", "con_web", "con_whatsapp", "sin_whatsapp", "con_redes", "sin_redes", "con_telefono", "con_email"}
CONDICIONES_CON_VALOR = {"nombre", "problemas"}
SERVICIOS_ESPECIALES = {"investigar_mas", "no_contactar"}

_cache = {"ruta": None, "reglas": None}


class ReglasInvalidas(ValueError):
    pass


# ---------------------------------------------------------------------------
# Texto comparable (misma definición en app.js)
# ---------------------------------------------------------------------------
def normalizar(texto) -> str:
    """Minúsculas y sin acentos (NFD sin marcas combinantes). Conserva los demás signos."""
    s = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def texto_comparable(texto) -> str:
    """Texto normalizado con todo lo que no sea a-z/0-9 convertido en un espacio, con espacios a los lados."""
    return " " + " ".join(re.sub(r"[^a-z0-9]+", " ", normalizar(texto)).split()) + " "


def contiene_frase(comparable: str, frase: str) -> bool:
    """¿El texto (ya comparable) contiene la frase como palabras completas?"""
    f = texto_comparable(frase)
    return len(f.strip()) > 0 and f in comparable


def tokens(texto) -> list:
    return texto_comparable(texto).split()


def fnv1a(texto: str) -> str:
    """Huella corta no criptográfica (igual en app.js). Solo sirve para detectar cambios."""
    h = 0x811C9DC5
    for ch in texto:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def rellenar(plantilla: str, **valores) -> str:
    out = plantilla
    for k, v in valores.items():
        out = out.replace("{" + k + "}", str(v))
    return out


# ---------------------------------------------------------------------------
# Carga y validación
# ---------------------------------------------------------------------------
def cargar_reglas(ruta=None, forzar=False) -> dict:
    ruta = Path(ruta or os.environ.get("SABUESO_REGLAS_PATH") or RUTA_REGLAS)
    if not forzar and _cache["reglas"] is not None and _cache["ruta"] == ruta:
        return _cache["reglas"]
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReglasInvalidas(f"No se pudo leer {ruta}: {exc}") from exc
    validar_reglas(datos)
    _cache.update(ruta=ruta, reglas=datos)
    return datos


def _exigir(cond, msg):
    if not cond:
        raise ReglasInvalidas(msg)


def validar_reglas(r: dict) -> None:
    """Valida la estructura para que un giro nuevo mal escrito falle con un mensaje claro."""
    for clave in ("version", "mensajes", "identidad", "localidades", "servicios", "sectores",
                  "sector_general", "modalidad_predeterminada", "modalidades"):
        _exigir(clave in r, f"Falta la sección «{clave}» en las reglas.")
    m = r["mensajes"]
    for k in ("objetivo_min", "objetivo_max", "advertencia_desde", "max_preguntas"):
        _exigir(isinstance(m.get(k), int) and m[k] >= 0, f"mensajes.{k} debe ser un entero.")
    _exigir(m["objetivo_min"] < m["objetivo_max"] < m["advertencia_desde"], "Umbrales de longitud incoherentes.")
    servicios = r["servicios"]
    _exigir(isinstance(servicios, dict) and servicios, "«servicios» debe tener al menos un servicio.")
    for sid, s in servicios.items():
        for k in ("nombre", "tema_seguimiento", "palabras_necesidad", "hipotesis"):
            _exigir(k in s, f"Al servicio «{sid}» le falta «{k}».")
    ids = set()
    for sector in r["sectores"] + [r["sector_general"]]:
        sid = sector.get("id")
        _exigir(isinstance(sid, str) and sid, "Cada sector necesita un «id».")
        _exigir(sid not in ids, f"Sector repetido: «{sid}».")
        ids.add(sid)
        for k in ("nombre", "palabras_clave", "vocabulario", "frases_propias", "reglas_servicio", "preguntas", "hipotesis"):
            _exigir(k in sector, f"Al sector «{sid}» le falta «{k}».")
        pc = sector["palabras_clave"]
        _exigir(isinstance(pc.get("fuertes"), list) and isinstance(pc.get("debiles"), list),
                f"Sector «{sid}»: palabras_clave necesita listas «fuertes» y «debiles».")
        _exigir(sector["reglas_servicio"] and sector["reglas_servicio"][-1].get("si") == [],
                f"Sector «{sid}»: la última regla de servicio debe ser la predeterminada (si: []).")
        for regla in sector["reglas_servicio"]:
            _exigir(regla.get("servicio") in servicios, f"Sector «{sid}»: servicio desconocido «{regla.get('servicio')}».")
            for cond in regla.get("si", []):
                base = cond.split(":", 1)[0]
                _exigir(cond in CONDICIONES_SIMPLES or (base in CONDICIONES_CON_VALOR and ":" in cond),
                        f"Sector «{sid}»: condición desconocida «{cond}».")
        for serv, variantes in sector["preguntas"].items():
            _exigir(serv in servicios or serv == "default", f"Sector «{sid}»: preguntas para servicio desconocido «{serv}».")
            for texto in variantes.values():
                _exigir(texto.count("?") <= m["max_preguntas"], f"Sector «{sid}»: la pregunta de «{serv}» tiene más de una pregunta.")
    _exigir("default" in r["sector_general"]["preguntas"], "sector_general.preguntas necesita «default».")
    _exigir(r["modalidad_predeterminada"] in r["modalidades"], "La modalidad predeterminada no existe.")
    # Fase 2: respuestas, memoria, seguimiento y recursos gratuitos
    for clave in ("respuestas", "memoria", "seguimiento", "recursos_gratuitos"):
        _exigir(clave in r, f"Falta la sección «{clave}» en las reglas.")
    cats = r["respuestas"]["categorias"]
    for cid in r["respuestas"]["orden"] + [r["respuestas"]["predeterminada"]]:
        _exigir(cid in cats, f"Categoría de respuesta desconocida: «{cid}».")
    for cid, c in cats.items():
        for k in ("nombre", "patrones", "cuenta_como_respuesta", "oportunidad_comercial", "conversacion", "respuesta_sugerida"):
            _exigir(k in c, f"A la categoría «{cid}» le falta «{k}».")
    _exigir(sum(1 for c in cats.values() if c["oportunidad_comercial"]) >= 1, "Ninguna categoría marca oportunidad comercial.")
    for k in ("conservar", "rechazar", "necesidad", "restriccion", "prioridad", "jerarquia_fuentes"):
        _exigir(isinstance(r["memoria"].get(k), list), f"memoria.{k} debe ser una lista.")
    _exigir(r["seguimiento"].get("maximo") == 1, "El seguimiento debe ser único (máximo 1).")
    vistos = set()
    for rec in r["recursos_gratuitos"]:
        for k in ("id", "titulo", "url", "origen", "condiciones", "intenciones", "temas", "revisado", "revisar_antes"):
            _exigir(k in rec, f"Al recurso «{rec.get('id')}» le falta «{k}».")
        _exigir(rec["id"] not in vistos, f"Recurso repetido: «{rec['id']}».")
        _exigir(rec["url"].startswith("https://"), f"El recurso «{rec['id']}» debe usar https.")
        _exigir(isinstance(rec.get("palabras", []), list), f"«palabras» del recurso «{rec['id']}» debe ser una lista.")
        vistos.add(rec["id"])
    for mid, mod in r["modalidades"].items():
        for k in ("saludos", "presentacion", "hechos", "con_necesidad", "pregunta_con_necesidad", "calido", "seguimiento"):
            _exigir(k in mod, f"A la modalidad «{mid}» le falta «{k}».")
        _exigir(len(mod["saludos"]) >= 1, f"La modalidad «{mid}» necesita al menos un saludo.")


# ---------------------------------------------------------------------------
# Sectores
# ---------------------------------------------------------------------------
def sectores(r=None) -> list:
    r = r or cargar_reglas()
    return r["sectores"]


def sector_por_id(sid: str, r=None) -> dict:
    r = r or cargar_reglas()
    for s in r["sectores"]:
        if s["id"] == sid:
            return s
    return r["sector_general"]


def detectar_sector(texto, r=None):
    """
    Devuelve {"id", "fuerte", "puntaje", "coincidencias"} o None si no hay un ganador claro.
    Palabra fuerte = 2 puntos, débil = 1. Empate = ambiguo (None).
    """
    r = r or cargar_reglas()
    comp = texto_comparable(texto)
    if not comp.strip():
        return None
    puntajes = []
    for s in r["sectores"]:
        fuertes = [p for p in s["palabras_clave"]["fuertes"] if contiene_frase(comp, p)]
        debiles = [p for p in s["palabras_clave"]["debiles"] if contiene_frase(comp, p)]
        puntaje = 2 * len(fuertes) + len(debiles)
        if puntaje:
            puntajes.append((puntaje, s["id"], bool(fuertes), fuertes + debiles))
    if not puntajes:
        return None
    puntajes.sort(key=lambda x: -x[0])
    if len(puntajes) > 1 and puntajes[0][0] == puntajes[1][0]:
        return None
    puntaje, sid, fuerte, coinc = puntajes[0]
    return {"id": sid, "fuerte": fuerte, "puntaje": puntaje, "coincidencias": coinc}


def sector_de_prospecto(p: dict, r=None) -> dict:
    """
    Sector a usar y posible discrepancia entre el giro registrado (campo «sector», p. ej. la
    categoría de búsqueda) y el que sugiere el nombre del negocio.
    """
    r = r or cargar_reglas()
    por_campo = detectar_sector(p.get("sector") or p.get("Sector") or "", r)
    por_nombre = detectar_sector(p.get("nombre") or p.get("Nombre del negocio") or "", r)
    conflicto = None
    nombre_comp = texto_comparable(p.get("nombre") or p.get("Nombre del negocio") or "")
    nombre_respalda_campo = bool(por_campo) and any(
        contiene_frase(nombre_comp, k) for k in sector_por_id(por_campo["id"], r)["palabras_clave"]["fuertes"]
    )
    if (por_campo and por_nombre and por_campo["fuerte"] and por_nombre["fuerte"]
            and por_campo["id"] != por_nombre["id"] and not nombre_respalda_campo):
        conflicto = {"registrado": por_campo["id"], "por_nombre": por_nombre["id"],
                     "palabras_nombre": por_nombre["coincidencias"]}
    elegido = por_campo or por_nombre
    sector = sector_por_id(elegido["id"], r) if elegido else r["sector_general"]
    fuente = "campo" if por_campo else ("nombre" if por_nombre else "general")
    return {"sector": sector, "id": sector["id"], "fuente": fuente, "conflicto": conflicto}


# ---------------------------------------------------------------------------
# Señales del prospecto y reglas de servicio
# ---------------------------------------------------------------------------
def senales(p: dict) -> dict:
    web = (p.get("web") or p.get("Web") or "").strip()
    wa = (p.get("whatsapp") or p.get("WhatsApp") or "").strip()
    wa_estado = (p.get("whatsapp_estado") or "").strip()
    wa_comp = bool(wa) and wa_estado in ("WHATSAPP_COMPROBADO", "confirmado")
    wa_pend = wa_estado in ("WHATSAPP_PENDIENTE_VERIFICACION", "declarado")
    return {
        "web": bool(web),
        "wa_comprobado": wa_comp,
        "wa_pendiente": wa_pend,
        "con_whatsapp": bool(wa) or wa_estado in ("WHATSAPP_COMPROBADO", "confirmado", "WHATSAPP_PENDIENTE_VERIFICACION"),
        "telefono": bool((p.get("telefono") or p.get("Teléfono") or "").strip()),
        "email": bool((p.get("email") or p.get("Email") or "").strip()),
        "redes": bool((p.get("redes_sociales") or p.get("Redes sociales") or "").strip()),
    }


def evaluar_condicion(cond: str, p: dict, s: dict) -> bool:
    if cond == "sin_web":
        return not s["web"]
    if cond == "con_web":
        return s["web"]
    if cond == "con_whatsapp":
        return s["con_whatsapp"]
    if cond == "sin_whatsapp":
        return not s["con_whatsapp"]
    if cond == "con_redes":
        return s["redes"]
    if cond == "sin_redes":
        return not s["redes"]
    if cond == "con_telefono":
        return s["telefono"]
    if cond == "con_email":
        return s["email"]
    base, valor = cond.split(":", 1)
    campo = normalizar(p.get("nombre") or "") if base == "nombre" else normalizar(p.get("problemas_detectados") or "")
    # Igual que la versión anterior: coincidencia por subcadena (p. ej. «cabana» en «cabanas»).
    return any(normalizar(v) in campo for v in valor.split("|") if v)


def servicio_por_reglas(sector: dict, p: dict, excluidos=None) -> str:
    """Primer servicio del giro cuyas condiciones se cumplen, saltando los que el prospecto rechazó o conserva."""
    excluidos = set(excluidos or [])
    s = senales(p)
    for regla in sector["reglas_servicio"]:
        if regla["servicio"] in excluidos:
            continue
        if all(evaluar_condicion(c, p, s) for c in regla.get("si", [])):
            return regla["servicio"]
    for sid in cargar_reglas()["servicios"]:
        if sid not in excluidos and sid == "consultoria":
            return sid
    return next((sid for sid in cargar_reglas()["servicios"] if sid not in excluidos), "consultoria")


def servicio_por_necesidad(texto, r=None):
    """Servicio que pide la necesidad confirmada por el prospecto, o None si no se reconoce."""
    r = r or cargar_reglas()
    comp = texto_comparable(texto)
    if not comp.strip():
        return None
    mejor, mejor_puntaje = None, 0
    for sid, serv in r["servicios"].items():  # el orden del JSON desempata
        puntaje = sum(1 for p in serv["palabras_necesidad"] if contiene_frase(comp, p))
        if puntaje > mejor_puntaje:
            mejor, mejor_puntaje = sid, puntaje
    return mejor


def estado_contacto(servicio: str, s: dict) -> str:
    if servicio == "web" and not s["web"]:
        return "sin_web"
    if s["wa_comprobado"]:
        return "con_whatsapp"
    if s["wa_pendiente"]:
        return "whatsapp_pendiente"
    return "sin_whatsapp"


def pregunta(sector: dict, servicio: str, estado: str, r=None) -> str:
    """
    Una sola pregunta. Si el WhatsApp no está verificado y no hay variante específica, primero se
    confirma el canal (nunca se da por hecho que atienden por WhatsApp).
    """
    r = r or cargar_reglas()
    gen = r["sector_general"]["preguntas"]
    if estado == "whatsapp_pendiente":
        especifica = (sector["preguntas"].get(servicio) or {}).get(estado) or (gen.get(servicio) or {}).get(estado)
        return especifica or gen["default"]["whatsapp_pendiente"]
    for fuente in (sector["preguntas"].get(servicio), gen.get(servicio)):
        if fuente:
            for clave in (estado, "default"):
                if fuente.get(clave):
                    return fuente[clave]
    return gen["default"]["default"]


def localidad(p: dict, r=None) -> str:
    """Localidad para el mensaje. Si no hay dato real, devuelve '' (nunca inventa una ubicación)."""
    r = r or cargar_reglas()
    municipio = (p.get("municipio") or p.get("Ubicación") or "").strip()
    comp = texto_comparable(f"{municipio} {p.get('nombre') or ''} {p.get('web') or ''}")
    for loc in r["localidades"]:
        if any(contiene_frase(comp, pat) or texto_comparable(pat).strip().replace(" ", "") in comp.replace(" ", "")
               for pat in loc["patrones"]):
            return loc["nombre"]
    if municipio and normalizar(municipio) != "costa de oaxaca":
        return municipio
    return ""


def servicios_validos(r=None) -> set:
    r = r or cargar_reglas()
    return set(r["servicios"]) | SERVICIOS_ESPECIALES
