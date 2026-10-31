import os
import time
import requests
import pandas as pd
import re
import json
import urllib.parse
import warnings
from bs4 import BeautifulSoup
from config import GEMINI_API_KEY, GOOGLE_MAPS_API_KEY
import security

warnings.filterwarnings("ignore", category=FutureWarning)

def search_businesses(query, num_results=5):
    print(f"\n[BUSQUEDA] Buscando negocios en DuckDuckGo para: '{query}'...")
    businesses = []
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query + " sitio oficial contacto", max_results=num_results * 4))
            for r in results:
                href = r.get("href", "")
                if not href or not href.startswith("http"):
                    continue

                directorios_exclusiones = [
                    'yelp.', 'tripadvisor.', 'seccionamarilla.', 'google.com',
                    'booking.com', 'expedia.', 'trivago.', 'hoteles.com',
                    'kayak.', 'despegar.', 'bestday.', 'airbnb.', 'foursquare.',
                    'facebook.com', 'instagram.com', 'twitter.com', 'youtube.com',
                    'linkedin.com', 'pinterest.com', 'tiktok.com', 'wikipedia.org'
                ]
                if any(dir_ex in href.lower() for dir_ex in directorios_exclusiones):
                    continue

                dominio = href.split("//")[-1].split("/")[0].replace("www.", "")
                nombre = r.get("title", "").split(" - ")[0].split(" | ")[0].strip() or dominio.split(".")[0].replace("-", " ").title()

                businesses.append({
                    "nombre": nombre,
                    "url": href
                })
                print(f"[OK] Encontrado prospecto: {nombre} ({href})")
                if len(businesses) >= num_results:
                    break
    except Exception as e:
        print(f"[ERROR] Error en la búsqueda web: {e}")

    return businesses

def analyze_website(business):
    url = business['url']
    print(f"\n[ANALISIS] Analizando sitio web con controles de seguridad: {url}")

    data = {
        "nombre": business['nombre'],
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

    resp = security.safe_http_get(url)
    data["load_time_seconds"] = resp.get("total_time_seconds") or resp.get("load_time_seconds", 0.0)
    data["ssl_valid"] = resp.get("ssl_valid", True)

    if not resp.get("ok"):
        data["error"] = resp.get("error") or f"HTTP {resp.get('status_code', 0)}"
        return data

    text_content = resp.get("text", "")
    soup = BeautifulSoup(text_content, 'html.parser')
    for hidden_tag in soup(["script", "style", "noscript", "svg"]):
        hidden_tag.extract()
    visible_text = soup.get_text(" ", strip=True)

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

    social_patterns = [
        r"facebook\.com/(?!sharer|tr|plugins)[a-zA-Z0-9_\-\.]+",
        r"instagram\.com/[a-zA-Z0-9_\-\.]+",
        r"linkedin\.com/company/[a-zA-Z0-9_\-\.]+"
    ]
    redes = []
    for pattern in social_patterns:
        found = re.findall(pattern, text_content, re.IGNORECASE)
        if found:
            redes.extend(found)
    data["redes_sociales"] = list(set(redes))

    wa_links = re.findall(r"wa\.me/([0-9]+)", text_content)
    wa_api = re.findall(r"api\.whatsapp\.com/send\?phone=([0-9]+)", text_content)
    todos_wa = list(set(wa_links + wa_api))

    if todos_wa or "whatsapp" in text_content.lower():
        data["has_whatsapp"] = True
        data["whatsapp_numeros"] = todos_wa

    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", visible_text)
    data["emails"] = list(set(emails))[:3]

    telefonos = re.findall(r"\+?[\d\-\s()]{8,15}", visible_text)
    tels_filtrados = []
    for tel in telefonos:
        digits = re.sub(r"\D", "", tel)
        if 8 <= len(digits) <= 12 and not digits.startswith("000"):
            tels_filtrados.append(tel.strip())
    data["telefonos"] = list(set(tels_filtrados))[:3]

    return data

def main():
    print("==========================================================")
    print("   SABUESO DIGITAL 2.0 — CÍDIKS SALES ENGINE (CLI)")
    print("==========================================================")
    category = input("¿Qué categoría buscas? (Ej. Hoteles, Restaurantes, Clínicas): ").strip()
    location = input("¿En qué ubicación? (Ej. Oaxaca, Puerto Escondido, Tabasco): ").strip()
    max_results = input("¿Cuántos prospectos quieres extraer? (Recomendado: 3 a 5): ").strip()

    try:
        max_results = int(max_results)
    except Exception:
        max_results = 5

    query = f"{category} en {location}"
    businesses = search_businesses(query, num_results=max_results)

    if not businesses:
        print("[AVISO] No se encontraron nuevos prospectos web.")
        return

    for biz in businesses:
        data = analyze_website(biz)
        print(f"Resultado para {biz['nombre']}: Tel: {data['telefonos']}, Email: {data['emails']}, WA: {data['has_whatsapp']}")

if __name__ == "__main__":
    main()
