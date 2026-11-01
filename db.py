import sqlite3
import contextlib
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path
from datetime import datetime
import pandas as pd
import config
from config import BASE_DIR, PROSPECTS_DB_FILE, BACKUPS_DIR

_INITIALIZED_DB_PATHS = set()


@contextlib.contextmanager
def _connect_raw(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def _ensure_column(cursor: sqlite3.Cursor, table: str, col_name: str, col_def: str):
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if col_name not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")


def init_db(target_path: Path = None):
    db_path = (target_path or config.get_database_path()).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect_raw(db_path) as conn:
        cursor = conn.cursor()

        # Migrations tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            );
        """)

        cursor.execute("SELECT MAX(version) FROM schema_migrations")
        row = cursor.fetchone()
        current_version = row[0] if row and row[0] is not None else 0

        if current_version < 1:
            # Migration 1: Core tables for Sabueso Digital 2.0 - CÍDIKS Sales Engine
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS negocios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    sector TEXT DEFAULT '',
                    municipio TEXT DEFAULT '',
                    direccion TEXT DEFAULT '',
                    web TEXT DEFAULT '',
                    redes_sociales TEXT DEFAULT '',
                    fuente_descubrimiento TEXT DEFAULT 'web',
                    fecha_investigacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    prioridad TEXT DEFAULT 'medium', -- 'critical', 'high', 'medium', 'low'
                    estado_comercial TEXT DEFAULT 'investigado', -- 'investigado', 'auditado', 'contactado', 'interesado', 'no_interesa', 'propuesta', 'ganado', 'descartado'
                    puntuacion INTEGER DEFAULT 0,
                    problemas_detectados TEXT DEFAULT '',
                    mensaje_personalizado TEXT DEFAULT '',
                    mensaje_calido TEXT DEFAULT '',
                    mensaje_seguimiento TEXT DEFAULT '',
                    checks_json TEXT DEFAULT '{}',
                    es_favorito INTEGER DEFAULT 0,
                    notas TEXT DEFAULT '',
                    en_cuarentena INTEGER DEFAULT 0,
                    motivo_cuarentena TEXT DEFAULT '',
                    fecha_cuarentena TIMESTAMP,
                    mensaje_aprobado INTEGER DEFAULT 0,
                    fecha_aprobacion_mensaje TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contactos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    negocio_id INTEGER NOT NULL,
                    telefono TEXT DEFAULT '',
                    whatsapp TEXT DEFAULT '',
                    whatsapp_estado TEXT DEFAULT 'no_verificado', -- 'confirmado', 'declarado', 'no_verificado', 'declarado_sin_numero'
                    email TEXT DEFAULT '',
                    url_origen TEXT DEFAULT '',
                    fecha_comprobacion TIMESTAMP,
                    estado_verificacion TEXT DEFAULT 'pendiente',
                    FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evidencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    negocio_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    tipo_observacion TEXT DEFAULT 'scraping_html', -- 'visual_playwright', 'scraping_html', 'regla_tecnica'
                    elemento_observado TEXT DEFAULT '',
                    contenido_visible_comprobado TEXT DEFAULT '',
                    hipotesis_necesidad TEXT DEFAULT '',
                    captura_path TEXT DEFAULT '',
                    estado_comprobacion TEXT DEFAULT 'PENDIENTE_REVISION', -- 'VERIFICADA_VISIBLE', 'PENDIENTE_REVISION', 'DESCARTADA', 'NO_VERIFICABLE'
                    revision_humana INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS actividad_comercial (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    negocio_id INTEGER NOT NULL,
                    primer_contacto_fecha TIMESTAMP,
                    fecha_contacto_confirmada TIMESTAMP,
                    canal TEXT DEFAULT '', -- 'whatsapp', 'email', 'llamada', 'redes'
                    respuesta TEXT DEFAULT '',
                    necesidad_expresada TEXT DEFAULT '',
                    siguiente_accion TEXT DEFAULT '',
                    fecha_seguimiento DATE,
                    propuesta_enviada INTEGER DEFAULT 0,
                    propuesta_monto REAL DEFAULT 0.0,
                    venta_acordada INTEGER DEFAULT 0,
                    venta_monto REAL DEFAULT 0.0,
                    ingreso_cobrado REAL DEFAULT 0.0,
                    notas TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS duplicados_candidatos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    negocio_a_id INTEGER NOT NULL,
                    negocio_b_id INTEGER NOT NULL,
                    motivo_coincidencia TEXT NOT NULL,
                    similitud REAL DEFAULT 0.0,
                    estado TEXT DEFAULT 'pendiente', -- 'pendiente', 'fusionado', 'rechazado'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                INSERT INTO schema_migrations (version, description)
                VALUES (1, 'Creación inicial de tablas CÍDIKS Sales Engine');
            """)
            conn.commit()

        # Asegurar columnas de Iteración 1 (cuarentena reversible y aprobación de mensaje) y bitácora
        _ensure_column(cursor, "negocios", "en_cuarentena", "INTEGER DEFAULT 0")
        _ensure_column(cursor, "negocios", "motivo_cuarentena", "TEXT DEFAULT ''")
        _ensure_column(cursor, "negocios", "fecha_cuarentena", "TIMESTAMP")
        _ensure_column(cursor, "negocios", "mensaje_aprobado", "INTEGER DEFAULT 0")
        _ensure_column(cursor, "negocios", "fecha_aprobacion_mensaje", "TIMESTAMP")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria_cambios_datos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tabla_afectada TEXT NOT NULL,
                registro_id INTEGER NOT NULL,
                negocio_id INTEGER NOT NULL,
                operacion TEXT NOT NULL,
                valores_anteriores_json TEXT NOT NULL,
                valores_nuevos_json TEXT NOT NULL,
                motivo TEXT NOT NULL,
                revertido INTEGER DEFAULT 0,
                reverted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

        # Migrar datos legacy solo si la tabla está vacía, NO estamos en entorno de pruebas
        # y no se deshabilitó explícitamente la migración legacy.
        if not config.is_test_environment() and os.environ.get("SABUESO_SKIP_LEGACY_MIGRATION") != "1":
            cursor.execute("SELECT COUNT(*) FROM negocios")
            count = cursor.fetchone()[0]
            if count == 0:
                migrate_legacy_data(conn)

    _INITIALIZED_DB_PATHS.add(str(db_path))


def get_db() -> sqlite3.Connection:
    db_path = config.get_database_path().resolve()
    if str(db_path) not in _INITIALIZED_DB_PATHS or not db_path.exists():
        init_db(db_path)
    return _connect_raw(db_path)


def strip_accents(text: str) -> str:
    if not text:
        return ""
    return unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8').lower()


def normalize_priority(val):
    if not val:
        return "medium"
    val_clean = strip_accents(val)
    if "crit" in val_clean:
        return "critical"
    if "alt" in val_clean or "high" in val_clean:
        return "high"
    if "med" in val_clean:
        return "medium"
    if "baj" in val_clean or "low" in val_clean:
        return "low"
    return "medium"


def normalize_status(val):
    if not val:
        return "investigado"
    val_clean = strip_accents(val)
    if "encontrado" in val_clean or "investigado" in val_clean:
        return "investigado"
    if "auditado" in val_clean:
        return "auditado"
    if "contactado" in val_clean:
        return "contactado"
    if "interesado" in val_clean:
        return "interesado"
    if "no interesa" in val_clean or "no_interesa" in val_clean:
        return "no_interesa"
    if "propuesta" in val_clean:
        return "propuesta"
    if "ganado" in val_clean or "cerrado" in val_clean or "venta" in val_clean:
        return "ganado"
    if "descartado" in val_clean:
        return "descartado"
    return "investigado"


def migrate_legacy_data(conn):
    cursor = conn.cursor()
    if os.path.exists(PROSPECTS_DB_FILE):
        try:
            with open(PROSPECTS_DB_FILE, "r", encoding="utf-8") as f:
                prospects = json.load(f)
            for p in prospects:
                nombre = p.get("Nombre del negocio", "").strip()
                if not nombre:
                    continue
                web = p.get("Web", "").strip()
                tel = p.get("Teléfono", "").strip()
                wa = p.get("WhatsApp", "").strip()
                email = p.get("Email", "").strip()
                redes = p.get("Redes sociales", "").strip()
                ubicacion = p.get("Ubicación", "").strip()
                prioridad = normalize_priority(p.get("Prioridad"))
                estado = normalize_status(p.get("Estado comercial"))
                score = int(p.get("Puntuación") or 0)
                problemas = p.get("Problemas detectados", "").strip()
                msg_pers = p.get("Mensaje personalizado", "").strip()
                msg_calido = p.get("Mensaje calido", "").strip()
                msg_seg = p.get("Mensaje seguimiento", "").strip()
                checks = json.dumps(p.get("checks", {}))

                # Regla Fase 3: Borradores importados/migrados NO se consideran mensajes aprobados (mensaje_aprobado = 0)
                cursor.execute("""
                    INSERT INTO negocios (
                        nombre, sector, municipio, direccion, web, redes_sociales,
                        fuente_descubrimiento, prioridad, estado_comercial, puntuacion,
                        problemas_detectados, mensaje_personalizado, mensaje_calido,
                        mensaje_seguimiento, checks_json, mensaje_aprobado
                    ) VALUES (?, ?, ?, ?, ?, ?, 'legacy_json', ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    nombre, "", ubicacion, ubicacion, web, redes,
                    prioridad, estado, score, problemas, msg_pers, msg_calido,
                    msg_seg, checks
                ))
                negocio_id = cursor.lastrowid

                if tel or wa or email:
                    cursor.execute("""
                        INSERT INTO contactos (
                            negocio_id, telefono, whatsapp, whatsapp_estado, email, url_origen
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        negocio_id, tel, wa,
                        'declarado' if wa else 'no_verificado',
                        email, web
                    ))

                cursor.execute("""
                    INSERT INTO actividad_comercial (negocio_id, primer_contacto_fecha)
                    VALUES (?, NULL)
                """, (negocio_id,))
            conn.commit()
        except Exception as e:
            print(f"[DB] Error migrando legacy json: {e}")


# =========================================================
# RESPALDO CONSISTENTE Y VERIFICACIÓN DE RESTAURACIÓN
# =========================================================

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def inspect_database_state(db_path: Path) -> dict:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ic = conn.execute("PRAGMA integrity_check;").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check;").fetchall()
    tables = ["schema_migrations", "negocios", "contactos", "actividad_comercial", "evidencias", "duplicados_candidatos"]
    counts = {}
    logical_hash = hashlib.sha256()
    for t in tables:
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()]
        counts[t] = len(rows)
        logical_hash.update(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    conn.close()
    return {
        "integrity_check": ic,
        "foreign_key_violations": len(fk),
        "table_counts": counts,
        "logical_sha256": logical_hash.hexdigest(),
        "file_sha256": _sha256_file(db_path),
        "size_bytes": db_path.stat().st_size
    }


def backup_and_verify_db(source_path: Path = None, label: str = "iter1") -> dict:
    """
    Crea un respaldo consistente mediante sqlite3.Connection.backup(),
    verifica PRAGMA integrity_check y foreign_key_check,
    prueba la restauración en una base temporal y guarda el manifiesto JSON.
    """
    src = (source_path or config.get_database_path()).resolve()
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_DIR / f"sabueso_cidiks_{label}_{ts}.db"
    temp_restore_path = BACKUPS_DIR / f"restore_verify_{label}_{ts}.db"
    manifest_path = BACKUPS_DIR / f"backup_manifest_{label}_{ts}.json"

    src_info = inspect_database_state(src)
    if src_info["integrity_check"] != "ok" or src_info["foreign_key_violations"] != 0:
        raise RuntimeError(f"La base origen falló la verificación de integridad: {src_info}")

    # 1. Respaldo consistente vía sqlite3.Connection.backup()
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    bkp_conn = sqlite3.connect(str(backup_path))
    with bkp_conn:
        src_conn.backup(bkp_conn, pages=0)
    bkp_conn.close()
    src_conn.close()

    bkp_info = inspect_database_state(backup_path)
    if bkp_info["integrity_check"] != "ok" or bkp_info["logical_sha256"] != src_info["logical_sha256"]:
        raise RuntimeError("El respaldo generado no coincide con la base de origen")

    # 2. Prueba de restauración en base temporal
    bkp_conn2 = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
    rst_conn = sqlite3.connect(str(temp_restore_path))
    with rst_conn:
        bkp_conn2.backup(rst_conn, pages=0)
    rst_conn.close()
    bkp_conn2.close()

    rst_info = inspect_database_state(temp_restore_path)
    temp_restore_path.unlink(missing_ok=True)

    if rst_info["integrity_check"] != "ok" or rst_info["logical_sha256"] != src_info["logical_sha256"]:
        raise RuntimeError("La prueba de restauración temporal falló la comprobación de registros")

    manifest = {
        "created_at": datetime.now().isoformat(),
        "label": label,
        "source_db_path": str(src),
        "backup_db_path": str(backup_path),
        "manifest_path": str(manifest_path),
        "source_verification": src_info,
        "backup_verification": bkp_info,
        "restore_test_verification": rst_info,
        "restore_test_status": "PASSED_100_PERCENT"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


# =========================================================
# CUARENTENA REVERSIBLE Y BITÁCORA DE AUDITORÍA (FASE 2)
# =========================================================

def quarantine_records(negocio_ids: list[int], motivo: str) -> dict:
    """
    Envía registros a cuarentena lógica y reversible sin ejecutar DELETE.
    Conserva contactos, actividades, evidencias y notas, y guarda bitácora en auditoria_cambios_datos.
    """
    if not negocio_ids:
        return {"quarantined_ids": [], "count": 0}
    if not motivo or not motivo.strip():
        raise ValueError("Se requiere un motivo explícito para poner registros en cuarentena.")

    now = datetime.now().isoformat()
    quarantined = []

    with get_db() as conn:
        cursor = conn.cursor()
        for nid in negocio_ids:
            cursor.execute("SELECT * FROM negocios WHERE id = ?", (nid,))
            row = cursor.fetchone()
            if not row:
                continue
            prev_data = dict(row)
            if prev_data.get("en_cuarentena") == 1:
                quarantined.append(nid)
                continue

            cursor.execute("""
                UPDATE negocios SET
                    en_cuarentena = 1,
                    motivo_cuarentena = ?,
                    fecha_cuarentena = ?
                WHERE id = ?
            """, (motivo.strip(), now, nid))

            new_data = dict(prev_data)
            new_data["en_cuarentena"] = 1
            new_data["motivo_cuarentena"] = motivo.strip()
            new_data["fecha_cuarentena"] = now

            cursor.execute("""
                INSERT INTO auditoria_cambios_datos (
                    tabla_afectada, registro_id, negocio_id, operacion,
                    valores_anteriores_json, valores_nuevos_json, motivo
                ) VALUES ('negocios', ?, ?, 'CUARENTENA', ?, ?, ?)
            """, (
                nid, nid,
                json.dumps({
                    "en_cuarentena": prev_data.get("en_cuarentena", 0),
                    "motivo_cuarentena": prev_data.get("motivo_cuarentena", ""),
                    "fecha_cuarentena": prev_data.get("fecha_cuarentena")
                }, ensure_ascii=False),
                json.dumps({
                    "en_cuarentena": 1,
                    "motivo_cuarentena": motivo.strip(),
                    "fecha_cuarentena": now
                }, ensure_ascii=False),
                motivo.strip()
            ))
            quarantined.append(nid)
        conn.commit()

    return {"quarantined_ids": quarantined, "count": len(quarantined), "quarantined_count": len(quarantined), "fecha_cuarentena": now}


def restore_quarantined_records(negocio_ids: list[int], motivo: str = "Restauración desde cuarentena", motivo_restauracion: str = None) -> dict:
    """Restaura registros en cuarentena devolviéndolos al estado activo."""
    if not negocio_ids:
        return {"restored_ids": [], "count": 0, "restored_count": 0}

    motivo_final = motivo_restauracion or motivo
    now = datetime.now().isoformat()
    restored = []

    with get_db() as conn:
        cursor = conn.cursor()
        for nid in negocio_ids:
            cursor.execute("SELECT * FROM negocios WHERE id = ?", (nid,))
            row = cursor.fetchone()
            if not row:
                continue
            prev_data = dict(row)
            if prev_data.get("en_cuarentena", 0) == 0:
                continue

            cursor.execute("""
                UPDATE negocios SET
                    en_cuarentena = 0,
                    motivo_cuarentena = '',
                    fecha_cuarentena = NULL
                WHERE id = ?
            """, (nid,))

            cursor.execute("""
                INSERT INTO auditoria_cambios_datos (
                    tabla_afectada, registro_id, negocio_id, operacion,
                    valores_anteriores_json, valores_nuevos_json, motivo
                ) VALUES ('negocios', ?, ?, 'RESTAURACION_CUARENTENA', ?, ?, ?)
            """, (
                nid, nid,
                json.dumps({
                    "en_cuarentena": prev_data.get("en_cuarentena"),
                    "motivo_cuarentena": prev_data.get("motivo_cuarentena"),
                    "fecha_cuarentena": prev_data.get("fecha_cuarentena")
                }, ensure_ascii=False),
                json.dumps({
                    "en_cuarentena": 0,
                    "motivo_cuarentena": "",
                    "fecha_cuarentena": None
                }, ensure_ascii=False),
                motivo_final
            ))
            restored.append(nid)
        conn.commit()

    return {"restored_ids": restored, "count": len(restored), "restored_count": len(restored), "restored_at": now}


def get_quarantined_records() -> list[dict]:
    """Consulta todos los registros actualmente en cuarentena junto con sus contactos y actividades."""
    return get_all_negocios(only_quarantine=True)


def sanitize_contact_record(negocio_id: int, updated_fields: dict = None, motivo: str = "", updates: dict = None) -> dict:
    """
    Corrige campos de contacto inválidos conservando los valores anteriores
    en la bitácora auditoria_cambios_datos para permitir restauración exacta.
    """
    fields_src = updated_fields if updated_fields is not None else (updates or {})
    allowed_fields = {"telefono", "whatsapp", "whatsapp_estado", "email", "estado_verificacion"}
    clean_updates = {k: v for k, v in fields_src.items() if k in allowed_fields}
    if not clean_updates:
        raise ValueError("No se proporcionaron campos de contacto válidos para actualizar.")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contactos WHERE negocio_id = ?", (negocio_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"No existe registro en 'contactos' para negocio_id={negocio_id}")

        prev_contact = dict(row)
        contacto_id = prev_contact["id"]

        prev_subset = {k: prev_contact.get(k) for k in clean_updates.keys()}
        set_clause = ", ".join([f"{k} = ?" for k in clean_updates.keys()])
        params = list(clean_updates.values()) + [contacto_id]

        cursor.execute(f"UPDATE contactos SET {set_clause} WHERE id = ?", params)

        cursor.execute("""
            INSERT INTO auditoria_cambios_datos (
                tabla_afectada, registro_id, negocio_id, operacion,
                valores_anteriores_json, valores_nuevos_json, motivo
            ) VALUES ('contactos', ?, ?, 'SANEAMIENTO_CONTACTO', ?, ?, ?)
        """, (
            contacto_id,
            negocio_id,
            json.dumps(prev_subset, ensure_ascii=False),
            json.dumps(clean_updates, ensure_ascii=False),
            motivo
        ))
        audit_id = cursor.lastrowid
        conn.commit()

        cursor.execute("SELECT * FROM contactos WHERE id = ?", (contacto_id,))
        updated_contact = dict(cursor.fetchone())
        return {
            "audit_id": audit_id,
            "negocio_id": negocio_id,
            "contacto_id": contacto_id,
            "changes_logged": len(clean_updates),
            "valores_anteriores": prev_subset,
            "valores_nuevos": clean_updates,
            "contacto_actual": updated_contact
        }


def restore_audit_change(audit_id: int) -> dict:
    """Restaura un cambio registrado en auditoria_cambios_datos a sus valores originales."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM auditoria_cambios_datos WHERE id = ?", (audit_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Registro de auditoría {audit_id} no encontrado")

        audit_entry = dict(row)
        tabla = audit_entry["tabla_afectada"]
        reg_id = audit_entry["registro_id"]
        prev_vals = json.loads(audit_entry["valores_anteriores_json"])

        if tabla not in ("contactos", "negocios"):
            raise ValueError(f"Restauración automática no soportada para tabla: {tabla}")

        set_clause = ", ".join([f"{k} = ?" for k in prev_vals.keys()])
        params = list(prev_vals.values()) + [reg_id]
        cursor.execute(f"UPDATE {tabla} SET {set_clause} WHERE id = ?", params)

        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE auditoria_cambios_datos
            SET revertido = 1, reverted_at = ?
            WHERE id = ?
        """, (now, audit_id))
        conn.commit()
        return {"restored": True, "audit_id": audit_id, "tabla": tabla, "registro_id": reg_id, "restored_values": prev_vals}


def get_audit_log(negocio_id: int = None) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        if negocio_id is not None:
            cursor.execute("SELECT * FROM auditoria_cambios_datos WHERE negocio_id = ? ORDER BY id DESC", (negocio_id,))
        else:
            cursor.execute("SELECT * FROM auditoria_cambios_datos ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]


# =========================================================
# CRUD DE NEGOCIOS Y ACTIVIDAD COMERCIAL (FASE 3)
# =========================================================

def get_all_negocios(
    filter_status=None,
    filter_priority=None,
    search_term=None,
    sort_col="id",
    sort_dir="desc",
    include_quarantine=False,
    only_quarantine=False
):
    valid_cols = {"id", "nombre", "puntuacion", "prioridad", "estado_comercial", "fecha_investigacion"}
    if sort_col not in valid_cols:
        sort_col = "id"
    sort_dir_clean = "DESC" if sort_dir.lower() == "desc" else "ASC"

    query = """
        SELECT n.*, c.telefono, c.whatsapp, c.whatsapp_estado, c.email, c.estado_verificacion,
               a.primer_contacto_fecha, a.fecha_contacto_confirmada, a.canal, a.respuesta,
               a.necesidad_expresada, a.siguiente_accion, a.fecha_seguimiento,
               a.propuesta_enviada, a.propuesta_monto, a.venta_acordada, a.venta_monto, a.ingreso_cobrado
        FROM negocios n
        LEFT JOIN contactos c ON c.negocio_id = n.id
        LEFT JOIN actividad_comercial a ON a.negocio_id = n.id
        WHERE 1=1
    """
    params = []

    if only_quarantine:
        query += " AND COALESCE(n.en_cuarentena, 0) = 1"
    elif not include_quarantine:
        query += " AND COALESCE(n.en_cuarentena, 0) = 0"

    if filter_status:
        query += " AND n.estado_comercial = ?"
        params.append(filter_status)

    if filter_priority:
        query += " AND n.prioridad = ?"
        params.append(filter_priority)

    if search_term:
        query += " AND (n.nombre LIKE ? OR n.web LIKE ? OR n.municipio LIKE ? OR n.sector LIKE ?)"
        like_term = f"%{search_term}%"
        params.extend([like_term, like_term, like_term, like_term])

    query += f" ORDER BY n.{sort_col} {sort_dir_clean}"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_negocio_detail(negocio_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT n.*, c.telefono, c.whatsapp, c.whatsapp_estado, c.email, c.estado_verificacion,
                   a.primer_contacto_fecha, a.fecha_contacto_confirmada, a.canal,
                   a.respuesta, a.necesidad_expresada, a.siguiente_accion, a.fecha_seguimiento,
                   a.propuesta_enviada, a.propuesta_monto, a.venta_acordada, a.venta_monto,
                   a.ingreso_cobrado, a.notas as notas_actividad
            FROM negocios n
            LEFT JOIN contactos c ON c.negocio_id = n.id
            LEFT JOIN actividad_comercial a ON a.negocio_id = n.id
            WHERE n.id = ?
        """, (negocio_id,))
        row = cursor.fetchone()
        if not row:
            return None
        negocio = dict(row)
        try:
            negocio["checks"] = json.loads(negocio.get("checks_json") or "{}")
        except Exception:
            negocio["checks"] = {}

        cursor.execute("SELECT * FROM evidencias WHERE negocio_id = ? ORDER BY id DESC", (negocio_id,))
        evidencias = [dict(e) for e in cursor.fetchall()]
        negocio["evidencias"] = evidencias
        return negocio


def save_or_update_negocio(data):
    """
    Crea o actualiza un negocio en SQLite.
    En actualizaciones parciales (cuando negocio_id existe), NUNCA sobrescribe
    prioridad, estado_comercial, puntuacion, checks_json ni otros campos que no
    hayan sido explícitamente incluidos en el diccionario `data`.
    """
    negocio_id = data.get("id")
    with get_db() as conn:
        cursor = conn.cursor()

        if negocio_id:
            # Resolver únicamente campos explícitamente enviados para no pisar con valores por defecto
            raw_prioridad = data.get("prioridad") if "prioridad" in data else data.get("Prioridad")
            prioridad_update = normalize_priority(raw_prioridad) if raw_prioridad is not None else None

            raw_estado = data.get("estado_comercial") if "estado_comercial" in data else data.get("Estado comercial")
            estado_update = normalize_status(raw_estado) if raw_estado is not None else None

            if "checks" in data and isinstance(data["checks"], dict):
                checks_update = json.dumps(data["checks"])
            elif "checks_json" in data and data["checks_json"] is not None:
                checks_update = data["checks_json"]
            else:
                checks_update = None

            if "puntuacion" in data and data["puntuacion"] is not None:
                puntuacion_update = int(data["puntuacion"])
            elif "Puntuación" in data and data["Puntuación"] is not None:
                puntuacion_update = int(data["Puntuación"])
            else:
                puntuacion_update = None

            mensaje_aprobado_update = int(bool(data["mensaje_aprobado"])) if "mensaje_aprobado" in data and data["mensaje_aprobado"] is not None else None
            fecha_aprobacion_update = datetime.now().isoformat() if mensaje_aprobado_update == 1 else None

            nombre_update = data.get("nombre") if "nombre" in data else data.get("Nombre del negocio")
            municipio_update = data.get("municipio") if "municipio" in data else data.get("Ubicación")
            web_update = data.get("web") if "web" in data else data.get("Web")
            redes_update = data.get("redes_sociales") if "redes_sociales" in data else data.get("Redes sociales")
            prob_update = data.get("problemas_detectados") if "problemas_detectados" in data else data.get("Problemas detectados")
            msg_pers_update = data.get("mensaje_personalizado") if "mensaje_personalizado" in data else data.get("Mensaje personalizado")
            msg_cal_update = data.get("mensaje_calido") if "mensaje_calido" in data else data.get("Mensaje calido")
            msg_seg_update = data.get("mensaje_seguimiento") if "mensaje_seguimiento" in data else data.get("Mensaje seguimiento")

            cursor.execute("""
                UPDATE negocios SET
                    nombre = COALESCE(?, nombre),
                    sector = COALESCE(?, sector),
                    municipio = COALESCE(?, municipio),
                    direccion = COALESCE(?, direccion),
                    web = COALESCE(?, web),
                    redes_sociales = COALESCE(?, redes_sociales),
                    prioridad = COALESCE(?, prioridad),
                    estado_comercial = COALESCE(?, estado_comercial),
                    puntuacion = COALESCE(?, puntuacion),
                    problemas_detectados = COALESCE(?, problemas_detectados),
                    mensaje_personalizado = COALESCE(?, mensaje_personalizado),
                    mensaje_calido = COALESCE(?, mensaje_calido),
                    mensaje_seguimiento = COALESCE(?, mensaje_seguimiento),
                    checks_json = COALESCE(?, checks_json),
                    es_favorito = COALESCE(?, es_favorito),
                    notas = COALESCE(?, notas),
                    mensaje_aprobado = COALESCE(?, mensaje_aprobado),
                    fecha_aprobacion_mensaje = CASE
                        WHEN ? = 1 THEN COALESCE(?, fecha_aprobacion_mensaje)
                        WHEN ? = 0 THEN NULL
                        ELSE fecha_aprobacion_mensaje
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                nombre_update,
                data.get("sector") if "sector" in data else None,
                municipio_update,
                data.get("direccion") if "direccion" in data else None,
                web_update,
                redes_update,
                prioridad_update,
                estado_update,
                puntuacion_update,
                prob_update,
                msg_pers_update,
                msg_cal_update,
                msg_seg_update,
                checks_update,
                data.get("es_favorito") if "es_favorito" in data else None,
                data.get("notas") if "notas" in data else None,
                mensaje_aprobado_update,
                mensaje_aprobado_update,
                fecha_aprobacion_update,
                mensaje_aprobado_update,
                negocio_id
            ))
        else:
            # Creación de nuevo negocio (INSERT)
            checks_str = json.dumps(data.get("checks", {})) if isinstance(data.get("checks"), dict) else data.get("checks_json", "{}")
            prioridad = normalize_priority(data.get("prioridad") or data.get("Prioridad"))
            estado = normalize_status(data.get("estado_comercial") or data.get("Estado comercial"))
            mensaje_aprobado_init = int(bool(data.get("mensaje_aprobado", 0)))
            fecha_aprobacion_init = datetime.now().isoformat() if mensaje_aprobado_init == 1 else None

            cursor.execute("""
                INSERT INTO negocios (
                    nombre, sector, municipio, direccion, web, redes_sociales,
                    fuente_descubrimiento, prioridad, estado_comercial, puntuacion,
                    problemas_detectados, mensaje_personalizado, mensaje_calido,
                    mensaje_seguimiento, checks_json, es_favorito, notas,
                    mensaje_aprobado, fecha_aprobacion_mensaje
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("nombre") or data.get("Nombre del negocio", "Sin Nombre"),
                data.get("sector", ""),
                data.get("municipio") or data.get("Ubicación", ""),
                data.get("direccion", ""),
                data.get("web") or data.get("Web", ""),
                data.get("redes_sociales") or data.get("Redes sociales", ""),
                data.get("fuente_descubrimiento", "busqueda_web"),
                prioridad,
                estado,
                int(data.get("puntuacion") or data.get("Puntuación") or 0),
                data.get("problemas_detectados") or data.get("Problemas detectados", ""),
                data.get("mensaje_personalizado") or data.get("Mensaje personalizado", ""),
                data.get("mensaje_calido") or data.get("Mensaje calido", ""),
                data.get("mensaje_seguimiento") or data.get("Mensaje seguimiento", ""),
                checks_str,
                data.get("es_favorito", 0),
                data.get("notas", ""),
                mensaje_aprobado_init,
                fecha_aprobacion_init
            ))
            negocio_id = cursor.lastrowid

            wa_init = data.get("whatsapp") or data.get("WhatsApp", "")
            wa_estado_init = data.get("whatsapp_estado") or ("declarado" if wa_init else "no_verificado")

            cursor.execute("""
                INSERT INTO contactos (negocio_id, telefono, whatsapp, whatsapp_estado, email, url_origen)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                negocio_id,
                data.get("telefono") or data.get("Teléfono", ""),
                wa_init,
                wa_estado_init,
                data.get("email") or data.get("Email", ""),
                data.get("web") or data.get("Web", "")
            ))

            cursor.execute("INSERT INTO actividad_comercial (negocio_id) VALUES (?)", (negocio_id,))

        # Actualizar registro en 'contactos' solo si se proporcionaron campos de contacto explícitamente
        tel = data.get("telefono") if "telefono" in data else data.get("Teléfono")
        wa = data.get("whatsapp") if "whatsapp" in data else data.get("WhatsApp")
        wa_est = data.get("whatsapp_estado") if "whatsapp_estado" in data else None
        email = data.get("email") if "email" in data else data.get("Email")
        if any(x is not None for x in [tel, wa, wa_est, email]):
            cursor.execute("SELECT id FROM contactos WHERE negocio_id = ?", (negocio_id,))
            c_row = cursor.fetchone()
            if c_row:
                cursor.execute("""
                    UPDATE contactos SET
                        telefono = COALESCE(?, telefono),
                        whatsapp = COALESCE(?, whatsapp),
                        whatsapp_estado = COALESCE(?, whatsapp_estado),
                        email = COALESCE(?, email),
                        fecha_comprobacion = CURRENT_TIMESTAMP
                    WHERE negocio_id = ?
                """, (tel, wa, wa_est, email, negocio_id))
            else:
                cursor.execute("""
                    INSERT INTO contactos (negocio_id, telefono, whatsapp, whatsapp_estado, email, url_origen, fecha_comprobacion)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    negocio_id,
                    tel or "",
                    wa or "",
                    wa_est or ("declarado" if wa else "no_verificado"),
                    email or "",
                    data.get("web") or ""
                ))

        # Actualizar registro en 'actividad_comercial' solo si se proporcionaron campos de actividad explícitamente
        # Regla Fase 3: venta_acordada NUNCA incrementa ingreso_cobrado automáticamente.
        resp = data.get("respuesta") if "respuesta" in data else None
        nec_exp = data.get("necesidad_expresada") if "necesidad_expresada" in data else None
        siguiente = data.get("siguiente_accion") if "siguiente_accion" in data else None
        fecha_seg = data.get("fecha_seguimiento") if "fecha_seguimiento" in data else None
        prop_env = int(bool(data["propuesta_enviada"])) if "propuesta_enviada" in data and data["propuesta_enviada"] is not None else None
        prop_monto = float(data["propuesta_monto"]) if "propuesta_monto" in data and data["propuesta_monto"] is not None else None
        vta_acordada = int(bool(data["venta_acordada"])) if "venta_acordada" in data and data["venta_acordada"] is not None else None
        vta_monto = float(data["venta_monto"]) if "venta_monto" in data and data["venta_monto"] is not None else None
        ing_cobrado = float(data["ingreso_cobrado"]) if "ingreso_cobrado" in data and data["ingreso_cobrado"] is not None else None

        if any(x is not None for x in [resp, nec_exp, siguiente, fecha_seg, prop_env, prop_monto, vta_acordada, vta_monto, ing_cobrado]):
            cursor.execute("""
                UPDATE actividad_comercial SET
                    respuesta = COALESCE(?, respuesta),
                    necesidad_expresada = COALESCE(?, necesidad_expresada),
                    siguiente_accion = COALESCE(?, siguiente_accion),
                    fecha_seguimiento = COALESCE(?, fecha_seguimiento),
                    propuesta_enviada = COALESCE(?, propuesta_enviada),
                    propuesta_monto = COALESCE(?, propuesta_monto),
                    venta_acordada = COALESCE(?, venta_acordada),
                    venta_monto = COALESCE(?, venta_monto),
                    ingreso_cobrado = COALESCE(?, ingreso_cobrado)
                WHERE negocio_id = ?
            """, (resp, nec_exp, siguiente, fecha_seg, prop_env, prop_monto, vta_acordada, vta_monto, ing_cobrado, negocio_id))

        conn.commit()
        return get_negocio_detail(negocio_id)


def add_evidencia(negocio_id, evidencia_data):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO evidencias (
                negocio_id, url, tipo_observacion, elemento_observado,
                contenido_visible_comprobado, hipotesis_necesidad, captura_path,
                estado_comprobacion, revision_humana
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            negocio_id,
            evidencia_data.get("url", ""),
            evidencia_data.get("tipo_observacion", "scraping_html"),
            evidencia_data.get("elemento_observado", ""),
            evidencia_data.get("contenido_visible_comprobado", ""),
            evidencia_data.get("hipotesis_necesidad", ""),
            evidencia_data.get("captura_path", ""),
            evidencia_data.get("estado_comprobacion", "PENDIENTE_REVISION"),
            evidencia_data.get("revision_humana", 0)
        ))
        evidencia_id = cursor.lastrowid
        conn.commit()
        return evidencia_id


def update_evidencia_estado(evidencia_id, nuevo_estado, revision_humana=1):
    valid_estados = {"VERIFICADA_VISIBLE", "PENDIENTE_REVISION", "DESCARTADA", "NO_VERIFICABLE"}
    if nuevo_estado not in valid_estados:
        raise ValueError(f"Estado de comprobación inválido: {nuevo_estado}")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE evidencias SET
                estado_comprobacion = ?,
                revision_humana = ?
            WHERE id = ?
        """, (nuevo_estado, revision_humana, evidencia_id))
        conn.commit()


def record_human_contact(negocio_id, canal, notas=""):
    """Registra contacto manual únicamente tras confirmación humana explícita."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE negocios SET estado_comercial = 'contactado', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (negocio_id,))
        cursor.execute("""
            UPDATE actividad_comercial SET
                fecha_contacto_confirmada = ?,
                primer_contacto_fecha = COALESCE(primer_contacto_fecha, ?),
                canal = ?,
                notas = CASE WHEN notas = '' THEN ? ELSE notas || '\n' || ? END
            WHERE negocio_id = ?
        """, (now, now, canal, notas, notas, negocio_id))
        conn.commit()


def get_dashboard_metrics():
    """
    Calcula las métricas del CRM separando rigurosamente cada etapa comercial
    y excluyendo cualquier registro en cuarentena (en_cuarentena = 1).
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Conteo de registros en cuarentena
        cursor.execute("SELECT COUNT(*) FROM negocios WHERE COALESCE(en_cuarentena, 0) = 1")
        en_cuarentena = cursor.fetchone()[0]

        # 1. Prospectos activos (fuera de cuarentena)
        cursor.execute("SELECT COUNT(*) FROM negocios n WHERE COALESCE(n.en_cuarentena, 0) = 0")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM negocios n WHERE COALESCE(n.en_cuarentena, 0) = 0 AND n.estado_comercial = 'investigado'")
        investigados = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM negocios n WHERE COALESCE(n.en_cuarentena, 0) = 0 AND n.estado_comercial = 'auditado'")
        auditados = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM negocios n WHERE COALESCE(n.en_cuarentena, 0) = 0 AND n.prioridad = 'critical'")
        criticos = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM evidencias e
            JOIN negocios n ON n.id = e.negocio_id
            WHERE COALESCE(n.en_cuarentena, 0) = 0 AND e.estado_comprobacion = 'PENDIENTE_REVISION'
        """)
        pendientes_verificacion = cursor.fetchone()[0]

        # 2. Mensajes generados (borradores) vs. Mensajes revisados y aprobados por el humano
        cursor.execute("""
            SELECT COUNT(*) FROM negocios n
            WHERE COALESCE(n.en_cuarentena, 0) = 0
              AND TRIM(COALESCE(n.mensaje_personalizado, '')) != ''
        """)
        mensajes_generados = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM negocios n
            WHERE COALESCE(n.en_cuarentena, 0) = 0
              AND COALESCE(n.mensaje_aprobado, 0) = 1
              AND TRIM(COALESCE(n.mensaje_personalizado, '')) != ''
        """)
        mensajes_aprobados = cursor.fetchone()[0]

        # 3. Contactos confirmados manualmente
        cursor.execute("""
            SELECT COUNT(*) FROM negocios n
            JOIN actividad_comercial a ON a.negocio_id = n.id
            WHERE COALESCE(n.en_cuarentena, 0) = 0
              AND a.fecha_contacto_confirmada IS NOT NULL
              AND TRIM(a.fecha_contacto_confirmada) != ''
        """)
        contactos_confirmados = cursor.fetchone()[0]

        # 4. Respuestas recibidas
        cursor.execute("""
            SELECT COUNT(*) FROM negocios n
            JOIN actividad_comercial a ON a.negocio_id = n.id
            WHERE COALESCE(n.en_cuarentena, 0) = 0
              AND TRIM(COALESCE(a.respuesta, '')) != ''
        """)
        respuestas_recibidas = cursor.fetchone()[0]

        # 5. Necesidades confirmadas (expresadas por el cliente)
        cursor.execute("""
            SELECT COUNT(*) FROM negocios n
            JOIN actividad_comercial a ON a.negocio_id = n.id
            WHERE COALESCE(n.en_cuarentena, 0) = 0
              AND TRIM(COALESCE(a.necesidad_expresada, '')) != ''
        """)
        necesidades_confirmadas = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM negocios n WHERE COALESCE(n.en_cuarentena, 0) = 0 AND n.estado_comercial = 'interesado'")
        interesados = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM negocios n
            JOIN actividad_comercial a ON a.negocio_id = n.id
            WHERE COALESCE(n.en_cuarentena, 0) = 0
              AND a.fecha_seguimiento IS NOT NULL
              AND TRIM(a.fecha_seguimiento) != ''
              AND a.fecha_seguimiento >= DATE('now')
        """)
        seguimientos_pendientes = cursor.fetchone()[0]

        # 6. Propuestas enviadas
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(a.propuesta_monto), 0.0)
            FROM negocios n
            JOIN actividad_comercial a ON a.negocio_id = n.id
            WHERE COALESCE(n.en_cuarentena, 0) = 0
              AND a.propuesta_enviada = 1
        """)
        prop_row = cursor.fetchone()
        propuestas_enviadas = prop_row[0] if prop_row else 0
        propuestas_monto_total = float(prop_row[1]) if prop_row and prop_row[1] is not None else 0.0

        # 7. Ventas acordadas (separadas de cobros)
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(a.venta_monto), 0.0)
            FROM negocios n
            JOIN actividad_comercial a ON a.negocio_id = n.id
            WHERE COALESCE(n.en_cuarentena, 0) = 0
              AND a.venta_acordada = 1
        """)
        vta_row = cursor.fetchone()
        ventas_acordadas = vta_row[0] if vta_row else 0
        ventas_acordadas_monto = float(vta_row[1]) if vta_row and vta_row[1] is not None else 0.0

        # 8. Ingreso efectivamente cobrado
        cursor.execute("""
            SELECT COALESCE(SUM(a.ingreso_cobrado), 0.0)
            FROM negocios n
            JOIN actividad_comercial a ON a.negocio_id = n.id
            WHERE COALESCE(n.en_cuarentena, 0) = 0
              AND a.ingreso_cobrado > 0
        """)
        row_ing = cursor.fetchone()
        ingresos_cobrados = float(row_ing[0]) if row_ing and row_ing[0] is not None else 0.0

        return {
            # Indicadores desglosados Fase 3
            "prospectos_investigados": total,
            "mensajes_generados": mensajes_generados,
            "mensajes_aprobados": mensajes_aprobados,
            "contactos_confirmados": contactos_confirmados,
            "respuestas_recibidas": respuestas_recibidas,
            "necesidades_confirmadas": necesidades_confirmadas,
            "propuestas_enviadas": propuestas_enviadas,
            "propuestas_monto_total": propuestas_monto_total,
            "ventas_acordadas": ventas_acordadas,
            "ventas_acordadas_monto": ventas_acordadas_monto,
            "ingresos_cobrados": ingresos_cobrados,
            "en_cuarentena": en_cuarentena,
            # Alias compatibles con vistas existentes
            "total": total,
            "investigados": investigados,
            "auditados": auditados,
            "criticos": criticos,
            "pendientes_verificacion": pendientes_verificacion,
            "contactados": contactos_confirmados,
            "respuestas": respuestas_recibidas,
            "interesados": interesados,
            "seguimientos_pendientes": seguimientos_pendientes,
            "ventas_confirmadas": ventas_acordadas
        }


def find_potential_duplicates():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, web, municipio FROM negocios
            WHERE COALESCE(en_cuarentena, 0) = 0
        """)
        negocios = [dict(r) for r in cursor.fetchall()]

    matches = []
    seen_pairs = set()

    def clean_name(n):
        return re.sub(r"[^\w\s]", "", n.lower()).strip()

    def clean_domain(u):
        if not u:
            return ""
        return u.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].lower()

    for i in range(len(negocios)):
        for j in range(i + 1, len(negocios)):
            n1 = negocios[i]
            n2 = negocios[j]
            pair_key = (min(n1["id"], n2["id"]), max(n1["id"], n2["id"]))
            if pair_key in seen_pairs:
                continue

            reasons = []
            score = 0.0

            dom1 = clean_domain(n1.get("web"))
            dom2 = clean_domain(n2.get("web"))
            if dom1 and dom2 and dom1 == dom2:
                reasons.append(f"Mismo dominio web: {dom1}")
                score += 0.8

            nom1 = clean_name(n1.get("nombre", ""))
            nom2 = clean_name(n2.get("nombre", ""))
            if nom1 and nom2:
                if nom1 == nom2:
                    reasons.append("Mismo nombre comercial exacto")
                    score += 0.7
                elif (nom1 in nom2 or nom2 in nom1) and len(nom1) > 4 and len(nom2) > 4:
                    reasons.append("Nombre comercial altamente similar")
                    score += 0.4

            if score >= 0.6:
                seen_pairs.add(pair_key)
                matches.append({
                    "negocio_a": n1,
                    "negocio_b": n2,
                    "motivos": reasons,
                    "similitud": round(min(score, 1.0), 2)
                })

    return matches


def export_db_to_df(include_quarantine: bool = False):
    where_clause = "" if include_quarantine else "WHERE COALESCE(n.en_cuarentena, 0) = 0"
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT 
                n.id as ID,
                n.nombre as "Nombre del negocio",
                n.sector as "Sector",
                n.municipio as "Ubicación",
                n.web as "Sitio Web",
                c.telefono as "Teléfono",
                c.whatsapp as "WhatsApp",
                c.whatsapp_estado as "Estado WhatsApp",
                c.email as "Email",
                n.redes_sociales as "Redes sociales",
                n.puntuacion as "Puntuación",
                n.prioridad as "Prioridad",
                n.estado_comercial as "Estado comercial",
                n.problemas_detectados as "Problemas detectados",
                n.mensaje_aprobado as "Mensaje aprobado",
                a.fecha_contacto_confirmada as "Fecha de contacto",
                a.canal as "Canal de contacto",
                a.respuesta as "Respuesta del cliente",
                a.necesidad_expresada as "Necesidad confirmada",
                a.propuesta_enviada as "Propuesta enviada",
                a.propuesta_monto as "Monto propuesta",
                a.venta_acordada as "Venta acordada",
                a.venta_monto as "Monto venta acordada",
                a.ingreso_cobrado as "Ingreso cobrado",
                n.mensaje_personalizado as "Mensaje frío",
                n.mensaje_calido as "Mensaje cálido",
                n.mensaje_seguimiento as "Mensaje seguimiento"
            FROM negocios n
            LEFT JOIN contactos c ON c.negocio_id = n.id
            LEFT JOIN actividad_comercial a ON a.negocio_id = n.id
            {where_clause}
            ORDER BY n.puntuacion DESC, n.id DESC
        """)
        rows = cursor.fetchall()
        data = [dict(r) for r in rows]
        return pd.DataFrame(data)
