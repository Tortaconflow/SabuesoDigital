"""
Identidad de contacto y bandejas de prospección (Pendientes / Abiertos / Contactados).

- Un mismo contacto se reconoce por su número normalizado en formato E.164 (+52XXXXXXXXXX),
  sin espacios, guiones ni paréntesis.
- Si el número no trae código de país, se usa el país del prospecto cuando se puede saber
  (campo `pais` o una ubicación mexicana reconocible). Si no se puede saber, o el número es
  inválido, el número queda como «ambiguo»/«inválido» y NUNCA se usa para unir prospectos.
- Este módulo no fusiona ni borra registros: solo decide qué se muestra en Pendientes.

La versión de bolsillo (docs/app.js) replica estas mismas reglas; mantenlas alineadas.
"""
import re
import unicodedata

CODIGOS_PAIS = {"MX": "52"}

# Estados comerciales que implican que ya hubo un contacto confirmado.
ESTADOS_CONTACTADOS = {"contactado", "interesado", "no_interesa", "propuesta", "ganado"}

_MARCAS_MEXICO = (
    "mexico", "cdmx", "aguascalientes", "baja california", "campeche", "chiapas", "chihuahua",
    "coahuila", "colima", "durango", "guanajuato", "guerrero", "hidalgo", "jalisco", "michoacan",
    "morelos", "nayarit", "nuevo leon", "oaxaca", "puebla", "queretaro", "quintana roo",
    "san luis potosi", "sinaloa", "sonora", "tabasco", "tamaulipas", "tlaxcala", "veracruz",
    "yucatan", "zacatecas",
    # Localidades de la Costa de Oaxaca que usa Sabueso (copilot.infer_specific_locality)
    "puerto escondido", "zicatela", "bacocho", "carrizalillo", "mazunte", "zipolite", "huatulco",
    "chahue", "santa cruz huatulco", "puerto angel", "san agustinillo", "pochutla", "chacahua",
    "juquila", "pinotepa", "salina cruz", "juchitan", "tehuantepec", "mitla", "tlacolula",
)
_RE_MEXICO = re.compile(r"\b(" + "|".join(re.escape(m) for m in _MARCAS_MEXICO) + r")\b")
_RE_SEPARADORES_NUMEROS = re.compile(r"[,;/|\n]|\s+(?:y|o|or|and)\s+", re.IGNORECASE)
_RE_EXTENSION = re.compile(r"\s*(?:ext\.?|extension|extensión|x)\s*\d+\s*$", re.IGNORECASE)
_RE_FORMATO = re.compile(r"[\s\-(). ]")


def _sin_acentos(texto) -> str:
    return unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii").lower()


def pais_del_prospecto(p: dict) -> str:
    """Código ISO del país del prospecto ('MX'), o '' si no se puede saber."""
    explicito = _sin_acentos(p.get("pais") or p.get("país") or "").strip()
    if explicito:
        if explicito in ("mx", "mex", "mexico"):
            return "MX"
        return explicito.upper()[:2]
    ubicacion = _sin_acentos(" ".join(str(p.get(k) or "") for k in ("municipio", "Ubicación", "direccion")))
    if "nuevo mexico" in ubicacion or "new mexico" in ubicacion:
        return ""
    return "MX" if _RE_MEXICO.search(ubicacion) else ""


def normalizar_telefono(raw, pais: str = "", es_whatsapp: bool = False) -> dict:
    """
    Devuelve {"estado": "valido"|"ambiguo"|"invalido", "e164": "+52...", "motivo": "..."}.
    Solo los números «valido» sirven para reconocer que dos prospectos son el mismo contacto.
    """
    s = str(raw or "").strip()
    if not s:
        return {"estado": "invalido", "e164": "", "motivo": "sin número"}
    s = _RE_EXTENSION.sub("", s)
    s = _RE_FORMATO.sub("", s)

    internacional = False
    if s.startswith("+"):
        internacional, s = True, s[1:]
    elif s.startswith("00") and len(s) >= 11:
        internacional, s = True, s[2:]
    if not s.isdigit():
        return {"estado": "invalido", "e164": "", "motivo": "contiene caracteres que no son dígitos"}

    # Formatos sin '+' que ya traen el código de México.
    if not internacional and len(s) == 12 and s.startswith("52"):
        internacional = True
    elif not internacional and len(s) == 13 and s.startswith("521"):
        internacional = True
    elif not internacional and es_whatsapp and 11 <= len(s) <= 15:
        # Los enlaces wa.me / api.whatsapp siempre llevan el código de país.
        internacional = True

    if internacional:
        if s.startswith("52"):
            nacional = s[2:]
            if len(nacional) == 11 and nacional.startswith("1"):
                nacional = nacional[1:]  # prefijo histórico de celular 521
            return _validar_mx(nacional)
        if 8 <= len(s) <= 15 and len(set(s)) > 2 and not s.startswith("0"):
            return {"estado": "valido", "e164": "+" + s, "motivo": ""}
        return {"estado": "invalido", "e164": "", "motivo": "número internacional con longitud inválida"}

    if len(s) == 10:
        pais = (pais or "").upper()
        if pais == "MX":
            return _validar_mx(s)
        if not pais:
            return {"estado": "ambiguo", "e164": "", "motivo": "sin código de país y país del prospecto desconocido"}
        return {"estado": "ambiguo", "e164": "", "motivo": f"sin código de país para {pais}"}
    if 7 <= len(s) <= 9:
        return {"estado": "ambiguo", "e164": "", "motivo": "número local sin lada"}
    return {"estado": "invalido", "e164": "", "motivo": "longitud inválida"}


def _validar_mx(nacional: str) -> dict:
    if len(nacional) != 10 or nacional[0] in "01" or len(set(nacional)) <= 2:
        return {"estado": "invalido", "e164": "", "motivo": "número mexicano inválido"}
    return {"estado": "valido", "e164": "+52" + nacional, "motivo": ""}


def claves_contacto(p: dict) -> dict:
    """Números válidos (E.164) del prospecto y el estado general de sus teléfonos."""
    pais = pais_del_prospecto(p)
    claves, estados = [], []
    for campo, es_wa in (("whatsapp", True), ("telefono", False)):
        valor = str(p.get(campo) or "").strip()
        if not valor:
            continue
        for parte in _RE_SEPARADORES_NUMEROS.split(valor):
            if not parte or not parte.strip():
                continue
            r = normalizar_telefono(parte, pais, es_whatsapp=es_wa)
            estados.append(r["estado"])
            if r["estado"] == "valido" and r["e164"] not in claves:
                claves.append(r["e164"])
    if claves:
        estado = "valido"
    elif "ambiguo" in estados:
        estado = "ambiguo"
    elif estados:
        estado = "invalido"
    else:
        estado = "sin_telefono"
    return {"claves": claves, "estado": estado, "pais": pais}


def bandeja(p: dict) -> str:
    """'contactado' (confirmado por la persona), 'abierto' (se abrió WhatsApp) o 'pendiente'."""
    if p.get("fecha_contacto_confirmada") or (p.get("estado_comercial") or "") in ESTADOS_CONTACTADOS:
        return "contactado"
    if (p.get("bandeja_contacto") or "") == "abierto":
        return "abierto"
    return "pendiente"


def anotar_bandejas(prospectos: list) -> dict:
    """
    Calcula, para cada prospecto (por id), su bandeja y si debe ocultarse de Pendientes porque
    su número ya está en Abiertos/Contactados o ya aparece en otro pendiente. No modifica nada.
    """
    info = {}
    reclamados = {}  # número -> id del prospecto abierto/contactado que ya lo usa
    for p in sorted(prospectos, key=lambda x: x.get("id") or 0):
        c = claves_contacto(p)
        b = bandeja(p)
        info[p["id"]] = {
            "bandeja": b,
            "claves_contacto": c["claves"],
            "telefono_estado": c["estado"],
            "oculto_en_pendientes": False,
            "duplicado_de": None,
        }
        if b in ("abierto", "contactado"):
            for k in c["claves"]:
                reclamados.setdefault(k, p["id"])

    # Entre pendientes se muestra uno solo por número: primero el que ya tiene historial de
    # intentos (p. ej. el que regresaste a Pendientes) y luego el más antiguo.
    pendientes = [p for p in prospectos if info[p["id"]]["bandeja"] == "pendiente"]
    pendientes.sort(key=lambda x: (0 if int(x.get("intentos_whatsapp") or 0) > 0 else 1, x.get("id") or 0))
    vistos = {}
    for p in pendientes:
        datos = info[p["id"]]
        claves = datos["claves_contacto"]
        dueno = next((reclamados[k] for k in claves if k in reclamados), None)
        if dueno is None:
            dueno = next((vistos[k] for k in claves if k in vistos), None)
        if dueno is not None and dueno != p["id"]:
            datos["oculto_en_pendientes"] = True
            datos["duplicado_de"] = dueno
            continue
        for k in claves:
            vistos.setdefault(k, p["id"])
    return info
