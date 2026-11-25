"""
Fase 4 — Aprendizaje y métricas (determinista, 0 tokens).

- Seudónimos: HMAC-SHA256 del identificador del prospecto con una CLAVE LOCAL que nunca sale de la PC
  (archivo `clave_seudonimos.key` junto a la base de datos; `data/` no se sube a Git).
  Esto es SEUDONIMIZACIÓN, no anonimización: con la clave y la base se puede volver a vincular.
- Textos del registro: sin correos, teléfonos, enlaces, nombre ni dominio del negocio, ni nombres
  de personas presentadas como «soy…», «me llamo…».
- Huella de cada envío confirmado: plantilla, estrategia, largo, preguntas y si se editó.
- Comparación por estrategia con aviso de muestra chica.
Las funciones puras (huella_envio, resultado_envio, comparar_estrategias) tienen su gemela en
docs/motor.js; la prueba de paridad lo verifica.
"""
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path

import config
import conversacion
import reglas as R
import validacion

NOMBRE_CLAVE = "clave_seudonimos.key"
PLANTILLAS = ("mensaje_personalizado", "mensaje_calido", "mensaje_seguimiento")
NOTA_SEUDONIMIZACION = ("Los prospectos aparecen como un código HMAC-SHA256 con clave local. "
                        "Es seudonimización, no anonimización: con la clave y la base se puede volver a vincular.")

_RE_ENLACE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_RE_PRESENTACION = re.compile(
    r"\b((?:[Ss]oy|[Mm]e llamo|[Mm]i nombre es|[Aa]tentamente,?|[Aa]tte\.?)\s+)"
    r"[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+)?")


def ruta_clave() -> Path:
    return Path(config.get_database_path()).resolve().parent / NOMBRE_CLAVE


def clave_local() -> bytes:
    """Lee la clave local o la crea (32 bytes aleatorios) la primera vez. Nunca la reemplaza."""
    ruta = ruta_clave()
    try:
        datos = ruta.read_bytes()
    except FileNotFoundError:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(ruta), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return clave_local()
        clave = secrets.token_bytes(32)
        with os.fdopen(fd, "wb") as f:
            f.write(clave)
        return clave
    if len(datos) < 32:
        raise RuntimeError(f"La clave de seudónimos ({ruta}) está dañada. Restáurala del respaldo; no se reemplaza sola.")
    return datos


def seudonimo(negocio_id) -> str:
    return "p_" + hmac.new(clave_local(), f"negocio:{negocio_id}".encode(), hashlib.sha256).hexdigest()[:16]


def anonimizar(texto: str, nombres=(), dominios=(), limite: int = 300) -> str:
    """Quita datos que identifican al negocio o a personas antes de guardar en el registro."""
    t = _RE_ENLACE.sub("[enlace]", str(texto or ""))
    t = conversacion.redactar(t, 4000)
    for d in sorted({d for d in dominios if d and len(d) >= 4}, key=len, reverse=True):
        t = re.sub(re.escape(d), "[dominio]", t, flags=re.IGNORECASE)
    for n in sorted({n.strip() for n in nombres if n and len(n.strip()) >= 3}, key=len, reverse=True):
        t = re.sub(re.escape(n), "[negocio]", t, flags=re.IGNORECASE)
    t = _RE_PRESENTACION.sub(r"\1[nombre]", t)
    return t.strip()[:limite]


# ---------------------------------------------------------------- funciones puras (paridad con motor.js)
def _norm(t) -> str:
    return " ".join(str(t or "").split())


def huella_envio(mensaje: str, p: dict, plantilla: str = "", r=None) -> dict:
    """Qué se envió (sin el texto): plantilla, estrategia, largo, preguntas y si se editó el borrador."""
    m = _norm(mensaje)
    coincide = next((k for k in PLANTILLAS if m and _norm(p.get(k)) == m), "")
    if coincide:
        plantilla, editado = coincide, False
    else:
        plantilla = plantilla if plantilla in PLANTILLAS else ("mensaje_personalizado" if m else "sin_mensaje")
        editado = bool(m)
    relacion = "educativa" if (p.get("tipo_relacion") or "") == "educativa" else "comercial"
    met = validacion._metricas(mensaje)
    return {"plantilla": plantilla, "estrategia": f"{relacion}|{plantilla}|{p.get('servicio_sugerido') or 'general'}",
            "caracteres": met["caracteres"], "preguntas": met["preguntas"], "editado": editado}


def resultado_envio(clasificaciones, r=None) -> str:
    """Resultado más decisivo de las respuestas recibidas después de un envío."""
    r = r or R.cargar_reglas()
    cats = r["respuestas"]["categorias"]
    infos = [cats[c] for c in clasificaciones or [] if c in cats]
    if any(i["oportunidad_comercial"] for i in infos):
        return "interes"
    if any(i.get("cierra_prospeccion") for i in infos):
        return "rechazo"
    if any(i["conversacion"] == "educativa" for i in infos):
        return "educativa"
    if any(i["cuenta_como_respuesta"] for i in infos):
        return "respuesta"
    return "sin_respuesta"


def comparar_estrategias(envios, r=None) -> list:
    """Respuestas humanas, interés y rechazos por estrategia, con aviso cuando la muestra es chica."""
    r = r or R.cargar_reglas()
    minimo = r["aprendizaje"]["muestra_minima"]
    validos = r["aprendizaje"]["resultados"]
    grupos = {}
    for e in envios or []:
        g = grupos.setdefault(e.get("estrategia") or "sin_huella", dict.fromkeys(["enviados"] + validos, 0))
        g["enviados"] += 1
        g[e.get("resultado") if e.get("resultado") in validos else "sin_respuesta"] += 1
    salida = []
    for est in sorted(grupos):
        g = grupos[est]
        humanas = g["interes"] + g["rechazo"] + g["educativa"] + g["respuesta"]
        suficiente = g["enviados"] >= minimo
        salida.append({
            "estrategia": est, "enviados": g["enviados"], "respuestas_humanas": humanas,
            "interes": g["interes"], "rechazos": g["rechazo"], "educativas": g["educativa"],
            "tasa_respuesta": humanas * 100 // g["enviados"], "muestra_suficiente": suficiente,
            "aviso": "" if suficiente else f"Muestra chica ({g['enviados']} de {minimo} envíos mínimos): todavía no saques conclusiones.",
        })
    return salida
