import sys
import os
import time
import re
import json
import urllib.parse
import socket
import ipaddress
import warnings
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
from flask_cors import CORS

from config import (
    BASE_DIR,
    FLASK_HOST,
    FLASK_PORT,
    FLASK_DEBUG,
    SECRET_KEY,
    GEMINI_API_KEY,
    SERPAPI_KEY,
    GOOGLE_MAPS_API_KEY,
    PROSPECTS_DB_FILE
)
import security
import db
import evidence_engine
import copilot
import importer

# Configuración de codificación y registro en log
try:
    if sys.stdout is None or not hasattr(sys.stdout, "write"):
        _log_f = open(BASE_DIR / "app.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = _log_f
        sys.stderr = _log_f
    elif getattr(sys.stdout, "encoding", None) != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Try to import duckduckgo_search
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    print("[WARN] duckduckgo_search no instalado. Usa: pip install duckduckgo-search")

app = Flask(
    __name__,
    static_folder=str(BASE_DIR / "static"),
    template_folder=str(BASE_DIR / "templates")
)
app.secret_key = SECRET_KEY

# Strict CORS: Only allow local loopback origins
CORS(app, origins=[
    f"http://127.0.0.1:{FLASK_PORT}",
    f"http://localhost:{FLASK_PORT}",
    "http://127.0.0.1",
    "http://localhost"
])

# Active backend configuration from config.py
CONFIG = {
    "gemini_api_key": GEMINI_API_KEY,
    "maps_api_key": GOOGLE_MAPS_API_KEY,
    "serpapi_key": SERPAPI_KEY
}

# Shared exclusion list for search engines
EXCLUSION_DOMAINS = [
    'yelp.', 'tripadvisor.', 'seccionamarilla.', 'google.com',
    'booking.com', 'expedia.', 'trivago.', 'hoteles.com',
    'kayak.', 'despegar.', 'bestday.', 'airbnb.', 'foursquare.',
    'twitter.com', 'youtube.com', 'pinterest.com', 'tiktok.com', 'github.com',
    'opentable.', 'michelin.', 'restaurantguru.', 'restaurant-guru.',
    'guiagastronomica.', 'zonaturistica.', 'viamichelin.', 'reservandolos.',
    'mexicodestinos.', 'directoriodehoteles.', 'paginasamarillas.',
    'cybo.com', 'all.biz', 'infobel.', 'hoteles-mexico.', 'inmobiliarias.',
    'guiaslocales.', 'mexicoenlasmanos.', 'habitamos.', 'mercadolibre.',
    'deturismo.', 'turismomexico.', 'dondeir.', 'timeout.', 'gastroactitud.',
    'wikipedia.org', 'amazon.com', 'gobiernodemexico.', 'gob.mx',
    'rae.es', 'wordreference.', 'thefreedictionary.', 'merriam-webster.',
    'dictionary.com', 'wiktionary.org', 'larousse.', 'collinsdictionary.',
    'oxfordlearnersdictionaries.', 'cambridge.org', 'reverso.net', 'linguee.',
    'significados.com', 'definicion.de', 'definicionyque.es',
    'conceptodefinicion.de', 'conceptos.de', 'lexico.com'
]

def normalize_phone(phone_str):
    if not phone_str:
        return ""
    phone_str = re.sub(r"\b20\d{2}\b", "", str(phone_str))
    cleaned = re.sub(r"[^\d\+\-\s()]", "", phone_str)
    cleaned = re.sub(r"[\s\-]+", " ", cleaned).strip()
    return cleaned

def clean_name_from_title(title, default_name):
    if not title:
        return default_name
    cleaned = title.strip()
    for sep in ["|", "-", "—", "•"]:
        if sep in cleaned:
            parts = cleaned.split(sep)
            candidate = parts[0].strip()
            if 3 <= len(candidate) <= 40:
                return candidate
    return default_name

def is_excluded_url(url):
    url_lower = url.lower()
    return any(exc in url_lower for exc in EXCLUSION_DOMAINS)

def url_to_business_name(url):
    dominio = url.split("//")[-1].split("/")[0].replace("www.", "")
    return dominio.split(".")[0].replace("-", " ").replace("_", " ").title()

def make_prospect_dict(name, url, location=""):
    is_soc = False
    soc_url = ""
    web_url = url
    for soc in ['facebook.com', 'instagram.com', 'linkedin.com']:
        if soc in url.lower():
            is_soc = True
            soc_url = url
            web_url = ""
            break

    return {
        "Nombre del negocio": name,
        "nombre": name,
        "Web": web_url,
        "web": web_url,
        "Teléfono": "",
        "telefono": "",
        "WhatsApp": "",
        "whatsapp": "",
        "Email": "",
        "email": "",
        "Redes sociales": soc_url,
        "redes_sociales": soc_url,
        "Ubicación": location,
        "municipio": location,
        "Calificación": "",
        "Reseñas": "",
        "Estado comercial": "investigado",
        "estado_comercial": "investigado",
        "Puntuación": 0,
        "puntuacion": 0,
        "Prioridad": "medium",
        "prioridad": "medium",
        "Problemas detectados": "Solo presencia en Redes Sociales (Sin Sitio Web)" if is_soc else "",
        "problemas_detectados": "Solo presencia en Redes Sociales (Sin Sitio Web)" if is_soc else "",
        "Mensaje personalizado": "",
        "mensaje_personalizado": "",
        "Mensaje calido": "",
        "mensaje_calido": "",
        "Mensaje seguimiento": "",
        "mensaje_seguimiento": "",
        "checks": {
            "ssl": False,
            "responsive": False,
            "speed": False,
            "whatsapp": False,
            "forms": False
        }
    }

# =============================================
# SEARCH ENGINES (Con protecciones y timeouts)
# =============================================

def search_serpapi(query, api_key, num_results=5, depth=1):
    import requests
    businesses = []
    start = (depth - 1) * 10
    response = requests.get("https://serpapi.com/search", params={
        "engine": "google",
        "q": query,
        "location": "Mexico",
        "api_key": api_key,
        "num": num_results * 2,
        "start": start,
        "gl": "mx",
        "hl": "es"
    }, timeout=15)

    if response.status_code != 200:
        raise Exception(f"SerpAPI HTTP {response.status_code}: {response.text[:200]}")

    data = response.json()
    organic = data.get("organic_results", [])
    raw_count = len(organic)

    for result in organic:
        if len(businesses) >= num_results:
            break
        url = result.get("link", "")
        if not url or is_excluded_url(url):
            continue

        title = result.get("title", "")
        name = title.split(" - ")[0].split(" | ")[0].strip() if title else url_to_business_name(url)
        if not name or len(name) < 2:
            name = url_to_business_name(url)

        businesses.append(make_prospect_dict(name, url))

    return businesses, raw_count

def search_ddg(query, num_results=5, depth=1):
    businesses = []
    if not DDGS_AVAILABLE:
        raise ImportError("duckduckgo_search no está instalado")

    with DDGS() as ddgs:
        results = list(ddgs.text(query + " sitio web contacto", max_results=num_results * depth * 4))
        raw_count = len(results)

        skip = (depth - 1) * num_results
        processed = 0

        for r in results:
            href = r.get("href", "")
            if not href or is_excluded_url(href):
                continue

            processed += 1
            if processed <= skip:
                continue

            if len(businesses) >= num_results:
                break

            name = clean_name_from_title(r.get("title", ""), url_to_business_name(href))
            if not name or len(name) < 2:
                name = url_to_business_name(href)

            businesses.append(make_prospect_dict(name, href))

    return businesses, raw_count

# =============================================
# WEBSITE AUDITING (Defensa contra SSRF y OOM)
# =============================================

def audit_and_scrape_website(url):
    data = {
        "url": url,
        "ssl_valid": True,
        "load_time_seconds": 0.0,
        "title": "",
        "meta_description": "",
        "has_whatsapp": False,
        "whatsapp_numeros": [],
        "emails": [],
        "telefonos": [],
        "redes_sociales": [],
        "has_forms": False,
        "is_responsive": False,
        "is_wordpress": False,
        "error": None
    }

    if not url:
        data["error"] = "Sin Sitio Web"
        return data

    # 1. Petición HTTP segura con security.safe_http_get (SSRF + límites)
    resp = security.safe_http_get(url)
    data["load_time_seconds"] = resp.get("total_time_seconds") or resp.get("load_time_seconds", 0.0)
    data["ssl_valid"] = resp.get("ssl_valid", True)

    if not resp.get("ok"):
        data["error"] = resp.get("error") or f"HTTP {resp.get('status_code', 0)}"
        return data

    text_content = resp.get("text", "")
    soup = BeautifulSoup(text_content, 'html.parser')

    # Remove script, style, and hidden tags before extracting visible contact info
    for hidden_tag in soup(["script", "style", "noscript", "svg", "path"]):
        hidden_tag.extract()

    visible_body_text = soup.get_text(" ", strip=True)

    if soup.title and soup.title.string:
        data["title"] = soup.title.string.strip()
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        data["meta_description"] = meta_desc.get("content").strip()

    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport:
        data["is_responsive"] = True

    if "wp-content" in text_content:
        data["is_wordpress"] = True

    forms = soup.find_all("form")
    if len(forms) > 0:
        data["has_forms"] = True

    # Redes sociales reales (excluyendo plugins/sharer)
    social_patterns = [
        r"facebook\.com/(?!sharer|tr|plugins|dialog)[a-zA-Z0-9_\-\.]+",
        r"instagram\.com/[a-zA-Z0-9_\-\.]+",
        r"linkedin\.com/company/[a-zA-Z0-9_\-\.]+"
    ]
    redes = []
    for pattern in social_patterns:
        found = re.findall(pattern, text_content, re.IGNORECASE)
        if found:
            redes.extend(found)
    data["redes_sociales"] = list(set(redes))

    # WhatsApp
    wa_links = re.findall(r"wa\.me/([0-9]+)", text_content)
    wa_api = re.findall(r"api\.whatsapp\.com/send\?phone=([0-9]+)", text_content)
    todos_wa = list(set(wa_links + wa_api))

    if todos_wa or "whatsapp" in text_content.lower():
        data["has_whatsapp"] = True
        data["whatsapp_numeros"] = todos_wa

    # Emails desde texto visible y mailto:
    emails_mailto = []
    for a in soup.find_all('a', href=True):
        if a['href'].startswith('mailto:'):
            clean_m = a['href'].replace('mailto:', '').split('?')[0].strip()
            if '@' in clean_m:
                emails_mailto.append(clean_m)

    emails_regex = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", visible_body_text)
    all_emails = [e for e in set(emails_mailto + emails_regex) if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.js', '.css'))]
    data["emails"] = all_emails[:3]

    # Teléfonos desde enlaces tel: y texto visible
    tels_found = []
    for a in soup.find_all('a', href=True):
        if a['href'].startswith('tel:'):
            clean_t = a['href'].replace('tel:', '').strip()
            tels_found.append(clean_t)

    tels_regex = re.findall(r"\+?[\d\-\s()]{8,15}", visible_body_text)
    for tel in tels_regex:
        digits = re.sub(r"\D", "", tel)
        if 8 <= len(digits) <= 12 and not digits.startswith("000"):
            tels_found.append(tel.strip())
    data["telefonos"] = list(set(tels_found))[:3]

    return data

# =============================================
# FLASK ROUTES
# =============================================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def api_status():
    gemini_ok = bool(CONFIG["gemini_api_key"])
    serpapi_ok = bool(CONFIG.get("serpapi_key"))
    maps_ok = bool(CONFIG.get("maps_api_key"))

    if serpapi_ok:
        search_engine = "SerpAPI (Premium)"
    elif maps_ok:
        search_engine = "Google Maps (Premium)"
    elif DDGS_AVAILABLE:
        search_engine = "DuckDuckGo (Gratis - Local)"
    else:
        search_engine = "Búsqueda Local"

    return jsonify({
        "gemini_configured": gemini_ok,
        "maps_configured": maps_ok,
        "serpapi_configured": serpapi_ok,
        "search_engine": search_engine,
        "search_configured": True,
        "gemini_status": "Conectado" if gemini_ok else "Modo reglas locales (Offline)",
        "maps_status": search_engine
    })

@app.route("/api/config", methods=["POST"])
def api_config():
    body = request.json or {}
    if "gemini_api_key" in body and body["gemini_api_key"].strip():
        CONFIG["gemini_api_key"] = body["gemini_api_key"].strip()
    if "maps_api_key" in body and body["maps_api_key"].strip():
        CONFIG["maps_api_key"] = body["maps_api_key"].strip()
    if "serpapi_key" in body and body["serpapi_key"].strip():
        CONFIG["serpapi_key"] = body["serpapi_key"].strip()
    return jsonify({"success": True})

@app.route("/api/metrics", methods=["GET"])
def api_metrics():
    metrics = db.get_dashboard_metrics()
    return jsonify(metrics)

@app.route("/api/prospects", methods=["GET"])
def api_prospects_get():
    status = request.args.get("status")
    priority = request.args.get("priority")
    search = request.args.get("search")
    sort_col = request.args.get("sort_col", "id")
    sort_dir = request.args.get("sort_dir", "desc")

    negocios = db.get_all_negocios(
        filter_status=status,
        filter_priority=priority,
        search_term=search,
        sort_col=sort_col,
        sort_dir=sort_dir
    )

    # Format into frontend-friendly response with normalized and display fields
    formatted = []
    for n in negocios:
        checks = {}
        try:
            checks = json.loads(n.get("checks_json") or "{}")
        except Exception:
            pass

        # Mapping for priority
        prioridad_norm = n.get("prioridad") or "medium"
        prioridad_label_map = {
            "critical": "Oportunidad crítica",
            "high": "Oportunidad alta",
            "medium": "Oportunidad media",
            "low": "Oportunidad baja"
        }
        prioridad_label = prioridad_label_map.get(prioridad_norm, "Oportunidad media")

        formatted.append({
            "id": n["id"],
            "Nombre del negocio": n["nombre"],
            "nombre": n["nombre"],
            "sector": n.get("sector", ""),
            "Web": n.get("web", ""),
            "web": n.get("web", ""),
            "Teléfono": n.get("telefono", ""),
            "telefono": n.get("telefono", ""),
            "WhatsApp": n.get("whatsapp", ""),
            "whatsapp": n.get("whatsapp", ""),
            "Email": n.get("email", ""),
            "email": n.get("email", ""),
            "Redes sociales": n.get("redes_sociales", ""),
            "redes_sociales": n.get("redes_sociales", ""),
            "Ubicación": n.get("municipio", ""),
            "municipio": n.get("municipio", ""),
            "Puntuación": n.get("puntuacion", 0),
            "puntuacion": n.get("puntuacion", 0),
            "Prioridad": prioridad_label,
            "prioridad": prioridad_norm,
            "Estado comercial": n.get("estado_comercial", "investigado"),
            "estado_comercial": n.get("estado_comercial", "investigado"),
            "Problemas detectados": n.get("problemas_detectados", ""),
            "problemas_detectados": n.get("problemas_detectados", ""),
            "Mensaje personalizado": n.get("mensaje_personalizado", ""),
            "mensaje_personalizado": n.get("mensaje_personalizado", ""),
            "Mensaje calido": n.get("mensaje_calido", ""),
            "mensaje_calido": n.get("mensaje_calido", ""),
            "Mensaje seguimiento": n.get("mensaje_seguimiento", ""),
            "mensaje_seguimiento": n.get("mensaje_seguimiento", ""),
            "checks": checks,
            "es_favorito": n.get("es_favorito", 0),
            "fecha_contacto_confirmada": n.get("fecha_contacto_confirmada"),
            "propuesta_enviada": n.get("propuesta_enviada", 0),
            "venta_acordada": n.get("venta_acordada", 0),
            "ingreso_cobrado": n.get("ingreso_cobrado", 0.0)
        })

    return jsonify(formatted)

@app.route("/api/prospects/<int:negocio_id>", methods=["GET"])
def api_prospect_detail(negocio_id):
    detail = db.get_negocio_detail(negocio_id)
    if not detail:
        return jsonify({"error": "Prospecto no encontrado"}), 404
    return jsonify(detail)

@app.route("/api/search", methods=["POST"])
def api_search():
    body = request.json or {}
    category = body.get("category", "").strip()
    location = body.get("location", "").strip()
    limit = int(body.get("limit", 5))
    depth = int(body.get("depth", 1))

    if not category or not location:
        return jsonify({"error": "Categoría y Ubicación son requeridas"}), 400

    query = f'"{category}" en "{location}" sitio web contacto'
    debug_info = {
        "query_ejecutada": query,
        "resultados_raw": 0,
        "resultados_filtrados": 0,
        "motor_usado": "",
        "error": None
    }

    businesses = []
    serpapi_key = CONFIG.get("serpapi_key", "")

    if serpapi_key:
        try:
            businesses, raw = search_serpapi(query, serpapi_key, limit, depth)
            debug_info["motor_usado"] = "serpapi"
            debug_info["resultados_raw"] = raw
        except Exception as e:
            debug_info["error"] = f"SerpAPI fallo: {str(e)}"

    if not businesses and DDGS_AVAILABLE:
        try:
            ddg_query = f"{category} en {location}"
            businesses, raw = search_ddg(ddg_query, limit, depth)
            debug_info["motor_usado"] = "duckduckgo"
            debug_info["resultados_raw"] = raw
        except Exception as e:
            debug_info["error"] = f"DuckDuckGo fallo: {str(e)}"

    debug_info["resultados_filtrados"] = len(businesses)

    # Guardar prospectos en SQLite y sync legacy
    saved_prospects = []
    for b in businesses:
        b["sector"] = category
        b["municipio"] = location
        saved = db.save_or_update_negocio(b)
        saved_prospects.append(saved)

    return jsonify({
        "prospects": saved_prospects,
        "debug_info": debug_info
    })

@app.route("/api/audit", methods=["POST"])
def api_audit():
    body = request.json or {}
    negocio_id = body.get("id")
    category = body.get("category", "")
    location = body.get("location", "")

    if not negocio_id:
        return jsonify({"error": "ID de prospecto requerido"}), 400

    prospect = db.get_negocio_detail(negocio_id)
    if not prospect:
        return jsonify({"error": "Prospecto no encontrado"}), 404

    url = prospect.get("web", "").strip()
    name = prospect.get("nombre", "Negocio Local")

    site_data = {"url": url}
    if url:
        site_data = audit_and_scrape_website(url)
    else:
        site_data["error"] = "Sin sitio web"

    # Generar mensajes con Copiloto ético CÍDIKS
    evidencias = prospect.get("evidencias", [])
    copilot_res = copilot.generate_cidiks_messages(
        prospect=site_data | {"nombre": name, "sector": category or prospect.get("sector", ""), "municipio": location or prospect.get("municipio", "")},
        evidencias=evidencias,
        use_ai=bool(CONFIG.get("gemini_api_key")),
        api_key=CONFIG.get("gemini_api_key")
    )

    # Calcular score y prioridad técnica
    score = 0
    problems = []
    if not url:
        score = 95
        priority = "critical"
        problems.append("No cuenta con un Sitio Web Oficial (depende de redes sociales)")
    else:
        if not site_data.get("ssl_valid", True):
            score += 30
            problems.append("Certificado SSL ausente o inválido")
        if not site_data.get("is_responsive", False):
            score += 25
            problems.append("No está optimizado para dispositivos móviles")
        if not site_data.get("has_whatsapp", False):
            score += 15
            problems.append("Carece de botón de WhatsApp directo")
        if not site_data.get("has_forms", False):
            score += 10
            problems.append("Sin formularios de consulta rápida")
        if site_data.get("load_time_seconds", 0) > 3.0:
            score += 20
            problems.append(f"Carga lenta ({site_data.get('load_time_seconds')}s)")

        score = min(max(score, 10), 100)
        if score >= 85:
            priority = "critical"
        elif score >= 65:
            priority = "high"
        elif score >= 45:
            priority = "medium"
        else:
            priority = "low"

    # Actualizar en SQLite
    updated_data = {
        "id": negocio_id,
        "nombre": name,
        "puntuacion": score,
        "prioridad": priority,
        "estado_comercial": "auditado",
        "problemas_detectados": ", ".join(problems) if problems else "Ningún problema técnico evidente",
        "mensaje_personalizado": copilot_res.get("mensaje_personalizado", ""),
        "mensaje_calido": copilot_res.get("mensaje_calido", ""),
        "mensaje_seguimiento": copilot_res.get("mensaje_seguimiento", ""),
        "checks": {
            "ssl": site_data.get("ssl_valid", False),
            "responsive": site_data.get("is_responsive", False),
            "speed": site_data.get("load_time_seconds", 0) < 2.5,
            "whatsapp": site_data.get("has_whatsapp", False),
            "forms": site_data.get("has_forms", False)
        }
    }

    if site_data.get("telefonos"):
        updated_data["telefono"] = ", ".join(site_data["telefonos"])
    if site_data.get("emails"):
        updated_data["email"] = ", ".join(site_data["emails"])
    if site_data.get("whatsapp_numeros"):
        updated_data["whatsapp"] = site_data["whatsapp_numeros"][0]

    updated_detail = db.save_or_update_negocio(updated_data)
    return jsonify(updated_detail)

@app.route("/api/audit/visual", methods=["POST"])
def api_audit_visual():
    body = request.json or {}
    negocio_id = body.get("id")
    text_to_verify = body.get("text_to_verify")

    if not negocio_id:
        return jsonify({"error": "ID de negocio requerido"}), 400

    prospect = db.get_negocio_detail(negocio_id)
    if not prospect or not prospect.get("web"):
        return jsonify({"error": "El prospecto no cuenta con sitio web para auditar visualmente"}), 400

    evidence = evidence_engine.capture_visual_evidence(
        url=prospect["web"],
        negocio_id=negocio_id,
        text_to_verify=text_to_verify
    )
    return jsonify(evidence)

@app.route("/api/prospects/update", methods=["POST"])
def api_prospects_update():
    body = request.json or {}
    negocio_data = body.get("prospect") or body
    if not negocio_data.get("id"):
        return jsonify({"error": "ID de prospecto requerido"}), 400

    updated = db.save_or_update_negocio(negocio_data)
    return jsonify({"success": True, "prospect": updated})

@app.route("/api/prospects/contact-confirm", methods=["POST"])
def api_contact_confirm():
    body = request.json or {}
    negocio_id = body.get("id")
    canal = body.get("canal", "manual")
    notas = body.get("notas", "")

    if not negocio_id:
        return jsonify({"error": "ID de prospecto requerido"}), 400

    db.record_human_contact(negocio_id, canal, notas)
    return jsonify({"success": True, "message": "Contacto confirmado manualmente"})

@app.route("/api/duplicates", methods=["GET"])
def api_duplicates():
    dups = db.find_potential_duplicates()
    return jsonify(dups)

@app.route("/api/import/preview", methods=["POST"])
def api_import_preview():
    body = request.json or {}
    filepath = body.get("filepath", "")
    if not filepath:
        return jsonify({"error": "Ruta de archivo requerida"}), 400

    try:
        preview = importer.preview_file(filepath)
        return jsonify(preview)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/import/execute", methods=["POST"])
def api_import_execute():
    body = request.json or {}
    filepath = body.get("filepath", "")
    mapping = body.get("mapping")

    if not filepath:
        return jsonify({"error": "Ruta de archivo requerida"}), 400

    try:
        res = importer.execute_import(filepath, mapping)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/import/rollback", methods=["POST"])
def api_import_rollback():
    body = request.json or {}
    batch_id = body.get("batch_id", "")
    if not batch_id:
        return jsonify({"error": "Batch ID requerido"}), 400

    deleted_count = importer.rollback_batch(batch_id)
    return jsonify({"success": True, "eliminados": deleted_count})

@app.route("/api/export", methods=["GET"])
def api_export():
    fmt = request.args.get("format", "csv").lower()
    df = db.export_db_to_df()

    if df.empty:
        return jsonify({"error": "No hay prospectos en la base de datos para exportar"}), 400

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    if fmt == "xlsx":
        out_file = BASE_DIR / f"prospectos_cidiks_{timestamp}.xlsx"
        df.to_excel(out_file, index=False, engine="openpyxl")
        return send_file(str(out_file), as_attachment=True, download_name=f"prospectos_cidiks_{timestamp}.xlsx")
    else:
        out_file = BASE_DIR / f"prospectos_cidiks_{timestamp}.csv"
        df.to_csv(out_file, index=False, encoding="utf-8-sig")
        return send_file(str(out_file), as_attachment=True, download_name=f"prospectos_cidiks_{timestamp}.csv")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print(f"[CÍDIKS SALES ENGINE] Iniciando Sabueso Digital 2.0 en http://{FLASK_HOST}:{FLASK_PORT}...")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
