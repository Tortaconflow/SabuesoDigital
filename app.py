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
    if os.environ.get("SABUESO_LOG_TO_FILE") == "1" or sys.stdout is None or not hasattr(sys.stdout, "write"):
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
    'conceptodefinicion.de', 'conceptos.de', 'lexico.com',
    'pdfjsviewer', '.pdf', '/plugins/generic/', 'viewer.html?file='
]

def normalize_mexican_phone(raw_value):
    """
    Normaliza y valida formato de números telefónicos en México (+52).
    Rechaza años (ej. 1990), números concatenados y cadenas < 10 o > 14 dígitos.
    Devuelve dict con valid, digits, e164, wa_digits, display.
    """
    if not raw_value:
        return {"valid": False, "raw": "", "digits": "", "e164": "", "wa_digits": "", "display": ""}

    raw_str = str(raw_value).strip()
    # Eliminar años evidentes (ej. 1990, 2024) y versiones
    raw_clean = re.sub(r"\b(?:19|20)\d{2}\b", "", raw_str)
    
    digits = re.sub(r"\D", "", raw_clean)

    # Validar longitud
    if not digits or len(digits) < 10 or len(digits) > 14:
        return {"valid": False, "raw": raw_str, "digits": digits, "e164": "", "wa_digits": "", "display": ""}
    # Rechazar repetitivos (0000000000, 1111111111, etc.)
    if len(set(digits)) <= 2:
        return {"valid": False, "raw": raw_str, "digits": digits, "e164": "", "wa_digits": "", "display": ""}

    # Caso 10 dígitos: Nacional México (ej. 9541240793)
    if len(digits) == 10:
        return {
            "valid": True,
            "raw": raw_str,
            "digits": digits,
            "e164": f"+52{digits}",
            "wa_digits": f"52{digits}",
            "display": f"+52 {digits[:3]} {digits[3:6]} {digits[6:]}"
        }

    # Caso 12 dígitos iniciando con 52 (ej. 529541240793)
    if len(digits) == 12 and digits.startswith("52"):
        national = digits[2:]
        return {
            "valid": True,
            "raw": raw_str,
            "digits": digits,
            "e164": f"+{digits}",
            "wa_digits": digits,
            "display": f"+52 {national[:3]} {national[3:6]} {national[6:]}"
        }

    # Caso 13 dígitos con prefijo histórico móvil 521 (ej. 5219541240793 -> 529541240793)
    if len(digits) == 13 and digits.startswith("521"):
        clean_12 = "52" + digits[3:]
        national = digits[3:]
        return {
            "valid": True,
            "raw": raw_str,
            "digits": clean_12,
            "e164": f"+{clean_12}",
            "wa_digits": clean_12,
            "display": f"+52 {national[:3]} {national[3:6]} {national[6:]}"
        }

    # Caso internacional con '+' o 11-14 dígitos
    if raw_str.startswith("+") or (11 <= len(digits) <= 14):
        return {
            "valid": True,
            "raw": raw_str,
            "digits": digits,
            "e164": f"+{digits}",
            "wa_digits": digits,
            "display": f"+{digits}"
        }

    return {"valid": False, "raw": raw_str, "digits": digits, "e164": "", "wa_digits": "", "display": ""}

def normalize_phone(phone_str):
    norm = normalize_mexican_phone(phone_str)
    return norm["display"] if norm["valid"] else ""

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
# WHATSAPP-FIRST EXTRACTOR & CONTACT CLASSIFICATION (NIVEL 1)
# =============================================

def extract_and_classify_channels(html, page_url):
    """
    Analiza un documento HTML para extraer canales comerciales con foco prioritario en WhatsApp.
    Distingue:
    - WHATSAPP_COMPROBADO: enlace directo wa.me/api.whatsapp o widget DOM con número verificado.
    - WHATSAPP_PENDIENTE_VERIFICACION: mención contextual de WhatsApp cerca de un número válido de 10 dígitos.
    - SIN_WHATSAPP_COMPROBABLE: sin número de WhatsApp rastreable (clasifica canal alternativo).
    """
    res = {
        "whatsapp": "",
        "whatsapp_estado": "SIN_WHATSAPP_COMPROBABLE",
        "fuente_whatsapp": "",
        "url_origen": page_url,
        "tipo_canal_principal": "ninguno",
        "telefono": "",
        "email": "",
        "redes_sociales": "",
        "has_forms": False,
        "has_whatsapp": False
    }

    if not html:
        return res

    soup = BeautifulSoup(html, "html.parser")
    text_content = html

    wa_comprobado_num = None
    fuente_wa = ""

    # 1. Enlaces explícitos de WhatsApp (href)
    wa_href_patterns = [
        r"wa\.me/\+?([0-9\-\s()]{10,16})",
        r"api\.whatsapp\.com/send(?:\/)?\?(?:[^\"'\s>]*&)?phone=\+?([0-9\-\s()]{10,16})",
        r"web\.whatsapp\.com/send(?:\/)?\?(?:[^\"'\s>]*&)?phone=\+?([0-9\-\s()]{10,16})",
        r"whatsapp://send(?:\/)?\?(?:[^\"'\s>]*&)?phone=\+?([0-9\-\s()]{10,16})"
    ]
    for pattern in wa_href_patterns:
        matches = re.findall(pattern, text_content, re.IGNORECASE)
        for m in matches:
            norm = normalize_mexican_phone(m)
            if norm["valid"]:
                wa_comprobado_num = norm["wa_digits"]
                fuente_wa = "enlace_directo_wa"
                break
        if wa_comprobado_num:
            break

    # 2. Atributos de widgets y plugins de WhatsApp en el DOM (Joinchat, Click to Chat, qlwapp, etc.)
    if not wa_comprobado_num:
        dom_attr_matches = re.findall(r'data-(?:phone|number|whatsapp|wa|tel)=["\']\+?([0-9\-\s()]{10,16})["\']', text_content, re.IGNORECASE)
        for m in dom_attr_matches:
            norm = normalize_mexican_phone(m)
            if norm["valid"]:
                wa_comprobado_num = norm["wa_digits"]
                fuente_wa = "widget_whatsapp_dom"
                break

    # 3. JSON inline de configuración de widgets de WhatsApp en scripts
    if not wa_comprobado_num:
        json_wa_matches = re.findall(r'["\'](?:phone|number|whatsapp)["\']\s*:\s*["\']\+?([0-9\-\s()]{10,16})["\']', text_content, re.IGNORECASE)
        for m in json_wa_matches:
            norm = normalize_mexican_phone(m)
            if norm["valid"]:
                wa_comprobado_num = norm["wa_digits"]
                fuente_wa = "widget_whatsapp_dom"
                break

    # 4. WhatsApp pendiente de verificación (Menciones textuales contextuales: "WhatsApp: 954...")
    wa_pendiente_num = None
    if not wa_comprobado_num:
        visible_text = soup.get_text(" ", strip=True)
        menciones = re.findall(r'(?:whatsapp|whats|wa\.?|reservaciones)\s*(?:al|:|\-)?\s*(\+?[\d\s\-()]{10,16})', visible_text, re.IGNORECASE)
        for m in menciones:
            norm = normalize_mexican_phone(m)
            if norm["valid"]:
                wa_pendiente_num = norm["wa_digits"]
                fuente_wa = "mencion_texto_whatsapp"
                break

    # 5. Teléfonos normales (href="tel:...") y visibles
    tels_found = []
    for a in soup.find_all('a', href=True):
        if a['href'].startswith('tel:'):
            clean_t = a['href'].replace('tel:', '').strip()
            norm = normalize_mexican_phone(clean_t)
            if norm["valid"] and norm["display"] not in tels_found:
                tels_found.append(norm["display"])

    if not tels_found:
        visible_text = soup.get_text(" ", strip=True)
        tels_regex = re.findall(r"\+?[\d\-\s()]{10,16}", visible_text)
        for t in tels_regex:
            norm = normalize_mexican_phone(t)
            if norm["valid"] and norm["display"] not in tels_found:
                tels_found.append(norm["display"])
                if len(tels_found) >= 2:
                    break

    # 6. Correos electrónicos (filtrando dependencias npm/JS)
    emails_found = []
    for a in soup.find_all('a', href=True):
        if a['href'].startswith('mailto:'):
            m = a['href'].replace('mailto:', '').split('?')[0].strip()
            if '@' in m and not m.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.js', '.css')):
                if m not in emails_found:
                    emails_found.append(m)

    visible_body = soup.get_text(" ", strip=True)
    email_regex = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", visible_body)
    bad_emails = ('select2', 'sentry', 'wixpress', 'example.com', 'domain.com', 'email.com', 'bootstrap', 'jquery')
    for e in email_regex:
        e_lower = e.lower()
        if not any(bad in e_lower for bad in bad_emails) and not e_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.js', '.css')):
            if e not in emails_found:
                emails_found.append(e)

    # 7. Redes sociales reales
    social_domains = ['facebook.com', 'instagram.com', 'linkedin.com', 'tiktok.com']
    redes_found = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        for s in social_domains:
            if s in href.lower() and not any(ign in href.lower() for ign in ['sharer', 'intent', 'share', 'plugins', 'tr?id=']):
                if href not in redes_found:
                    redes_found.append(href)

    # 8. Formularios
    has_forms = len(soup.find_all('form')) > 0

    # Clasificación final
    if wa_comprobado_num:
        res["whatsapp"] = wa_comprobado_num
        res["whatsapp_estado"] = "WHATSAPP_COMPROBADO"
        res["fuente_whatsapp"] = fuente_wa
        res["tipo_canal_principal"] = "whatsapp"
        res["has_whatsapp"] = True
    elif wa_pendiente_num:
        res["whatsapp"] = wa_pendiente_num
        res["whatsapp_estado"] = "WHATSAPP_PENDIENTE_VERIFICACION"
        res["fuente_whatsapp"] = fuente_wa
        res["tipo_canal_principal"] = "whatsapp"
        res["has_whatsapp"] = True
    else:
        res["whatsapp"] = ""
        res["whatsapp_estado"] = "SIN_WHATSAPP_COMPROBABLE"
        res["fuente_whatsapp"] = ""
        res["has_whatsapp"] = False
        if tels_found:
            res["tipo_canal_principal"] = "telefono"
        elif emails_found:
            res["tipo_canal_principal"] = "email"
        elif redes_found:
            res["tipo_canal_principal"] = "redes_sociales"
        elif has_forms:
            res["tipo_canal_principal"] = "formulario"
        else:
            res["tipo_canal_principal"] = "ninguno"

    res["telefono"] = ", ".join(tels_found[:2]) if tels_found else ""
    res["email"] = ", ".join(emails_found[:2]) if emails_found else ""
    res["redes_sociales"] = ", ".join(redes_found[:2]) if redes_found else ""
    res["has_forms"] = has_forms
    return res


def discover_contact_channels_level1(base_url, max_subpages=2):
    """
    Descubre canales de contacto de Nivel 1:
    1. Inspecciona la portada.
    2. Si no tiene WhatsApp comprobado, revisa hasta 2 subpáginas internas de contacto del mismo dominio.
    """
    if not base_url or not base_url.startswith(("http://", "https://")):
        return extract_and_classify_channels("", base_url)

    # 1. Portada
    html_landing = ""
    try:
        resp = security.safe_http_get(base_url, timeout=6.0)
        if resp.get("ok"):
            html_landing = resp.get("text", "")
    except Exception as e:
        print(f"[DISCOVERY] Error consultando portada {base_url}: {e}")

    landing_res = extract_and_classify_channels(html_landing, base_url)

    # Si ya tiene WhatsApp comprobado, retornar de inmediato (alta velocidad)
    if landing_res["whatsapp_estado"] == "WHATSAPP_COMPROBADO":
        return landing_res

    # 2. Si no tiene WhatsApp comprobado, buscar hasta max_subpages enlaces de contacto
    if html_landing:
        try:
            soup = BeautifulSoup(html_landing, "html.parser")
            parsed_base = urllib.parse.urlparse(base_url)
            base_domain = parsed_base.netloc.lower()

            candidate_links = []
            contact_keywords = ["contacto", "contact", "reserv", "ubicacion", "whatsapp", "about"]

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                full_url = urllib.parse.urljoin(base_url, href)
                parsed_full = urllib.parse.urlparse(full_url)

                # Mismo dominio y ruta distinta a la portada
                if parsed_full.netloc.lower() == base_domain and full_url.rstrip("/") != base_url.rstrip("/"):
                    path_lower = parsed_full.path.lower()
                    if any(kw in path_lower for kw in contact_keywords):
                        if full_url not in candidate_links:
                            candidate_links.append(full_url)
                            if len(candidate_links) >= max_subpages:
                                break

            # Consultar subpáginas candidatas de forma segura
            for sub_url in candidate_links:
                try:
                    sub_resp = security.safe_http_get(sub_url, timeout=5.0)
                    if sub_resp.get("ok"):
                        sub_res = extract_and_classify_channels(sub_resp.get("text", ""), sub_url)
                        if sub_res["whatsapp_estado"] == "WHATSAPP_COMPROBADO":
                            sub_res["fuente_whatsapp"] = "subpagina_contacto"
                            return sub_res
                        if sub_res["whatsapp_estado"] == "WHATSAPP_PENDIENTE_VERIFICACION" and landing_res["whatsapp_estado"] != "WHATSAPP_COMPROBADO":
                            landing_res = sub_res
                            landing_res["fuente_whatsapp"] = "subpagina_contacto"
                        if not landing_res["telefono"] and sub_res["telefono"]:
                            landing_res["telefono"] = sub_res["telefono"]
                        if not landing_res["email"] and sub_res["email"]:
                            landing_res["email"] = sub_res["email"]
                except Exception as e_sub:
                    print(f"[DISCOVERY] Error consultando subpágina {sub_url}: {e_sub}")
        except Exception as e_parse:
            print(f"[DISCOVERY] Error analizando enlaces de contacto en {base_url}: {e_parse}")

    return landing_res

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

    # Extracción unificada y clasificada de canales (WhatsApp-first)
    channel_info = extract_and_classify_channels(text_content, url)
    data["has_whatsapp"] = channel_info["has_whatsapp"]
    data["whatsapp_numeros"] = [channel_info["whatsapp"]] if channel_info["whatsapp"] else []
    data["whatsapp_estado"] = channel_info["whatsapp_estado"]
    data["fuente_whatsapp"] = channel_info["fuente_whatsapp"]
    data["tipo_canal_principal"] = channel_info["tipo_canal_principal"]
    data["has_forms"] = channel_info["has_forms"]
    data["telefonos"] = [t.strip() for t in channel_info["telefono"].split(",") if t.strip()]
    data["emails"] = [e.strip() for e in channel_info["email"].split(",") if e.strip()]
    data["redes_sociales"] = [r.strip() for r in channel_info["redes_sociales"].split(",") if r.strip()]

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
    include_quarantine = request.args.get("include_quarantine") == "1"
    only_quarantine = request.args.get("only_quarantine") == "1"

    negocios = db.get_all_negocios(
        filter_status=status,
        filter_priority=priority,
        search_term=search,
        sort_col=sort_col,
        sort_dir=sort_dir,
        include_quarantine=include_quarantine,
        only_quarantine=only_quarantine
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
            "mensaje_aprobado": n.get("mensaje_aprobado", 0),
            "fecha_aprobacion_mensaje": n.get("fecha_aprobacion_mensaje"),
            "checks": checks,
            "whatsapp_estado": n.get("whatsapp_estado") or ("WHATSAPP_COMPROBADO" if n.get("whatsapp") else "SIN_WHATSAPP_COMPROBABLE"),
            "fuente_whatsapp": n.get("fuente_whatsapp") or "",
            "tipo_canal_principal": n.get("tipo_canal_principal") or ("whatsapp" if n.get("whatsapp") else "ninguno"),
            "servicio_sugerido": n.get("servicio_sugerido") or "catalogos",
            "observacion_verificada": n.get("observacion_verificada") or "",
            "hipotesis_comercial": n.get("hipotesis_comercial") or "",
            "pregunta_comercial": n.get("pregunta_comercial") or "",
            "identidad_verificada": n.get("identidad_verificada") if n.get("identidad_verificada") is not None else 1,
            "contacto_url_origen": n.get("contacto_url_origen") or "",
            "contacto_fecha_comprobacion": n.get("contacto_fecha_comprobacion") or "",
            "es_favorito": n.get("es_favorito", 0),
            "fecha_contacto_confirmada": n.get("fecha_contacto_confirmada"),
            "respuesta": n.get("respuesta", ""),
            "necesidad_expresada": n.get("necesidad_expresada", ""),
            "propuesta_enviada": n.get("propuesta_enviada", 0),
            "propuesta_monto": n.get("propuesta_monto", 0.0),
            "venta_acordada": n.get("venta_acordada", 0),
            "venta_monto": n.get("venta_monto", 0.0),
            "ingreso_cobrado": n.get("ingreso_cobrado", 0.0),
            "en_cuarentena": n.get("en_cuarentena", 0),
            "motivo_cuarentena": n.get("motivo_cuarentena", ""),
            "fecha_cuarentena": n.get("fecha_cuarentena")
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
    use_paid_apis = bool(body.get("use_paid_apis", False))
    serpapi_key = CONFIG.get("serpapi_key", "") if use_paid_apis else ""

    if DDGS_AVAILABLE and not use_paid_apis:
        try:
            ddg_query = f"{category} en {location}"
            businesses, raw = search_ddg(ddg_query, limit, depth)
            debug_info["motor_usado"] = "duckduckgo"
            debug_info["resultados_raw"] = raw
        except Exception as e:
            debug_info["error"] = f"DuckDuckGo fallo: {str(e)}"

    if not businesses and serpapi_key:
        try:
            businesses, raw = search_serpapi(query, serpapi_key, limit, depth)
            debug_info["motor_usado"] = "serpapi"
            debug_info["resultados_raw"] = raw
        except Exception as e:
            debug_info["error"] = f"SerpAPI fallo: {str(e)}"

    debug_info["resultados_filtrados"] = len(businesses)

    # Obtener dominios y nombres de negocios ya existentes / contactados para no duplicar ni alterar seguimientos
    existing_negocios = db.get_all_negocios(include_quarantine=False)
    existing_domains = set()
    contacted_domains = set()
    for ex in existing_negocios:
        dom = copilot.extract_domain_clean(ex.get("web") or "")
        if dom:
            existing_domains.add(dom)
            if ex.get("estado_comercial") == "contactado" or ex.get("fecha_contacto_confirmada"):
                contacted_domains.add(dom)

    # Filtrar enlaces a archivos, visores de PDFs o negocios previamente contactados/registrados
    valid_businesses = []
    excluded_existing = 0
    for b in businesses:
        u = (b.get("web") or "").lower()
        if any(ign in u for ign in ['.pdf', 'pdfjsviewer', '/plugins/generic/', 'viewer.html?file=']):
            continue
        dom = copilot.extract_domain_clean(u)
        if dom and (dom in contacted_domains or dom in existing_domains):
            excluded_existing += 1
            continue
        valid_businesses.append(b)

    debug_info["excluidos_existentes_o_contactados"] = excluded_existing

    # Guardar prospectos en SQLite clasificando canales WhatsApp-first (Nivel 0 y 1)
    saved_prospects = []
    wa_comp_count = 0
    wa_pend_count = 0
    otros_count = 0

    for b in valid_businesses:
        b["sector"] = category
        b["municipio"] = location

        url = b.get("web", "").strip()
        # Nivel 1: Descubrimiento de canales sin auditoría pesada
        if url:
            channel_info = discover_contact_channels_level1(url, max_subpages=2)
            b["whatsapp"] = channel_info["whatsapp"]
            b["whatsapp_estado"] = channel_info["whatsapp_estado"]
            b["fuente_whatsapp"] = channel_info["fuente_whatsapp"]
            b["tipo_canal_principal"] = channel_info["tipo_canal_principal"]
            b["url_origen"] = channel_info["url_origen"]
            if channel_info["telefono"] and not b.get("telefono"):
                b["telefono"] = channel_info["telefono"]
            if channel_info["email"] and not b.get("email"):
                b["email"] = channel_info["email"]
            if channel_info["redes_sociales"] and not b.get("redes_sociales"):
                b["redes_sociales"] = channel_info["redes_sociales"]
        else:
            b["whatsapp_estado"] = "SIN_WHATSAPP_COMPROBABLE"
            b["tipo_canal_principal"] = "redes_sociales" if b.get("redes_sociales") else "ninguno"

        # Conteo para diagnóstico
        st = b.get("whatsapp_estado")
        if st == "WHATSAPP_COMPROBADO":
            wa_comp_count += 1
        elif st == "WHATSAPP_PENDIENTE_VERIFICACION":
            wa_pend_count += 1
        else:
            otros_count += 1

        # Generar borrador comercial inicial conversacional con CÍDIKS Copilot
        copilot_res = copilot.generate_cidiks_messages(
            prospect=b,
            evidencias=[],
            use_ai=False
        )
        b["mensaje_personalizado"] = copilot_res.get("mensaje_personalizado", "")
        b["mensaje_calido"] = copilot_res.get("mensaje_calido", "")
        b["mensaje_seguimiento"] = copilot_res.get("mensaje_seguimiento", "")
        b["servicio_sugerido"] = copilot_res.get("servicio_sugerido", "catalogos")
        b["observacion_verificada"] = copilot_res.get("observacion_verificada", "")
        b["hipotesis_comercial"] = copilot_res.get("hipotesis_comercial", "")
        b["pregunta_comercial"] = copilot_res.get("pregunta_comercial", "")
        b["identidad_verificada"] = 1 if copilot_res.get("identidad_verificada", True) else 0
        b["problemas_detectados"] = copilot_res.get("observacion_verificada", "")
        b["mensaje_aprobado"] = 0

        saved = db.save_or_update_negocio(b)
        saved_prospects.append(saved)

    debug_info["con_whatsapp_comprobado"] = wa_comp_count
    debug_info["con_whatsapp_pendiente"] = wa_pend_count
    debug_info["otros_canales"] = otros_count

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

    # Actualizar en SQLite (nuevos borradores generados requieren aprobacion humana explicita)
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
        "mensaje_aprobado": 0,
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
    if site_data.get("whatsapp_estado"):
        updated_data["whatsapp_estado"] = site_data["whatsapp_estado"]
    if site_data.get("fuente_whatsapp"):
        updated_data["fuente_whatsapp"] = site_data["fuente_whatsapp"]
    if site_data.get("tipo_canal_principal"):
        updated_data["tipo_canal_principal"] = site_data["tipo_canal_principal"]
    if copilot_res.get("servicio_sugerido"):
        updated_data["servicio_sugerido"] = copilot_res["servicio_sugerido"]

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
    fecha_contacto = body.get("fecha_contacto")

    if not negocio_id:
        return jsonify({"error": "ID de prospecto requerido"}), 400

    db.record_human_contact(negocio_id, canal, notas, fecha_contacto=fecha_contacto)
    return jsonify({"success": True, "message": "Contacto confirmado manualmente"})

@app.route("/api/copilot/regenerate", methods=["POST"])
def api_copilot_regenerate():
    body = request.json or {}
    negocio_id = body.get("id")
    servicio_sugerido = body.get("servicio_sugerido", "catalogos")

    if not negocio_id:
        return jsonify({"error": "ID de prospecto requerido"}), 400

    prospect = db.get_negocio_detail(negocio_id)
    if not prospect:
        return jsonify({"error": "Prospecto no encontrado"}), 404

    prospect["servicio_sugerido"] = servicio_sugerido
    prospect["_force_explicit"] = True
    copilot_res = copilot.generate_cidiks_messages(
        prospect=prospect,
        evidencias=prospect.get("evidencias", []),
        use_ai=bool(body.get("use_ai", False)),
        api_key=CONFIG.get("gemini_api_key")
    )

    updated = db.save_or_update_negocio({
        "id": negocio_id,
        "servicio_sugerido": copilot_res.get("servicio_sugerido", servicio_sugerido),
        "observacion_verificada": copilot_res.get("observacion_verificada", ""),
        "hipotesis_comercial": copilot_res.get("hipotesis_comercial", ""),
        "pregunta_comercial": copilot_res.get("pregunta_comercial", ""),
        "identidad_verificada": 1 if copilot_res.get("identidad_verificada", True) else 0,
        "mensaje_personalizado": copilot_res.get("mensaje_personalizado", ""),
        "mensaje_calido": copilot_res.get("mensaje_calido", ""),
        "mensaje_seguimiento": copilot_res.get("mensaje_seguimiento", ""),
        "mensaje_aprobado": 0
    })

    return jsonify({"success": True, "prospect": updated, "copilot": copilot_res})

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

@app.route("/api/quarantine", methods=["GET"])
def api_quarantine_list():
    quarantined = db.get_quarantined_records()
    return jsonify({
        "total_en_cuarentena": len(quarantined),
        "registros": quarantined
    })

@app.route("/api/quarantine/restore", methods=["POST"])
def api_quarantine_restore():
    body = request.json or {}
    ids = body.get("ids", [])
    motivo = body.get("motivo", "Restauración manual solicitada por usuario")
    if not ids or not isinstance(ids, list):
        return jsonify({"error": "Lista de IDs requerida para restaurar de cuarentena"}), 400
    res = db.restore_quarantined_records(ids, motivo_restauracion=motivo)
    return jsonify({"success": True, **res})

@app.route("/api/audit-log", methods=["GET"])
def api_audit_log_list():
    negocio_id = request.args.get("negocio_id", type=int)
    logs = db.get_audit_log(negocio_id=negocio_id)
    return jsonify({
        "total_cambios": len(logs),
        "cambios": logs
    })

@app.route("/api/audit-log/restore", methods=["POST"])
def api_audit_log_restore():
    body = request.json or {}
    audit_id = body.get("audit_id")
    if not audit_id:
        return jsonify({"error": "audit_id requerido"}), 400
    try:
        res = db.restore_audit_change(int(audit_id))
        return jsonify({"success": True, **res})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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
    db.init_db()
    print(f"[CÍDIKS SALES ENGINE] Iniciando Sabueso Digital 2.0 en http://{FLASK_HOST}:{FLASK_PORT}...")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
