import os
import re
import uuid
from datetime import datetime
import pandas as pd
from pathlib import Path
import db

COLUMN_SYNONYMS = {
    "nombre": ["nombre", "nombre del negocio", "negocio", "comercio", "empresa", "establecimiento", "cliente", "hotel"],
    "sector": ["sector", "categoria", "categoría", "giro", "tipo", "rubro"],
    "municipio": ["municipio", "ubicacion", "ubicación", "ciudad", "localidad", "zona", "estado", "direccion", "dirección"],
    "web": ["web", "sitio web", "sitio", "url", "pagina", "página", "link", "portal"],
    "telefono": ["telefono", "teléfono", "tel", "celular", "movil", "móvil", "contacto"],
    "whatsapp": ["whatsapp", "wa", "whats", "wa_link"],
    "email": ["email", "correo", "e-mail", "mail", "correo electrónico", "correo electronico"],
    "redes_sociales": ["redes", "redes sociales", "social", "facebook", "instagram", "redes_sociales"],
    "problemas": ["problemas", "problemas detectados", "observaciones", "notas", "comentarios", "detalle"],
    "prioridad": ["prioridad", "priority", "urgencia"],
    "puntuacion": ["puntuacion", "puntuación", "score", "calificacion", "calificación"]
}

def normalize_column_name(col: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", str(col).lower()).strip()
    for standard_name, synonyms in COLUMN_SYNONYMS.items():
        if cleaned in synonyms:
            return standard_name
        for syn in synonyms:
            if syn in cleaned:
                return standard_name
    return col

def clean_phone(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    s = str(val).split(".")[0].strip()
    digits = re.sub(r"\D", "", s)
    if len(digits) == 10:
        return f"+52 {digits[:3]} {digits[3:6]} {digits[6:]}"
    elif len(digits) == 12 and digits.startswith("52"):
        return f"+52 {digits[2:5]} {digits[5:8]} {digits[8:]}"
    return s if len(digits) >= 7 else ""

def clean_email(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", str(val))
    return emails[0] if emails else ""

def preview_file(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    if path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path)
    elif path.suffix.lower() in [".csv"]:
        try:
            df = pd.read_csv(file_path, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding="latin1")
    else:
        raise ValueError(f"Formato no compatible: {path.suffix}. Use .xlsx o .csv")

    raw_cols = list(df.columns)
    mapped_cols = {}
    for col in raw_cols:
        norm = normalize_column_name(col)
        mapped_cols[col] = norm

    # Analizar prospectos existentes para detección previa de duplicados
    existing_records = db.get_all_negocios()
    existing_domains = {r["web"].replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].lower() for r in existing_records if r.get("web")}
    existing_names = {re.sub(r"[^\w\s]", "", r["nombre"].lower()).strip() for r in existing_records if r.get("nombre")}

    sample_rows = []
    potential_duplicate_count = 0

    for idx, row in df.head(5).iterrows():
        sample = {}
        for col in raw_cols:
            val = row[col]
            sample[col] = "" if pd.isna(val) else str(val)
        sample_rows.append(sample)

    for _, row in df.iterrows():
        nombre_val = ""
        web_val = ""
        for raw_col, norm in mapped_cols.items():
            if norm == "nombre":
                nombre_val = str(row[raw_col]) if not pd.isna(row[raw_col]) else ""
            elif norm == "web":
                web_val = str(row[raw_col]) if not pd.isna(row[raw_col]) else ""

        dom = web_val.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].lower() if web_val else ""
        nom = re.sub(r"[^\w\s]", "", nombre_val.lower()).strip() if nombre_val else ""

        if (dom and dom in existing_domains) or (nom and nom in existing_names):
            potential_duplicate_count += 1

    return {
        "archivo": path.name,
        "total_filas": len(df),
        "columnas_originales": raw_cols,
        "mapeo_sugerido": mapped_cols,
        "filas_muestra": sample_rows,
        "posibles_duplicados": potential_duplicate_count
    }

def execute_import(file_path: str, column_mapping: dict = None) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    if path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path)
    else:
        try:
            df = pd.read_csv(file_path, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding="latin1")

    if not column_mapping:
        column_mapping = {col: normalize_column_name(col) for col in df.columns}

    batch_id = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    imported_ids = []
    skipped_count = 0

    for _, row in df.iterrows():
        record = {
            "nombre": "",
            "sector": "",
            "municipio": "",
            "web": "",
            "telefono": "",
            "whatsapp": "",
            "email": "",
            "redes_sociales": "",
            "problemas_detectados": "",
            "prioridad": "medium",
            "puntuacion": 0,
            "estado_comercial": "investigado",
            "fuente_descubrimiento": f"import_{path.name}"
        }

        for raw_col, val in row.items():
            if pd.isna(val):
                continue
            norm_target = column_mapping.get(raw_col)
            if not norm_target:
                continue

            val_str = str(val).strip()
            if norm_target == "nombre":
                record["nombre"] = val_str
            elif norm_target == "sector":
                record["sector"] = val_str
            elif norm_target == "municipio":
                record["municipio"] = val_str
            elif norm_target == "web":
                record["web"] = val_str if val_str.startswith("http") else f"https://{val_str}"
            elif norm_target == "telefono":
                record["telefono"] = clean_phone(val_str)
            elif norm_target == "whatsapp":
                record["whatsapp"] = clean_phone(val_str)
            elif norm_target == "email":
                record["email"] = clean_email(val_str)
            elif norm_target == "redes_sociales":
                record["redes_sociales"] = val_str
            elif norm_target == "problemas":
                record["problemas_detectados"] = val_str
            elif norm_target == "prioridad":
                record["prioridad"] = db.normalize_priority(val_str)
            elif norm_target == "puntuacion":
                try:
                    record["puntuacion"] = int(float(val_str))
                except Exception:
                    record["puntuacion"] = 0

        if not record["nombre"]:
            skipped_count += 1
            continue

        record["notas"] = f"Lote de importación: {batch_id} | Archivo origen: {path.name}"
        saved = db.save_or_update_negocio(record)
        negocio_id = saved["id"]
        imported_ids.append(negocio_id)

        # Regla irrenunciable: toda observación importada entra inicialmente como PENDIENTE_REVISION
        if record["problemas_detectados"]:
            db.add_evidencia(negocio_id, {
                "url": record["web"] or "sin_web",
                "tipo_observacion": "importacion_historica",
                "elemento_observado": "Observación importada de archivo histórico",
                "contenido_visible_comprobado": "",
                "hipotesis_necesidad": record["problemas_detectados"],
                "estado_comprobacion": "PENDIENTE_REVISION",
                "revision_humana": 0
            })

    return {
        "batch_id": batch_id,
        "archivo": path.name,
        "importados": len(imported_ids),
        "omitidos_sin_nombre": skipped_count,
        "negocios_ids": imported_ids
    }

def rollback_batch(batch_id: str) -> int:
    """Revierte una importación eliminando los registros de ese lote."""
    with db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM negocios WHERE notas LIKE ?", (f"%{batch_id}%",))
        rows = cursor.fetchall()
        ids_to_delete = [r[0] for r in rows]

        for nid in ids_to_delete:
            cursor.execute("DELETE FROM negocios WHERE id = ?", (nid,))
        conn.commit()
        return len(ids_to_delete)
