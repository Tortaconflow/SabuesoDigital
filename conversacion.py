"""
Fase 2 — Conversación, memoria comercial y consentimiento (determinista, 0 tokens).

- Clasifica lo que responde un negocio o persona: automática, rechazo, corrección,
  retroalimentación, educativa, orientación, contratación, informativa o humana.
  Lo educativo se evalúa antes que lo comercial: aprender no convierte a nadie en prospecto.
  Solo «contratación» es oportunidad comercial. Siempre es una sugerencia que confirma una persona.
- Extrae memoria SOLO de lo que el prospecto escribió (necesidades, servicios rechazados o que
  quiere conservar, restricciones, prioridades). Nunca infiere presupuestos ni características.
- Un rechazo explícito cierra la prospección; solo se reabre con una nueva solicitud expresa.
- Seguimiento: uno solo, manual, desde el día 5 tras el primer contacto y solo sin respuesta humana.
- Recomienda recursos gratuitos pertinentes (CÍDIKS Comunidad y biblioteca externa revisada).
La versión de bolsillo (docs/motor.js) replica estas reglas; la prueba de paridad lo verifica.
"""
import re
from datetime import date, timedelta

import reglas as R

TIPOS_EXCLUYENTES = ("servicio_rechazado", "servicio_conservado")
_RE_CLAUSULAS = re.compile(r"[.;!?\n]+")
_RE_CORREO = re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+")
_RE_TELEFONO = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def redactar(texto: str, limite: int = 1000) -> str:
    """Minimiza datos personales antes de guardar: correos y teléfonos se reemplazan."""
    t = _RE_CORREO.sub("[correo]", str(texto or ""))
    t = _RE_TELEFONO.sub("[teléfono]", t)
    return t.strip()[:limite]


def _categoria(cid: str, r: dict, coincidencias: list) -> dict:
    cat = r["respuestas"]["categorias"][cid]
    return {
        "categoria": cid,
        "nombre": cat["nombre"],
        "coincidencias": coincidencias,
        "cuenta_como_respuesta": bool(cat["cuenta_como_respuesta"]),
        "oportunidad_comercial": bool(cat["oportunidad_comercial"]),
        "conversacion": cat["conversacion"],
        "cierra_prospeccion": bool(cat.get("cierra_prospeccion")),
        "pide_revision_identidad": bool(cat.get("pide_revision_identidad")),
        "registra_retroalimentacion": bool(cat.get("registra_retroalimentacion")),
        "recomienda_recursos": bool(cat.get("recomienda_recursos")),
    }


def clasificar_respuesta(texto: str, r=None):
    """Sugerencia de intención de la respuesta, o None si no hay texto."""
    r = r or R.cargar_reglas()
    comp = R.texto_comparable(texto)
    if not comp.strip():
        return None
    cfg = r["respuestas"]
    for cid in cfg["orden"]:
        coinc = [p for p in cfg["categorias"][cid]["patrones"] if R.contiene_frase(comp, p)]
        if coinc:
            return _categoria(cid, r, coinc)
    return _categoria(cfg["predeterminada"], r, [])


def info_categoria(cid: str, r=None):
    r = r or R.cargar_reglas()
    return _categoria(cid, r, []) if cid in r["respuestas"]["categorias"] else None


def extraer_memoria(texto: str, r=None) -> list:
    """Memoria literal por frase: servicio rechazado/conservado, necesidad, restricción, prioridad."""
    r = r or R.cargar_reglas()
    mem = r["memoria"]
    items, vistos = [], set()

    def agregar(tipo, servicio, frase):
        clave = (tipo, servicio, frase)
        if clave not in vistos:
            vistos.add(clave)
            items.append({"tipo": tipo, "servicio": servicio, "texto": frase, "fuente": "prospecto"})

    for clausula in _RE_CLAUSULAS.split(str(texto or "")):
        comp = R.texto_comparable(clausula)
        if not comp.strip():
            continue
        frase = clausula.strip()[:160]
        tiene = lambda lista: any(R.contiene_frase(comp, t) for t in lista)
        servicio = R.servicio_por_necesidad(clausula, r)
        rechaza = tiene(mem["rechazar"])
        if servicio:
            if rechaza:
                agregar("servicio_rechazado", servicio, frase)
            elif tiene(mem["conservar"]):
                agregar("servicio_conservado", servicio, frase)
            elif tiene(mem["necesidad"]):
                agregar("necesidad", servicio, frase)
        elif tiene(mem["necesidad"]) and not rechaza:
            agregar("necesidad", "", frase)
        if tiene(mem["restriccion"]):
            agregar("restriccion", "", frase)
        if tiene(mem["prioridad"]):
            agregar("prioridad", "", frase)
    return items


def memoria_efectiva(p: dict, r=None) -> dict:
    """Combina la memoria guardada con la extraída de la última respuesta, por jerarquía de fuentes."""
    r = r or R.cargar_reglas()
    guardada = [m for m in (p.get("memoria") or []) if int(1 if m.get("vigente") is None else m.get("vigente")) == 1]
    claves = {(m.get("tipo"), m.get("servicio") or "") for m in guardada}
    derivada = [m for m in extraer_memoria(p.get("respuesta") or "", r) if (m["tipo"], m["servicio"]) not in claves]
    jerarquia = r["memoria"]["jerarquia_fuentes"]
    rango = lambda m: jerarquia.index(m.get("fuente")) if m.get("fuente") in jerarquia else len(jerarquia)
    todas = sorted(guardada + derivada, key=rango)
    excluidos = []
    for m in todas:
        if m.get("tipo") in TIPOS_EXCLUYENTES and m.get("servicio") and m["servicio"] not in excluidos:
            excluidos.append(m["servicio"])
    necesidades = []
    for m in todas:
        s = m.get("servicio") or ""
        if m.get("tipo") == "necesidad" and s and s not in excluidos and s not in necesidades:
            necesidades.append(s)
    textos = lambda tipo: [m.get("texto") or "" for m in todas if m.get("tipo") == tipo]
    return {
        "necesidades": necesidades,
        "excluidos": excluidos,
        "necesidades_sin_servicio": [m.get("texto") or "" for m in todas if m.get("tipo") == "necesidad" and not m.get("servicio")],
        "restricciones": textos("restriccion"),
        "prioridades": textos("prioridad"),
        "items": todas,
    }


def ultima_clasificacion(p: dict, r=None):
    """Clasificación confirmada por una persona; si no la hay, la sugerida de la última respuesta."""
    confirmada = (p.get("ultima_clasificacion") or "").strip()
    if confirmada:
        return confirmada
    res = clasificar_respuesta(p.get("respuesta") or "", r)
    return res["categoria"] if res else ""


def estado_prospeccion(p: dict, r=None) -> dict:
    if int(p.get("prospeccion_cerrada") or 0) == 1:
        return {"cerrada": True, "motivo": p.get("cierre_motivo") or "Rechazo explícito del negocio."}
    if int(p.get("prospeccion_reabierta") or 0) == 1:
        return {"cerrada": False, "motivo": ""}
    if (p.get("estado_comercial") or "") == "no_interesa":
        return {"cerrada": True, "motivo": "Marcado como «No le interesa»."}
    if ultima_clasificacion(p, r) == "rechazo":
        return {"cerrada": True, "motivo": "El negocio respondió con un rechazo explícito."}
    return {"cerrada": False, "motivo": ""}


def _hoy(p: dict, hoy=None) -> str:
    return (hoy or p.get("_hoy") or date.today().isoformat())[:10]


def estado_seguimiento(p: dict, hoy=None, r=None) -> dict:
    """Seguimiento único y manual: solo sin respuesta humana, sin rechazo y desde el día mínimo."""
    r = r or R.cargar_reglas()
    cfg = r["seguimiento"]
    if estado_prospeccion(p, r)["cerrada"]:
        return {"permitido": False, "motivo": "Prospección cerrada: no se envían seguimientos.", "desde": ""}
    contactos = int(p.get("contactos_confirmados_n") or 0) or (1 if p.get("fecha_contacto_confirmada") else 0)
    base = str(p.get("primer_contacto_fecha") or p.get("fecha_contacto_confirmada") or "")[:10]
    if not contactos or not base:
        return {"permitido": False, "motivo": "Aún no hay un primer contacto confirmado.", "desde": ""}
    cat = ultima_clasificacion(p, r)
    info = info_categoria(cat, r) if cat else None
    if info and info["cuenta_como_respuesta"]:
        return {"permitido": False, "motivo": "Conversación activa: responde personalmente a lo que escribieron.", "desde": ""}
    if contactos > cfg["maximo"]:
        return {"permitido": False, "motivo": "Ya se envió el único seguimiento permitido.", "desde": ""}
    try:
        inicio = date.fromisoformat(base)
    except ValueError:
        return {"permitido": False, "motivo": "La fecha del primer contacto no es válida.", "desde": ""}
    desde = (inicio + timedelta(days=cfg["dias_minimos"])).isoformat()
    hasta = (inicio + timedelta(days=cfg["dias_sugeridos_hasta"])).isoformat()
    if _hoy(p, hoy) < desde:
        return {"permitido": False, "motivo": f"Disponible a partir del {desde}.", "desde": desde}
    return {"permitido": True, "motivo": f"Seguimiento único permitido (sugerido entre el {desde} y el {hasta}).", "desde": desde}


def recursos_sugeridos(intencion: str, servicios=None, hoy=None, maximo: int = 2, r=None, texto: str = "") -> list:
    """Recursos gratuitos vigentes y pertinentes; los externos solo si coinciden con el tema o con lo que se pidió."""
    r = r or R.cargar_reglas()
    hoy = (hoy or date.today().isoformat())[:10]
    servicios = [s for s in (servicios or []) if s]
    comp = R.texto_comparable(texto) if texto else ""
    candidatos = []
    for i, rec in enumerate(r["recursos_gratuitos"]):
        if rec["revisar_antes"] < hoy:
            continue
        if intencion and intencion not in rec["intenciones"]:
            continue
        coincide = len(set(servicios) & set(rec["temas"]))
        if comp and any(R.contiene_frase(comp, f) for f in rec.get("palabras", [])):
            coincide += 1
        if (servicios or coincide) and not coincide and rec["origen"] != "cidiks":
            continue
        candidatos.append(((coincide, 1 if rec["origen"] == "cidiks" else 0, -i), rec))
    candidatos.sort(key=lambda x: x[0], reverse=True)
    return [rec for _, rec in candidatos[:maximo]]


def respuesta_sugerida(categoria: str, p: dict, recursos: list, r=None) -> str:
    """Borrador breve para que una persona lo revise; vacío si no corresponde o falta el recurso."""
    r = r or R.cargar_reglas()
    cat = r["respuestas"]["categorias"].get(categoria)
    if not cat or not cat["respuesta_sugerida"]:
        return ""
    plantilla = cat["respuesta_sugerida"]
    if "{recurso}" in plantilla:
        if not recursos:
            return ""
        plantilla = R.rellenar(plantilla, recurso=f"{recursos[0]['titulo']} {recursos[0]['url']}")
    return R.rellenar(plantilla, nombre=p.get("nombre") or "")


def analizar_respuesta(texto: str, p: dict, hoy=None, r=None) -> dict:
    """Todo lo que una persona necesita para confirmar una respuesta recibida (nada se guarda aquí)."""
    r = r or R.cargar_reglas()
    clasif = clasificar_respuesta(texto, r)
    memoria = extraer_memoria(texto, r)
    servicios = [m["servicio"] for m in memoria if m["tipo"] == "necesidad" and m["servicio"]]
    servicios += [s for s in memoria_efectiva(p, r)["necesidades"] if s not in servicios]
    recursos = recursos_sugeridos(clasif["categoria"], servicios, hoy, r=r, texto=texto) if clasif and clasif["recomienda_recursos"] else []
    return {
        "clasificacion": clasif,
        "memoria": memoria,
        "recursos": recursos,
        "respuesta_sugerida": respuesta_sugerida(clasif["categoria"], p, recursos, r) if clasif else "",
        "texto_guardado": redactar(texto),
    }


TIPOS_MEMORIA = ("necesidad", "servicio_rechazado", "servicio_conservado", "restriccion", "prioridad")


def sanear_memoria(items, r=None) -> list:
    """Solo tipos conocidos, servicios existentes y texto corto redactado. Fuente: prospecto o humano."""
    r = r or R.cargar_reglas()
    limpios = []
    for m in items or []:
        if not isinstance(m, dict) or m.get("tipo") not in TIPOS_MEMORIA:
            continue
        servicio = m.get("servicio") or ""
        if servicio and servicio not in r["servicios"]:
            continue
        fuente = m.get("fuente") if m.get("fuente") in ("prospecto", "humano") else "prospecto"
        limpios.append({"tipo": m["tipo"], "servicio": servicio, "texto": redactar(m.get("texto") or "", 200), "fuente": fuente})
    return limpios[:20]


def sanear_recursos(ids, r=None) -> list:
    r = r or R.cargar_reglas()
    validos = {rec["id"] for rec in r["recursos_gratuitos"]}
    return [i for i in (ids or []) if isinstance(i, str) and i in validos][:5]
