"""
Sincronización Sabueso PC <-> Sabueso Móvil (iPhone), sin internet ni servidores externos.

Flujo:
  1. PC -> Celular: `build_mobile_export()` genera un archivo JSON con los prospectos activos
     y la lista de eventos del celular que la PC ya aplicó (acuse de recibo).
  2. Celular -> PC: el celular genera un archivo de "avances" con eventos (contactos confirmados,
     respuestas, propuestas, ventas, cobros, notas y prospectos nuevos). `apply_mobile_events()`
     los valida y aplica uno por uno de forma idempotente: un evento con el mismo UUID nunca
     se aplica dos veces, aunque el archivo se importe varias veces.

Reglas CÍDIKS que se respetan aquí:
  - El estado 'contactado' solo llega por un evento `contacto_confirmado` (confirmación humana),
    nunca por una actualización genérica.
  - Los prospectos bloqueados (NO_CONTACTAR / INVESTIGAR_MAS) exigen nota, igual que en la PC.
  - Los prospectos nuevos que parecen duplicados NO se fusionan: se registran en
    `duplicados_candidatos` para revisión humana.
  - Una venta acordada nunca incrementa el ingreso cobrado.
"""
import json
import re
from datetime import datetime

import db
import validacion

EXPORT_FORMAT = "sabueso-movil"
AVANCES_FORMAT = "sabueso-movil-avances"
FORMAT_VERSION = 1

MAX_EVENTS = 5000
MAX_TEXT = 2000
MAX_MESSAGE = 5000

EVENT_TYPES = {"nuevo_prospecto", "contacto_confirmado", "actualizacion", "nota", "whatsapp_abierto", "regresar_pendientes", "revision_identidad"}
CANALES = {"whatsapp", "llamada", "email", "redes", "persona"}
ESTADOS_ACTUALIZABLES = {"investigado", "auditado", "interesado", "no_interesa", "propuesta", "ganado", "descartado"}
FUENTES = {"maps", "facebook", "instagram", "persona", "recomendacion", "web", "otro"}

_UUID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_UID_PC_RE = re.compile(r"^pc-(\d{1,12})$")
_UID_MOVIL_RE = re.compile(r"^m-[A-Za-z0-9-]{8,64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

EXPORT_FIELDS = (
    "id", "nombre", "sector", "municipio", "web", "redes_sociales",
    "telefono", "whatsapp", "whatsapp_estado", "email",
    "puntuacion", "prioridad", "estado_comercial", "problemas_detectados",
    "observacion_verificada", "hipotesis_comercial", "pregunta_comercial",
    "servicio_sugerido", "identidad_verificada",
    "mensaje_personalizado", "mensaje_calido", "mensaje_seguimiento", "mensaje_aprobado",
    "notas", "fecha_contacto_confirmada", "canal", "respuesta", "necesidad_expresada",
    "siguiente_accion", "fecha_seguimiento", "propuesta_enviada", "propuesta_monto",
    "venta_acordada", "venta_monto", "ingreso_cobrado", "movil_uid",
    "bandeja_contacto", "intentos_whatsapp", "ultimo_intento_whatsapp", "identidad_revisada_firma",
)


class EventoInvalido(ValueError):
    pass


# =========================================================
# PC -> CELULAR
# =========================================================

def build_mobile_export() -> dict:
    """Genera el paquete JSON que el celular importa (solo prospectos fuera de cuarentena)."""
    negocios = db.get_all_negocios(sort_col="puntuacion", sort_dir="desc")
    indice = validacion.indice_claves(negocios)
    prospectos = []
    for n in negocios:
        item = {}
        for field in EXPORT_FIELDS:
            val = n.get(field)
            item[field] = "" if val is None else val
        ident = validacion.analizar_identidad(n, indice=indice)
        item["revision_identidad"] = ident["hallazgos"]
        item["identidad_requiere_revision"] = ident["requiere_revision"]
        item["firma_identidad"] = ident["firma"]
        prospectos.append(item)

    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT evento_uuid FROM movil_sync WHERE resultado = 'aplicado'"
        ).fetchall()
    aplicados = [r["evento_uuid"] for r in rows]

    return {
        "formato": EXPORT_FORMAT,
        "version": FORMAT_VERSION,
        "generado_en": datetime.now().isoformat(timespec="seconds"),
        "total_prospectos": len(prospectos),
        "prospectos": prospectos,
        "eventos_aplicados": aplicados,
    }


# =========================================================
# CELULAR -> PC
# =========================================================

def _text(value, limit=MAX_TEXT, field="texto") -> str:
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)):
        raise EventoInvalido(f"El campo '{field}' debe ser texto.")
    s = str(value).strip()
    if len(s) > limit:
        raise EventoInvalido(f"El campo '{field}' excede {limit} caracteres.")
    return s


def _money(value, field) -> float:
    if value is None or value == "":
        return 0.0
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise EventoInvalido(f"El monto '{field}' no es un número válido.")
    if amount < 0 or amount > 1_000_000_000:
        raise EventoInvalido(f"El monto '{field}' está fuera de rango.")
    return round(amount, 2)


def _flag(value) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "true", "si", "sí", "yes") else 0
    return 1 if value else 0


def _event_date(value) -> str:
    s = _text(value, 40, "fecha")
    if not s:
        return datetime.now().isoformat(timespec="seconds")
    try:
        datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise EventoInvalido("La fecha del evento no tiene formato ISO válido.")
    return s


def _validate_envelope(payload) -> list:
    if not isinstance(payload, dict):
        raise EventoInvalido("El archivo no tiene el formato de avances de Sabueso Móvil.")
    if payload.get("formato") != AVANCES_FORMAT:
        raise EventoInvalido("Este archivo no es de avances de Sabueso Móvil (formato desconocido).")
    if payload.get("version") != FORMAT_VERSION:
        raise EventoInvalido(f"Versión de archivo no compatible: {payload.get('version')}.")
    eventos = payload.get("eventos")
    if not isinstance(eventos, list):
        raise EventoInvalido("El archivo no contiene una lista de eventos.")
    if len(eventos) > MAX_EVENTS:
        raise EventoInvalido(f"El archivo excede el máximo de {MAX_EVENTS} eventos.")
    return eventos


def count_pending_events(payload: dict) -> int:
    """Cuántos eventos del archivo aún no se han aplicado (para no respaldar en vano)."""
    eventos = _validate_envelope(payload)
    with db.get_db() as conn:
        aplicados = {
            r["evento_uuid"] for r in conn.execute(
                "SELECT evento_uuid FROM movil_sync WHERE resultado = 'aplicado'"
            ).fetchall()
        }
    return sum(1 for e in eventos if isinstance(e, dict) and str(e.get("id") or "") not in aplicados)


def _resolve_negocio_id(conn, uid: str):
    m = _UID_PC_RE.match(uid)
    if m:
        row = conn.execute(
            "SELECT id, en_cuarentena FROM negocios WHERE id = ?", (int(m.group(1)),)
        ).fetchone()
    elif _UID_MOVIL_RE.match(uid):
        row = conn.execute(
            "SELECT id, en_cuarentena FROM negocios WHERE movil_uid = ? AND movil_uid != ''", (uid,)
        ).fetchone()
    else:
        raise EventoInvalido(f"Identificador de prospecto inválido: {uid!r}.")
    if not row:
        raise EventoInvalido("El prospecto no existe en la PC (¿se creó en el celular y su alta no se ha importado?).")
    if row["en_cuarentena"]:
        raise EventoInvalido("El prospecto está en cuarentena en la PC; restáuralo antes de importar avances.")
    return row["id"]


def _digits(phone: str) -> str:
    d = re.sub(r"\D", "", phone or "")
    return d[-10:] if len(d) >= 10 else ""


def _clean_name(name: str) -> str:
    return re.sub(r"[^\w\s]", "", db.strip_accents(name or "")).strip()


def _register_duplicate_candidates(conn, nuevo_id: int, nombre: str, telefono: str, whatsapp: str) -> list:
    """Busca coincidencias y las deja pendientes de revisión humana (nunca fusiona)."""
    telefonos = {d for d in (_digits(telefono), _digits(whatsapp)) if d}
    nombre_limpio = _clean_name(nombre)
    rows = conn.execute("""
        SELECT n.id, n.nombre, c.telefono, c.whatsapp
        FROM negocios n LEFT JOIN contactos c ON c.negocio_id = n.id
        WHERE n.id != ? AND COALESCE(n.en_cuarentena, 0) = 0
    """, (nuevo_id,)).fetchall()

    encontrados = []
    for r in rows:
        motivos = []
        similitud = 0.0
        tel_existentes = {d for d in (_digits(r["telefono"]), _digits(r["whatsapp"])) if d}
        if telefonos & tel_existentes:
            motivos.append("Mismo teléfono / WhatsApp")
            similitud += 0.8
        if nombre_limpio and nombre_limpio == _clean_name(r["nombre"]):
            motivos.append("Mismo nombre comercial exacto")
            similitud += 0.7
        if motivos:
            conn.execute("""
                INSERT INTO duplicados_candidatos (negocio_a_id, negocio_b_id, motivo_coincidencia, similitud, estado)
                VALUES (?, ?, ?, ?, 'pendiente')
            """, (r["id"], nuevo_id, "; ".join(motivos) + " (alta desde Sabueso Móvil)", min(similitud, 1.0)))
            encontrados.append({"existente_id": r["id"], "existente_nombre": r["nombre"], "motivos": motivos})
    return encontrados


def _apply_nuevo_prospecto(uid: str, datos: dict, fecha: str) -> dict:
    if not _UID_MOVIL_RE.match(uid):
        raise EventoInvalido("Un prospecto nuevo del celular debe tener identificador 'm-...'.")
    nombre = _text(datos.get("nombre"), 200, "nombre")
    if not nombre:
        raise EventoInvalido("El prospecto nuevo no tiene nombre.")

    with db.get_db() as conn:
        existing = conn.execute("SELECT id FROM negocios WHERE movil_uid = ?", (uid,)).fetchone()
    if existing:
        return {"negocio_id": existing["id"], "ya_existia": True, "duplicados": []}

    fuente = _text(datos.get("fuente"), 30, "fuente").lower()
    if fuente not in FUENTES:
        fuente = "otro"
    wa_estado = _text(datos.get("whatsapp_estado"), 30, "whatsapp_estado")
    if wa_estado not in ("confirmado", "no_verificado"):
        wa_estado = "no_verificado"
    identidad = _flag(datos.get("identidad_verificada"))
    servicio = _text(datos.get("servicio_sugerido"), 40, "servicio_sugerido") or "catalogos"
    if not identidad:
        servicio = "no_contactar"

    web = _text(datos.get("web"), 500, "web")
    if web and not re.match(r"^https?://", web, re.IGNORECASE):
        web = "https://" + web

    notas = _text(datos.get("notas"), MAX_TEXT, "notas")
    marca = f"[Alta desde Sabueso Móvil {fecha[:16].replace('T', ' ')} · fuente: {fuente}]"

    record = {
        "nombre": nombre,
        "sector": _text(datos.get("sector"), 120, "sector"),
        "municipio": _text(datos.get("municipio"), 120, "municipio"),
        "web": web,
        "redes_sociales": _text(datos.get("redes_sociales"), 500, "redes_sociales"),
        "telefono": _text(datos.get("telefono"), 40, "telefono"),
        "whatsapp": _text(datos.get("whatsapp"), 40, "whatsapp"),
        "whatsapp_estado": wa_estado,
        "email": _text(datos.get("email"), 200, "email"),
        "fuente_descubrimiento": f"movil_{fuente}",
        "prioridad": "medium",
        "estado_comercial": "investigado",
        "servicio_sugerido": servicio,
        "identidad_verificada": identidad,
        "mensaje_personalizado": _text(datos.get("mensaje_personalizado"), MAX_MESSAGE, "mensaje_personalizado"),
        "mensaje_calido": _text(datos.get("mensaje_calido"), MAX_MESSAGE, "mensaje_calido"),
        "mensaje_seguimiento": _text(datos.get("mensaje_seguimiento"), MAX_MESSAGE, "mensaje_seguimiento"),
        "notas": f"{marca}\n{notas}".strip(),
    }
    created = db.save_or_update_negocio(record)
    nuevo_id = created["id"]

    with db.get_db() as conn:
        conn.execute("UPDATE negocios SET movil_uid = ? WHERE id = ?", (uid, nuevo_id))
        duplicados = _register_duplicate_candidates(
            conn, nuevo_id, nombre, record["telefono"], record["whatsapp"]
        )
        conn.commit()

    # La persona confirmó en el celular que los datos son de este negocio (revisión de identidad).
    firma = _text(datos.get("identidad_revisada_firma"), 16, "identidad_revisada_firma")
    if re.match(r"^[0-9a-f]{8}$", firma):
        db.record_identity_review(nuevo_id, firma, nota="Confirmado al darlo de alta en el celular", origen="movil", fecha=fecha)
    return {"negocio_id": nuevo_id, "ya_existia": False, "duplicados": duplicados}


def _apply_contacto(negocio_id: int, datos: dict, fecha: str):
    canal = _text(datos.get("canal"), 20, "canal").lower()
    if canal not in CANALES:
        raise EventoInvalido(f"Canal de contacto no válido: {canal!r}.")
    notas = _text(datos.get("notas"), MAX_TEXT, "notas")
    notas_marcadas = f"[Confirmado desde Sabueso Móvil] {notas}".strip()
    fecha_contacto = _event_date(datos.get("fecha") or fecha)
    # record_human_contact exige nota en prospectos bloqueados; se pasa la nota original
    # para no burlar esa regla con la marca automática.
    if not notas:
        with db.get_db() as conn:
            n = conn.execute(
                "SELECT servicio_sugerido, identidad_verificada FROM negocios WHERE id = ?", (negocio_id,)
            ).fetchone()
        if n and ((n["servicio_sugerido"] or "") in ("no_contactar", "investigar_mas") or n["identidad_verificada"] == 0):
            raise EventoInvalido("Prospecto bloqueado: se requiere una nota explicativa para registrar el contacto.")
    db.record_human_contact(negocio_id, canal, notas_marcadas, fecha_contacto=fecha_contacto)


def _apply_actualizacion(negocio_id: int, datos: dict):
    if not isinstance(datos, dict) or not datos:
        raise EventoInvalido("La actualización no contiene campos.")
    update = {"id": negocio_id}
    for key, value in datos.items():
        if key == "estado_comercial":
            estado = _text(value, 30, key)
            if estado == "contactado":
                raise EventoInvalido("El estado 'contactado' solo se registra con una confirmación de contacto.")
            if estado not in ESTADOS_ACTUALIZABLES:
                raise EventoInvalido(f"Estado comercial no válido: {estado!r}.")
            update[key] = estado
        elif key in ("respuesta", "necesidad_expresada", "siguiente_accion"):
            update[key] = _text(value, MAX_TEXT, key)
        elif key in ("mensaje_personalizado", "mensaje_calido", "mensaje_seguimiento"):
            update[key] = _text(value, MAX_MESSAGE, key)
        elif key == "fecha_seguimiento":
            fecha = _text(value, 10, key)
            if fecha and not _DATE_RE.match(fecha):
                raise EventoInvalido("La fecha de seguimiento debe tener formato AAAA-MM-DD.")
            update[key] = fecha
        elif key in ("propuesta_enviada", "venta_acordada"):
            update[key] = _flag(value)
        elif key in ("propuesta_monto", "venta_monto", "ingreso_cobrado"):
            update[key] = _money(value, key)
        else:
            raise EventoInvalido(f"Campo no permitido desde el celular: {key!r}.")
    db.save_or_update_negocio(update)


def _apply_nota(negocio_id: int, datos: dict, fecha: str):
    texto = _text(datos.get("texto"), MAX_TEXT, "texto")
    if not texto:
        raise EventoInvalido("La nota está vacía.")
    linea = f"[Celular {fecha[:16].replace('T', ' ')}] {texto}"
    with db.get_db() as conn:
        conn.execute("""
            UPDATE negocios SET
                notas = CASE WHEN COALESCE(notas, '') = '' THEN ? ELSE notas || char(10) || ? END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (linea, linea, negocio_id))
        conn.commit()


def _apply_whatsapp_abierto(negocio_id: int, datos: dict, fecha: str, evento_uuid: str):
    """Intento de WhatsApp hecho en el celular: mueve a Abiertos sin confirmar el envío."""
    tel = _text(datos.get("telefono_e164"), 20, "telefono_e164")
    if tel and not re.match(r"^\+\d{8,15}$", tel):
        raise EventoInvalido("El número del intento no está normalizado (+código de país).")
    mensaje = _text(datos.get("mensaje"), MAX_MESSAGE, "mensaje")
    with db.get_db() as conn:
        n = conn.execute(
            "SELECT servicio_sugerido, identidad_verificada FROM negocios WHERE id = ?", (negocio_id,)
        ).fetchone()
    if n and ((n["servicio_sugerido"] or "") in ("no_contactar", "investigar_mas") or n["identidad_verificada"] == 0):
        raise EventoInvalido("Prospecto bloqueado: no se registra apertura de WhatsApp.")
    db.register_whatsapp_open(negocio_id, tel, mensaje, origen="movil", fecha=fecha, evento_uuid=evento_uuid)


def _apply_revision_identidad(negocio_id: int, datos: dict, fecha: str):
    """Revisión humana hecha en el celular: confirma los datos que vio o corrige nombre/giro."""
    decision = _text(datos.get("decision"), 20, "decision")
    nota = _text(datos.get("nota"), MAX_TEXT, "nota")
    if decision not in ("confirmar", "corregir"):
        raise EventoInvalido("Decisión de revisión inválida.")
    if decision == "corregir":
        cambios = {"id": negocio_id}
        nombre = _text(datos.get("nombre"), 200, "nombre")
        sector = _text(datos.get("sector"), 120, "sector")
        if nombre:
            cambios["nombre"] = nombre
        if sector:
            cambios["sector"] = sector
        if len(cambios) == 1:
            raise EventoInvalido("La corrección no trae nombre ni giro.")
        db.save_or_update_negocio(cambios)
    detalle = db.get_negocio_detail(negocio_id)
    firma_actual = validacion.firma_identidad(detalle)
    firma_vista = _text(datos.get("firma_vista"), 16, "firma_vista")
    if decision == "confirmar" and firma_vista and firma_vista != firma_actual:
        raise EventoInvalido("Los datos del prospecto cambiaron en la PC después de exportarlos; vuelve a revisarlo con el archivo nuevo.")
    db.record_identity_review(negocio_id, firma_actual, nota=nota, origen="movil", fecha=fecha)


def _record_result(evento_uuid, tipo, uid, negocio_id, resultado, motivo, evento, fecha):
    with db.get_db() as conn:
        conn.execute("""
            INSERT INTO movil_sync (evento_uuid, tipo, prospecto_uid, negocio_id, resultado, motivo, payload_json, fecha_evento)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(evento_uuid) DO UPDATE SET
                negocio_id = excluded.negocio_id,
                resultado = excluded.resultado,
                motivo = excluded.motivo,
                payload_json = excluded.payload_json,
                aplicado_en = CURRENT_TIMESTAMP
        """, (evento_uuid, tipo, uid, negocio_id, resultado, motivo,
              json.dumps(evento, ensure_ascii=False)[:20000], fecha))
        conn.commit()


def apply_mobile_events(payload: dict) -> dict:
    """
    Aplica los eventos del celular en orden. Devuelve un resumen con aplicados, omitidos
    (ya aplicados antes) y errores por evento. Un error en un evento no detiene los demás.
    """
    eventos = _validate_envelope(payload)
    resumen = {
        "total": len(eventos),
        "aplicados": 0,
        "omitidos_ya_aplicados": 0,
        "errores": [],
        "prospectos_nuevos": [],
        "posibles_duplicados": [],
    }

    with db.get_db() as conn:
        ya_aplicados = {
            r["evento_uuid"] for r in conn.execute(
                "SELECT evento_uuid FROM movil_sync WHERE resultado = 'aplicado'"
            ).fetchall()
        }

    for idx, evento in enumerate(eventos):
        if not isinstance(evento, dict):
            resumen["errores"].append({"indice": idx, "motivo": "Evento con formato inválido."})
            continue
        evento_uuid = str(evento.get("id") or "")
        tipo = str(evento.get("tipo") or "")
        uid = str(evento.get("uid") or "")
        datos = evento.get("datos") if isinstance(evento.get("datos"), dict) else {}

        if not _UUID_RE.match(evento_uuid):
            resumen["errores"].append({"indice": idx, "motivo": "Evento sin identificador válido."})
            continue
        if evento_uuid in ya_aplicados:
            resumen["omitidos_ya_aplicados"] += 1
            continue

        negocio_id = None
        fecha = ""
        try:
            if tipo not in EVENT_TYPES:
                raise EventoInvalido(f"Tipo de evento desconocido: {tipo!r}.")
            fecha = _event_date(evento.get("fecha"))

            if tipo == "nuevo_prospecto":
                res = _apply_nuevo_prospecto(uid, datos, fecha)
                negocio_id = res["negocio_id"]
                if not res["ya_existia"]:
                    resumen["prospectos_nuevos"].append({"negocio_id": negocio_id, "nombre": datos.get("nombre", "")})
                resumen["posibles_duplicados"].extend(
                    [{"nuevo_id": negocio_id, **d} for d in res["duplicados"]]
                )
            else:
                with db.get_db() as conn:
                    negocio_id = _resolve_negocio_id(conn, uid)
                if tipo == "contacto_confirmado":
                    _apply_contacto(negocio_id, datos, fecha)
                elif tipo == "actualizacion":
                    _apply_actualizacion(negocio_id, datos)
                elif tipo == "nota":
                    _apply_nota(negocio_id, datos, fecha)
                elif tipo == "whatsapp_abierto":
                    _apply_whatsapp_abierto(negocio_id, datos, fecha, evento_uuid)
                elif tipo == "revision_identidad":
                    _apply_revision_identidad(negocio_id, datos, fecha)
                elif tipo == "regresar_pendientes":
                    db.return_to_pending(negocio_id, origen="movil", fecha=fecha, evento_uuid=evento_uuid)

            _record_result(evento_uuid, tipo, uid, negocio_id, "aplicado", "", evento, fecha)
            ya_aplicados.add(evento_uuid)
            resumen["aplicados"] += 1
        except (EventoInvalido, ValueError) as exc:
            motivo = str(exc)
            _record_result(evento_uuid, tipo or "desconocido", uid, negocio_id, "error", motivo, evento, fecha)
            resumen["errores"].append({
                "indice": idx,
                "evento": evento_uuid,
                "tipo": tipo,
                "prospecto": datos.get("nombre") or uid,
                "motivo": motivo,
            })

    return resumen
