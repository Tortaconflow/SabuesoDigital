import sqlite3
import json
import os
import re
from pathlib import Path
from datetime import datetime
import pandas as pd
from config import DATABASE_PATH, BASE_DIR, PROSPECTS_DB_FILE

def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
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
                    whatsapp_estado TEXT DEFAULT 'no_verificado', -- 'confirmado', 'declarado', 'no_verificado'
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

        # Check if table 'negocios' has records; if not, migrate legacy data
        cursor.execute("SELECT COUNT(*) FROM negocios")
        count = cursor.fetchone()[0]
        if count == 0:
            migrate_legacy_data(conn)

import unicodedata

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
    # 1. Migrate from prospectos_current.json
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

                cursor.execute("""
                    INSERT INTO negocios (
                        nombre, sector, municipio, direccion, web, redes_sociales,
                        fuente_descubrimiento, prioridad, estado_comercial, puntuacion,
                        problemas_detectados, mensaje_personalizado, mensaje_calido,
                        mensaje_seguimiento, checks_json
                    ) VALUES (?, ?, ?, ?, ?, ?, 'legacy_json', ?, ?, ?, ?, ?, ?, ?, ?)
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

                # Create baseline activity record
                cursor.execute("""
                    INSERT INTO actividad_comercial (negocio_id, primer_contacto_fecha)
                    VALUES (?, NULL)
                """, (negocio_id,))
            conn.commit()
        except Exception as e:
            print(f"[DB] Error migrando legacy json: {e}")

# Helper CRUD
def get_all_negocios(filter_status=None, filter_priority=None, search_term=None, sort_col="id", sort_dir="desc"):
    valid_cols = {"id", "nombre", "puntuacion", "prioridad", "estado_comercial", "fecha_investigacion"}
    if sort_col not in valid_cols:
        sort_col = "id"
    sort_dir_clean = "DESC" if sort_dir.lower() == "desc" else "ASC"

    query = """
        SELECT n.*, c.telefono, c.whatsapp, c.whatsapp_estado, c.email,
               a.fecha_contacto_confirmada, a.canal, a.respuesta, a.siguiente_accion,
               a.fecha_seguimiento, a.propuesta_enviada, a.venta_acordada, a.ingreso_cobrado
        FROM negocios n
        LEFT JOIN contactos c ON c.negocio_id = n.id
        LEFT JOIN actividad_comercial a ON a.negocio_id = n.id
        WHERE 1=1
    """
    params = []

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
            SELECT n.*, c.telefono, c.whatsapp, c.whatsapp_estado, c.email,
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

        cursor.execute("SELECT * FROM evidencias WHERE negocio_id = ? ORDER BY id DESC", (negocio_id,))
        evidencias = [dict(e) for e in cursor.fetchall()]
        negocio["evidencias"] = evidencias
        return negocio

def save_or_update_negocio(data):
    negocio_id = data.get("id")
    with get_db() as conn:
        cursor = conn.cursor()
        checks_str = json.dumps(data.get("checks", {})) if isinstance(data.get("checks"), dict) else data.get("checks_json", "{}")
        prioridad = normalize_priority(data.get("prioridad") or data.get("Prioridad"))
        estado = normalize_status(data.get("estado_comercial") or data.get("Estado comercial"))

        if negocio_id:
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
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                data.get("nombre") or data.get("Nombre del negocio"),
                data.get("sector"),
                data.get("municipio") or data.get("Ubicación"),
                data.get("direccion"),
                data.get("web") or data.get("Web"),
                data.get("redes_sociales") or data.get("Redes sociales"),
                prioridad,
                estado,
                data.get("puntuacion") if data.get("puntuacion") is not None else data.get("Puntuación"),
                data.get("problemas_detectados") or data.get("Problemas detectados"),
                data.get("mensaje_personalizado") or data.get("Mensaje personalizado"),
                data.get("mensaje_calido") or data.get("Mensaje calido"),
                data.get("mensaje_seguimiento") or data.get("Mensaje seguimiento"),
                checks_str,
                data.get("es_favorito"),
                data.get("notas"),
                negocio_id
            ))
        else:
            cursor.execute("""
                INSERT INTO negocios (
                    nombre, sector, municipio, direccion, web, redes_sociales,
                    fuente_descubrimiento, prioridad, estado_comercial, puntuacion,
                    problemas_detectados, mensaje_personalizado, mensaje_calido,
                    mensaje_seguimiento, checks_json, es_favorito, notas
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                data.get("notas", "")
            ))
            negocio_id = cursor.lastrowid

            # Create default contacts and activity records
            cursor.execute("""
                INSERT INTO contactos (negocio_id, telefono, whatsapp, email, url_origen)
                VALUES (?, ?, ?, ?, ?)
            """, (
                negocio_id,
                data.get("telefono") or data.get("Teléfono", ""),
                data.get("whatsapp") or data.get("WhatsApp", ""),
                data.get("email") or data.get("Email", ""),
                data.get("web") or data.get("Web", "")
            ))

            cursor.execute("INSERT INTO actividad_comercial (negocio_id) VALUES (?)", (negocio_id,))

        # Update contact record if provided
        tel = data.get("telefono") or data.get("Teléfono")
        wa = data.get("whatsapp") or data.get("WhatsApp")
        email = data.get("email") or data.get("Email")
        if tel is not None or wa is not None or email is not None:
            cursor.execute("""
                UPDATE contactos SET
                    telefono = COALESCE(?, telefono),
                    whatsapp = COALESCE(?, whatsapp),
                    email = COALESCE(?, email),
                    fecha_comprobacion = CURRENT_TIMESTAMP
                WHERE negocio_id = ?
            """, (tel, wa, email, negocio_id))

        # Update CRM activity record if provided
        crm_status = data.get("estado_comercial")
        resp = data.get("respuesta")
        siguiente = data.get("siguiente_accion")
        fecha_seg = data.get("fecha_seguimiento")
        prop_env = data.get("propuesta_enviada")
        prop_monto = data.get("propuesta_monto")
        vta_acordada = data.get("venta_acordada")
        vta_monto = data.get("venta_monto")
        ing_cobrado = data.get("ingreso_cobrado")

        if any(x is not None for x in [crm_status, resp, siguiente, fecha_seg, prop_env, prop_monto, vta_acordada, vta_monto, ing_cobrado]):
            cursor.execute("""
                UPDATE actividad_comercial SET
                    respuesta = COALESCE(?, respuesta),
                    siguiente_accion = COALESCE(?, siguiente_accion),
                    fecha_seguimiento = COALESCE(?, fecha_seguimiento),
                    propuesta_enviada = COALESCE(?, propuesta_enviada),
                    propuesta_monto = COALESCE(?, propuesta_monto),
                    venta_acordada = COALESCE(?, venta_acordada),
                    venta_monto = COALESCE(?, venta_monto),
                    ingreso_cobrado = COALESCE(?, ingreso_cobrado)
                WHERE negocio_id = ?
            """, (resp, siguiente, fecha_seg, prop_env, prop_monto, vta_acordada, vta_monto, ing_cobrado, negocio_id))

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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM negocios")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM negocios WHERE estado_comercial = 'investigado'")
        investigados = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM evidencias WHERE estado_comercial = 'PENDIENTE_REVISION'" if False else "SELECT COUNT(*) FROM evidencias WHERE estado_comprobacion = 'PENDIENTE_REVISION'")
        pendientes_verificacion = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM negocios WHERE prioridad = 'critical'")
        criticos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM negocios WHERE estado_comercial = 'auditado'")
        auditados = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM negocios WHERE estado_comercial = 'contactado'")
        contactados = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM actividad_comercial WHERE respuesta != '' AND respuesta IS NOT NULL")
        respuestas = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM negocios WHERE estado_comercial = 'interesado'")
        interesados = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM actividad_comercial WHERE fecha_seguimiento >= DATE('now')")
        seguimientos_pendientes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM actividad_comercial WHERE propuesta_enviada = 1")
        propuestas_enviadas = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM actividad_comercial WHERE venta_acordada = 1")
        ventas_confirmadas = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(ingreso_cobrado) FROM actividad_comercial")
        row = cursor.fetchone()
        ingresos_cobrados = float(row[0]) if row and row[0] is not None else 0.0

        return {
            "total": total,
            "investigados": investigados,
            "pendientes_verificacion": pendientes_verificacion,
            "criticos": criticos,
            "auditados": auditados,
            "contactados": contactados,
            "respuestas": respuestas,
            "interesados": interesados,
            "seguimientos_pendientes": seguimientos_pendientes,
            "propuestas_enviadas": propuestas_enviadas,
            "ventas_confirmadas": ventas_confirmadas,
            "ingresos_cobrados": ingresos_cobrados
        }

def find_potential_duplicates():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, web, municipio FROM negocios
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

def export_db_to_df():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
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
                a.fecha_contacto_confirmada as "Fecha de contacto",
                a.canal as "Canal de contacto",
                a.respuesta as "Respuesta del cliente",
                a.propuesta_enviada as "Propuesta enviada",
                a.venta_acordada as "Venta acordada",
                a.ingreso_cobrado as "Ingreso cobrado",
                n.mensaje_personalizado as "Mensaje frío",
                n.mensaje_calido as "Mensaje cálido",
                n.mensaje_seguimiento as "Mensaje seguimiento"
            FROM negocios n
            LEFT JOIN contactos c ON c.negocio_id = n.id
            LEFT JOIN actividad_comercial a ON a.negocio_id = n.id
            ORDER BY n.puntuacion DESC, n.id DESC
        """)
        rows = cursor.fetchall()
        data = [dict(r) for r in rows]
        return pd.DataFrame(data)

# Run initialization upon module load
init_db()
