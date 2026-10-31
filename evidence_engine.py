import os
import re
import time
import socket
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from bs4 import BeautifulSoup

from config import (
    ENABLE_PLAYWRIGHT,
    PLAYWRIGHT_HEADLESS,
    PLAYWRIGHT_TIMEOUT_MS,
    SCREENSHOTS_DIR,
    BASE_DIR
)
from security import validate_public_url, safe_http_get
import db

def clean_filename(text: str) -> str:
    return re.sub(r"[^\w\-]", "_", text).strip("_")[:50]

def is_element_visually_present(visible_text: str, candidate_text: str) -> bool:
    """Verifica de forma estricta si el candidato aparece en el texto visible del navegador."""
    if not visible_text or not candidate_text:
        return False
    # Normalizar espacios y mayúsculas
    norm_vis = re.sub(r"\s+", " ", visible_text.lower()).strip()
    norm_cand = re.sub(r"\s+", " ", candidate_text.lower()).strip()
    return norm_cand in norm_vis

def capture_visual_evidence(url: str, negocio_id: int = None, text_to_verify: str = None) -> dict:
    """
    Realiza auditoría visual en navegador real mediante Playwright.
    Distingue:
    - Contenido recuperado (HTML)
    - Contenido visible comprobado (Navegador real)
    - Clasificación: VERIFICADA_VISIBLE, PENDIENTE_REVISION, DESCARTADA, NO_VERIFICABLE.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_res = {
        "url_solicitada": url,
        "url_final": url,
        "fecha": datetime.now().isoformat(),
        "resolucion": "1280x800",
        "resultado_carga": "error",
        "estado_comprobacion": "NO_VERIFICABLE",
        "texto_visible_muestra": "",
        "captura_path": "",
        "elemento_observado": "",
        "hipotesis_necesidad": "",
        "error": None,
        "checks": {
            "ssl": True,
            "responsive": False,
            "has_whatsapp": False,
            "has_forms": False,
            "load_time_seconds": 0.0
        }
    }

    # 1. Validación de seguridad previa (SSRF)
    is_safe, reason = validate_public_url(url)
    if not is_safe:
        evidence_res["error"] = f"Seguridad SSRF: {reason}"
        evidence_res["estado_comprobacion"] = "NO_VERIFICABLE"
        return evidence_res

    if not ENABLE_PLAYWRIGHT:
        evidence_res["error"] = "Auditoría visual con Playwright desactivada por configuración"
        evidence_res["estado_comprobacion"] = "PENDIENTE_REVISION"
        return evidence_res

    # 2. Ejecución con Playwright
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        evidence_res["error"] = "Playwright no está instalado en el entorno"
        evidence_res["estado_comprobacion"] = "PENDIENTE_REVISION"
        return evidence_res

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            start_t = time.time()
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT_MS)
                load_time = round(time.time() - start_t, 2)
                evidence_res["checks"]["load_time_seconds"] = load_time
            except Exception as e:
                browser.close()
                evidence_res["error"] = f"Fallo al conectar o timeout: {e}"
                evidence_res["estado_comprobacion"] = "NO_VERIFICABLE"
                return evidence_res

            if not response:
                browser.close()
                evidence_res["error"] = "No se recibió respuesta HTTP del servidor"
                evidence_res["estado_comprobacion"] = "NO_VERIFICABLE"
                return evidence_res

            status = response.status
            evidence_res["url_final"] = page.url

            # Detección de bloqueos o errores de servidor
            if status in (401, 403, 429, 503):
                browser.close()
                evidence_res["resultado_carga"] = f"HTTP {status}"
                evidence_res["error"] = "El sitio requiere autenticación o aplica protección de acceso"
                evidence_res["estado_comprobacion"] = "NO_VERIFICABLE"
                return evidence_res

            # Pequeña espera para renderizado de fuentes y estilos
            page.wait_for_timeout(1000)

            # Tomar captura de pantalla
            domain_part = clean_filename(urlsplit(evidence_res["url_final"]).netloc)
            filename = f"evidencia_{domain_part}_{timestamp}.png"
            full_screenshot_path = SCREENSHOTS_DIR / filename
            rel_screenshot_path = f"/static/screenshots/{filename}"
            page.screenshot(path=str(full_screenshot_path), full_page=False)
            evidence_res["captura_path"] = rel_screenshot_path

            # Extraer ÚNICAMENTE texto visible en pantalla (omitiendo display:none, visibility:hidden, opacity:0)
            visible_text = page.evaluate("""() => {
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                const texts = [];
                while (walker.nextNode()) {
                    const node = walker.currentNode;
                    const parent = node.parentElement;
                    if (!parent) continue;
                    const style = window.getComputedStyle(parent);
                    if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0' && parent.offsetWidth > 0 && parent.offsetHeight > 0) {
                        const trimmed = node.nodeValue.trim();
                        if (trimmed.length > 2) texts.push(trimmed);
                    }
                }
                return texts.join(' ');
            }""")

            evidence_res["texto_visible_muestra"] = visible_text[:500] if visible_text else ""
            evidence_res["resultado_carga"] = "ok"

            # Validar si tiene enlaces o botones visibles de WhatsApp
            has_wa_link = page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a[href*="wa.me"], a[href*="whatsapp.com"], a[href*="api.whatsapp"]'));
                return links.some(l => {
                    const s = window.getComputedStyle(l);
                    return s.display !== 'none' && s.visibility !== 'hidden' && l.offsetWidth > 0;
                });
            }""")
            evidence_res["checks"]["has_whatsapp"] = bool(has_wa_link)

            # Validar formularios visibles
            has_visible_form = page.evaluate("""() => {
                const forms = Array.from(document.querySelectorAll('form'));
                return forms.some(f => {
                    const s = window.getComputedStyle(f);
                    return s.display !== 'none' && s.visibility !== 'hidden' && f.offsetWidth > 0;
                });
            }""")
            evidence_res["checks"]["has_forms"] = bool(has_visible_form)

            # Validar responsividad básica probando viewport móvil
            page.set_viewport_size({"width": 375, "height": 667})
            page.wait_for_timeout(300)
            viewport_meta = page.query_selector('meta[name="viewport"]')
            evidence_res["checks"]["responsive"] = bool(viewport_meta)

            browser.close()

            # Clasificación de observación si se solicitó verificar un texto
            if text_to_verify:
                evidence_res["elemento_observado"] = text_to_verify
                if is_element_visually_present(visible_text, text_to_verify):
                    evidence_res["estado_comprobacion"] = "VERIFICADA_VISIBLE"
                    evidence_res["hipotesis_necesidad"] = f"El texto '{text_to_verify}' es observable en la página por los visitantes."
                else:
                    evidence_res["estado_comprobacion"] = "DESCARTADA"
                    evidence_res["hipotesis_necesidad"] = f"El texto '{text_to_verify}' NO es visible para el visitante (posible contenido oculto o metadato)."
            else:
                evidence_res["estado_comprobacion"] = "VERIFICADA_VISIBLE"
                evidence_res["elemento_observado"] = "Auditoría visual de página de inicio"
                evidence_res["hipotesis_necesidad"] = "Página renderizada y captura comprobada"

    except Exception as e:
        evidence_res["error"] = f"Excepción en auditoría visual: {e}"
        evidence_res["estado_comprobacion"] = "NO_VERIFICABLE"

    # Registrar en base de datos si se proporcionó un negocio_id
    if negocio_id:
        try:
            db.add_evidencia(negocio_id, {
                "url": evidence_res["url_final"],
                "tipo_observacion": "visual_playwright",
                "elemento_observado": evidence_res["elemento_observado"],
                "contenido_visible_comprobado": evidence_res["texto_visible_muestra"],
                "hipotesis_necesidad": evidence_res["hipotesis_necesidad"],
                "captura_path": evidence_res["captura_path"],
                "estado_comprobacion": evidence_res["estado_comprobacion"],
                "revision_humana": 0
            })
        except Exception as e:
            print(f"[EVIDENCE] Error guardando evidencia en DB: {e}")

    return evidence_res
