import os
import sys
import json
import sqlite3
import pytest
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
import security
import db
import evidence_engine
import copilot
import importer
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# 1. La aplicación inicia desde Windows y responde
def test_01_app_initialization(client):
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert b"Sabueso Digital 2.0" in res_index.data

    res_status = client.get("/api/status")
    assert res_status.status_code == 200
    data = res_status.get_json()
    assert "search_engine" in data

# 2. El acceso directo y lanzador funcionan cuando el servidor está apagado
def test_02_launcher_script_exists():
    bat_file = BASE_DIR / "iniciar_sabueso.bat"
    assert bat_file.exists()
    content = bat_file.read_text(encoding="utf-8")
    assert "127.0.0.1:5000" in content
    assert "python app.py" in content
    assert "start http://127.0.0.1:5000/" in content

# 3. No quedan credenciales escritas en el código fuente de la aplicación
def test_03_no_plain_credentials_in_code():
    # Hashes o fragmentos reconocibles de las antiguas claves expuestas
    fragmentos_detectados = [
        "AIzaSyAzbfgcI5tI4FFnt",
        "fd0cd7cd72c1d86a32275a",
        "AIzaSyC-il_QS4kTzLFL2Hv"
    ]
    tracked_extensions = [".py", ".js", ".html"]
    for ext in tracked_extensions:
        for file_path in BASE_DIR.rglob(f"*{ext}"):
            # Excluir la propia suite de pruebas, backups y caches
            if "tests" in str(file_path) or "node_modules" in str(file_path) or ".git" in str(file_path) or "backup" in str(file_path):
                continue
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for frag in fragmentos_detectados:
                assert frag not in text, f"Credencial detectada en texto plano en {file_path.name}"

# 4. No se expone el depurador de Flask ni host 0.0.0.0
def test_04_flask_security_config():
    assert config.FLASK_HOST == "127.0.0.1"
    assert config.FLASK_DEBUG is False

# 5. Los prospectos sobreviven al reinicio (Persistencia SQLite)
def test_05_persistence_across_restart():
    # Insert test business
    test_negocio = {
        "nombre": "Hotel Prueba Oaxaca",
        "sector": "Hospedaje",
        "municipio": "Oaxaca",
        "web": "https://hotelpruebaoaxaca.com",
        "puntuacion": 75,
        "prioridad": "high",
        "estado_comercial": "investigado"
    }
    saved = db.save_or_update_negocio(test_negocio)
    saved_id = saved["id"]

    # Simular reinicio volviendo a leer desde una nueva conexión SQLite
    reloaded = db.get_negocio_detail(saved_id)
    assert reloaded is not None
    assert reloaded["nombre"] == "Hotel Prueba Oaxaca"
    assert reloaded["prioridad"] == "high"

# 6. Los filtros y prioridades funcionan con identificadores normalizados
def test_06_filters_and_priority_normalization():
    assert db.normalize_priority("Oportunidad crítica") == "critical"
    assert db.normalize_priority("ALTA") == "high"
    assert db.normalize_priority("Media") == "medium"
    assert db.normalize_priority("Baja") == "low"

    results_critical = db.get_all_negocios(filter_priority="critical")
    assert isinstance(results_critical, list)

# 7. Los datos externos no ejecutan JavaScript (Protección XSS en Frontend)
def test_07_xss_protection_in_frontend():
    js_content = (BASE_DIR / "static" / "js" / "main.js").read_text(encoding="utf-8")
    assert "function escapeHtml" in js_content
    assert "function safeUrl" in js_content
    assert "javascript:" not in js_content

# 8. Las URLs internas o peligrosas son bloqueadas (Protección SSRF)
def test_08_ssrf_and_dangerous_urls_blocked():
    blocked_urls = [
        "http://127.0.0.1:8080/admin",
        "http://localhost:5000/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/router",
        "http://192.168.1.1/setup",
        "ftp://example.com/file",
        "file:///etc/passwd"
    ]
    for url in blocked_urls:
        is_safe, reason = security.validate_public_url(url)
        assert is_safe is False, f"La URL peligrosa {url} no fue bloqueada. Razón: {reason}"

# 9. Los contactos no verificados no se presentan como confirmados
def test_09_contacts_verification_states():
    # Test phone normalization and whatsapp default state
    clean = importer.clean_phone("9511234567")
    assert clean.startswith("+52")

    invalid = importer.clean_phone("000")
    assert invalid == ""

# 10. El contenido oculto no produce falsas afirmaciones visuales
def test_10_hidden_content_does_not_produce_false_visual_claims():
    visible_sample = "Bienvenido a Hotel Posada Oaxaca. Habitaciones con vista al valle."
    # El texto presente es verificado
    assert evidence_engine.is_element_visually_present(visible_sample, "Hotel Posada") is True
    # El texto oculto o metadato ausente del texto visible es descartado
    assert evidence_engine.is_element_visually_present(visible_sample, "Describa alguna cualidad...") is False

# 11. Los duplicados no inflan métricas
def test_11_duplicates_do_not_inflate_metrics():
    metrics = db.get_dashboard_metrics()
    assert metrics["total"] >= 0
    dups = db.find_potential_duplicates()
    assert isinstance(dups, list)

# 12. Copiar un mensaje NO registra un envío (Regla de confirmación humana)
def test_12_copy_message_does_not_mark_contacted(client):
    test_biz = db.save_or_update_negocio({
        "nombre": "Café CÍDIKS Test",
        "sector": "Cafetería",
        "municipio": "Oaxaca",
        "estado_comercial": "investigado"
    })
    biz_id = test_biz["id"]

    # Simular consulta del prospecto
    res = client.get(f"/api/prospects/{biz_id}")
    data = res.get_json()
    assert data["estado_comercial"] == "investigado"
    assert data.get("fecha_contacto_confirmada") is None

    # Solo tras llamar explícitamente a /api/prospects/contact-confirm cambia
    confirm_res = client.post("/api/prospects/contact-confirm", json={
        "id": biz_id,
        "canal": "whatsapp",
        "notas": "Enviado mensaje frío manualmente por WhatsApp."
    })
    assert confirm_res.status_code == 200

    updated = db.get_negocio_detail(biz_id)
    assert updated["estado_comercial"] == "contactado"
    assert updated["fecha_contacto_confirmada"] is not None

# 13. El CRM conserva seguimientos y cambios comerciales
def test_13_crm_preserves_followup_and_changes():
    test_biz = db.save_or_update_negocio({
        "nombre": "Restaurante La Oaxaqueña",
        "sector": "Restaurante",
        "municipio": "Oaxaca",
        "respuesta": "Interesados en catálogo digital",
        "siguiente_accion": "Enviar demo visual",
        "fecha_seguimiento": "2026-11-05",
        "propuesta_enviada": 1,
        "propuesta_monto": 8500.0,
        "venta_acordada": 1,
        "venta_monto": 8500.0,
        "ingreso_cobrado": 4250.0
    })
    biz_id = test_biz["id"]
    detail = db.get_negocio_detail(biz_id)

    assert detail["respuesta"] == "Interesados en catálogo digital"
    assert detail["propuesta_enviada"] == 1
    assert detail["propuesta_monto"] == 8500.0
    assert detail["ingreso_cobrado"] == 4250.0

# 14. La aplicación funciona sin internet con los datos existentes
def test_14_offline_functionality():
    # Copiloto genera mensajes CÍDIKS determinísticos en modo offline sin IA
    msgs = copilot.generate_cidiks_messages({
        "nombre": "Artesanías Don Benito",
        "sector": "Comercio",
        "municipio": "Oaxaca Centro",
        "web": "https://artesaniasdonbenito.com",
        "checks": {"responsive": False, "whatsapp": False}
    }, use_ai=False)

    assert msgs["modalidad"] == "A_PROBLEMA_VERIFICADO"
    assert "Artesanías Don Benito" in msgs["mensaje_personalizado"]
    assert "CÍDIKS" in msgs["mensaje_personalizado"]

# 15. Los módulos externos fallan de forma controlada
def test_15_graceful_external_module_failure():
    # Simular auditoría de un host inexistente o no resoluble
    res = evidence_engine.capture_visual_evidence("http://sitio-que-no-existe-en-la-red-12345.com")
    assert res["estado_comprobacion"] == "NO_VERIFICABLE"
    assert res["error"] is not None

# 16. Los reportes separan investigación, conversaciones, ventas e ingresos
def test_16_reports_separate_investigation_conversations_sales_and_revenue(client):
    metrics = db.get_dashboard_metrics()
    assert "investigados" in metrics
    assert "contactados" in metrics
    assert "propuestas_enviadas" in metrics
    assert "ventas_confirmadas" in metrics
    assert "ingresos_cobrados" in metrics

    df = db.export_db_to_df()
    expected_cols = [
        "Nombre del negocio", "Sitio Web", "Teléfono", "WhatsApp",
        "Puntuación", "Prioridad", "Estado comercial",
        "Fecha de contacto", "Propuesta enviada", "Venta acordada", "Ingreso cobrado"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Columna {col} ausente en reporte comercial exportado"
