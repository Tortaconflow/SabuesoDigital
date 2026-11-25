"""
Fase 3 — Lectura local de QR (determinista, sin red, 0 tokens).

La imagen se decodifica en el navegador (jsQR, incluido en el proyecto). Aquí solo se interpreta
el TEXTO del QR: qué tipo es (WhatsApp, menú o catálogo, redes, mapa, tarjeta de contacto, Wi-Fi,
enlace o texto) y qué hecho observable aporta («ya cuenta con menú digital»).
- Nunca se abre el enlace ni se consulta internet.
- Solo se guarda el tipo y, si aplica, el dominio. Nunca contraseñas de Wi-Fi, datos de tarjetas
  de contacto ni números de teléfono.
La versión de bolsillo (docs/motor.js: interpretarQr) replica estas reglas; la prueba de paridad lo verifica.
"""
import json
import re

import reglas as R

_RE_URL = re.compile(r"^([a-z][a-z0-9+.\-]*):(//)?([^/?#\s]*)([^?#\s]*)", re.IGNORECASE)
_RE_DOMINIO = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
_RE_SSID = re.compile(r"(?:^|;)S:((?:\\.|[^;])*)")


def _partes_url(t: str):
    m = _RE_URL.match(t)
    if not m:
        return None
    host = m.group(3).lower().rsplit("@", 1)[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return m.group(1).lower(), host, m.group(4).lower()


def _coincide(host: str, ruta: str, patron: str) -> bool:
    i = patron.find("/")
    dom, pref = (patron, "") if i < 0 else (patron[:i], patron[i:])
    return (host == dom or host.endswith("." + dom)) and ruta.startswith(pref)


def interpretar_qr(texto: str, r=None):
    """Interpreta el contenido de un QR. No guarda nada: devuelve lo que una persona debe confirmar."""
    r = r or R.cargar_reglas()
    q = r["qr"]
    t = str(texto or "").strip()[:2000]
    if not t:
        return None
    tipo, dominio, vista = "texto", "", t[:300]
    mayus = t.upper()
    for tid, cfg in q["tipos"].items():
        if any(mayus.startswith(p.upper()) for p in cfg.get("prefijos", [])):
            tipo = tid
            break
    if tipo == "wifi":
        m = _RE_SSID.search(t[5:])
        vista = f"Red Wi-Fi «{m.group(1) if m else 'sin nombre'}» (la contraseña no se muestra ni se guarda)"
    elif tipo == "contacto":
        vista = "Tarjeta de contacto (sus datos no se guardan)"
    else:
        partes = _partes_url(t)
        if partes:
            esquema, host, ruta = partes
            web = esquema in ("http", "https") and bool(host)
            for tid in q["orden"]:
                cfg = q["tipos"][tid]
                if esquema in cfg.get("esquemas", []) or (web and any(_coincide(host, ruta, p) for p in cfg.get("patrones", []))):
                    tipo = tid
                    break
            if tipo == "texto" and web:
                palabras = set(w for w in re.split(r"[^a-z0-9]+", host + " " + ruta) if w)
                tipo = next((tid for tid in q["orden"] if palabras & set(q["tipos"][tid].get("palabras", []))), "enlace")
            if tipo != "texto":
                dominio = host if _RE_DOMINIO.match(host) else ""
                if web:
                    vista = f"{esquema}://{host}{ruta}"[:300]
    cfg = q["tipos"][tipo]
    if not cfg["guardar_dominio"]:
        dominio = ""
    observacion = R.rellenar(cfg["observacion"], dominio=dominio or "un sitio") if cfg["observacion"] else ""
    return {
        "tipo": tipo,
        "nombre": cfg["nombre"],
        "dominio": dominio,
        "observacion": observacion,
        "servicio_existente": cfg["servicio_existente"],
        "vista": vista,
        "guardable": bool(cfg["guardar"]),
        "entrada": {"tipo": tipo, "dominio": dominio} if cfg["guardar"] else None,
    }


def sanear_qr(entrada, r=None):
    """Solo tipo conocido y dominio válido (si el tipo lo admite). Todo lo demás se descarta."""
    r = r or R.cargar_reglas()
    if not isinstance(entrada, dict):
        return None
    tipo = str(entrada.get("tipo") or "")
    cfg = r["qr"]["tipos"].get(tipo)
    if not cfg or not cfg["guardar"]:
        return None
    dominio = str(entrada.get("dominio") or "").strip().lower()[:253]
    if not cfg["guardar_dominio"] or not _RE_DOMINIO.match(dominio):
        dominio = ""
    return {"tipo": tipo, "dominio": dominio}


def lista_qr(p: dict, r=None) -> list:
    """QR guardados del prospecto (lista o JSON), saneados y sin repetidos."""
    r = r or R.cargar_reglas()
    crudo = p.get("qr_recibidos") or []
    if isinstance(crudo, str):
        try:
            crudo = json.loads(crudo)
        except ValueError:
            crudo = []
    vistos, salida = set(), []
    for e in crudo if isinstance(crudo, list) else []:
        s = sanear_qr(e, r)
        if s and (s["tipo"], s["dominio"]) not in vistos:
            vistos.add((s["tipo"], s["dominio"]))
            salida.append(s)
    return salida


def observaciones_qr(p: dict, r=None) -> list:
    """Hechos observables aportados por los QR recibidos (para la observación verificada)."""
    r = r or R.cargar_reglas()
    salida = []
    for e in lista_qr(p, r):
        cfg = r["qr"]["tipos"][e["tipo"]]
        if not cfg["observacion"]:
            continue
        obs = R.rellenar(cfg["observacion"], dominio=e["dominio"] or "un sitio")
        if e["dominio"] and "{dominio}" not in cfg["observacion"]:
            obs += f" (QR: {e['dominio']})"
        if obs not in salida:
            salida.append(obs)
    return salida


def memoria_qr(p: dict, r=None) -> list:
    """Lo que el QR demuestra que el negocio YA tiene: no se le vuelve a proponer."""
    r = r or R.cargar_reglas()
    items = []
    for e in lista_qr(p, r):
        cfg = r["qr"]["tipos"][e["tipo"]]
        if cfg["servicio_existente"]:
            items.append({"tipo": "canal_existente", "servicio": cfg["servicio_existente"],
                          "texto": R.rellenar(cfg["observacion"], dominio=e["dominio"] or "un sitio"), "fuente": "qr"})
    return items
