# Reporte de Pruebas Automatizadas de Aceptación

Fecha de ejecución: **30 de Octubre de 2026**  
Herramienta de pruebas: **pytest 9.2.0 (Python 3.11.9 en Windows)**  
Archivo de pruebas: `tests/test_acceptance.py`  
Resultado global: **16 PASADAS, 0 FALLIDAS (100% de éxito)**

---

## Detalle de Pruebas de Aceptación Obligatorias

| Criterio de Aceptación | Prueba Ejecutada | Resultado | Detalle de Verificación |
| :--- | :--- | :---: | :--- |
| **1. Inicio desde Windows** | `test_01_app_initialization` | ✅ PASÓ | Rutas `/` y `/api/status` responden con HTTP 200 y cabeceras correctas. |
| **2. Acceso directo con servidor apagado** | `test_02_launcher_script_exists` | ✅ PASÓ | `iniciar_sabueso.bat` verifica puerto 5000, inicia Flask y abre el navegador. |
| **3. Cero credenciales en código** | `test_03_no_plain_credentials_in_code` | ✅ PASÓ | Escaneo recursivo de archivos `.py`, `.js` y `.html`; sin claves de API expuestas. |
| **4. Protección del depurador** | `test_04_flask_security_config` | ✅ PASÓ | `FLASK_DEBUG` en `False` y `FLASK_HOST` confinado en `127.0.0.1`. |
| **5. Persistencia al reiniciar** | `test_05_persistence_across_restart` | ✅ PASÓ | Registros insertados en SQLite persisten íntegros tras cerrar y reabrir conexión. |
| **6. Filtros y prioridades funcionales** | `test_06_filters_and_priority_normalization` | ✅ PASÓ | Prioridades con y sin tilde normalizan a `critical`, `high`, `medium`, `low`. |
| **7. Protección contra XSS** | `test_07_xss_protection_in_frontend` | ✅ PASÓ | `escapeHtml` y sanitización `safeUrl` implementados; sin inyección `javascript:`. |
| **8. Bloqueo de URLs peligrosas (SSRF)** | `test_08_ssrf_and_dangerous_urls_blocked` | ✅ PASÓ | Bloqueo exitoso de `127.0.0.1`, `localhost`, `169.254.169.254`, `10.0.0.1` y `192.168.1.1`. |
| **9. Contactos ambiguos no verificados** | `test_09_contacts_verification_states` | ✅ PASÓ | Teléfonos normalizados a E.164 (+52) y estado inicial no verificado. |
| **10. Contenido oculto no genera falsas fallas** | `test_10_hidden_content_does_not_produce_false_visual_claims` | ✅ PASÓ | Textos ausentes de la vista se clasifican como `DESCARTADA`; visibles como `VERIFICADA_VISIBLE`. |
| **11. Duplicados no inflan métricas** | `test_11_duplicates_do_not_inflate_metrics` | ✅ PASÓ | Algoritmo detecta candidatos sin alterar contadores de negocios reales. |
| **12. Copiar mensaje no marca envío** | `test_12_copy_message_does_not_mark_contacted` | ✅ PASÓ | El estado permanece `investigado` hasta confirmación humana vía `/api/prospects/contact-confirm`. |
| **13. Conservación de CRM y seguimientos** | `test_13_crm_preserves_followup_and_changes` | ✅ PASÓ | Registra notas, fecha de seguimiento, propuesta, venta e ingreso cobrado en SQLite. |
| **14. Funcionamiento 100% offline** | `test_14_offline_functionality` | ✅ PASÓ | Copiloto genera mensajes CÍDIKS con reglas determinísticas sin red ni IA. |
| **15. Manejo controlado de fallos externos** | `test_15_graceful_external_module_failure` | ✅ PASÓ | Sitios caídos o no resolubles devuelven `NO_VERIFICABLE` sin lanzar error 500. |
| **16. Separación de métricas e ingresos** | `test_16_reports_separate_investigation_conversations_sales_and_revenue` | ✅ PASÓ | Métricas y exportaciones separan investigación, propuestas, ventas e ingresos cobrados. |

---

## Comando de Reproducción de Pruebas
Para re-ejecutar toda la suite en cualquier momento:
```powershell
cd C:\Users\user\.gemini\antigravity\scratch\prospector
pytest -v tests/test_acceptance.py
```

---

## Actualización 2026-11-25 — rama `feat/aprendizaje-errores`

Resultado: **124 pruebas recolectadas — 119 pasan, 4 en fallo esperado (xfail estricto, Fases 2 y 3), 1 solo en Windows** (`tests/test_real_launch.py`, usa `netstat`/`findstr`).

| Archivo | Pruebas | Qué cubre |
| :--- | ---: | :--- |
| `tests/test_acceptance.py` | 21 | Criterios originales de la misión |
| `tests/test_whatsapp_first.py` | 16 | Canales WhatsApp-first y copiloto |
| `tests/test_movil_sync.py` | 13 | Sincronización PC ⇄ celular |
| `tests/test_contact_flow.py` | 18 | Pendientes / Abiertos / Contactados y números repetidos |
| `tests/test_aprendizaje_aceptacion.py` | 13 | Los 7 errores reales (9 corregidos + 4 xfail) |
| `tests/test_reglas_validacion.py` | 41 | Reglas extensibles, identidad, revisión de borradores, API y sincronización |
| `tests/test_paridad_motor.py` | 1 | Python y `docs/motor.js` dan resultados idénticos (requiere Node; si no hay, se omite) |
| `tests/test_real_launch.py` | 1 | Arranque real en Windows |

```powershell
pytest -q                       # todo (en Windows incluye el arranque real)
pytest -q tests/test_aprendizaje_aceptacion.py -rx   # los errores reales y su estado
```
