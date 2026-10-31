# Registro de Cambios: Sabueso Digital 2.0 (CÍDIKS Sales Engine)

## [2.0.0] - 2026-10-30

### Seguridad y Configuración
- **Migración de secretos a `.env`:** Eliminadas todas las API keys hardcodeadas en `app.py` y `scraper.py`. Creados `.env.example` y `.gitignore`.
- **Confinamiento de red:** Flask ahora corre en `127.0.0.1` con `debug=False` por defecto. CORS restringido únicamente a loopback.
- **Módulo `security.py`:** Implementada validación anti-SSRF con inspección DNS previa, bloqueo de rangos RFC 1918 y loopback, y tope de descarga de 5 MB.
- **Sanitización contra XSS:** Reemplazo de inyecciones inseguras en `static/js/main.js` por `escapeHtml()` y sanitización de URLs contra esquemas `javascript:`.

### Base de Datos y Persistencia
- **Migración a SQLite (`data/sabueso_cidiks.db`):** Creado esquema relacional con tablas `negocios`, `contactos`, `evidencias`, `actividad_comercial`, `duplicados_candidatos` y control de migraciones `schema_migrations`.
- **Cero pérdida de datos:** Implementada auto-migración al arrancar desde `prospectos_current.json`.
- **Carga al inicio:** `main.js` ahora invoca automáticamente `/api/prospects` y `/api/metrics` al cargar la página (`DOMContentLoaded`), resolviendo el bug de pantalla en blanco al refrescar con F5.
- **Normalización de prioridades y tildes:** Creada función `strip_accents()` en `db.py` con mapeo interno estándar `critical`, `high`, `medium`, `low`. Corregidos los bugs donde el contador de críticos se quedaba en 0 y el filtro "Alta prioridad" fallaba.

### Evidencia Visual y Comprobación Real
- **Motor `evidence_engine.py`:** Integración de Playwright con Chromium *headless*.
- **Comprobación de visibilidad estricta:** Distingue contenido recuperado en HTML de contenido visible comprobado en el navegador real.
- **Estados de clasificación:** `VERIFICADA_VISIBLE`, `PENDIENTE_REVISION`, `DESCARTADA`, `NO_VERIFICABLE`. Resuelto el problema de generar afirmaciones falsas a partir de texto oculto en páginas web.
- **Capturas automáticas:** Generación y almacenamiento local de capturas en `static/screenshots/` con visualización en la ficha comercial.

### Prospección y CRM CÍDIKS
- **Copiloto `copilot.py`:** Sistema de redacción en dos modalidades (Modalidad A: Problema Verificado vs Modalidad B: Oportunidad Exploratoria) respetando el estilo humano y profesional de CÍDIKS.
- **Confirmación humana de contacto:** Se eliminó la marcación automática. Copiar un mensaje o abrir WhatsApp no cambia el estado comercial. Añadido modal de confirmación humana con registro de canal y notas en `actividad_comercial`.
- **Separación de ingresos:** El CRM y el dashboard distinguen de forma precisa entre investigación, propuesta enviada, venta acordada e ingreso efectivamente cobrado.

### Herramientas e Integraciones
- **Importador de historiales (`importer.py`):** Reconocimiento inteligente de columnas equivalentes, validación de teléfonos y emails, detección de duplicados previa y función de reversión (*rollback*).
- **Lanzador autónomo:** Creado `iniciar_sabueso.bat` que verifica si el servidor en el puerto 5000 está encendido y lo inicia automáticamente en segundo plano. Actualizado `create_shortcut.py` para generar el acceso directo `.lnk` en el Escritorio.
- **Exportación dual:** Soporte para descarga en formato CSV y Excel nativo (`.xlsx` vía openpyxl).

### Calidad y Pruebas
- **Suite de pruebas de aceptación (`tests/test_acceptance.py`):** 16 pruebas automatizadas cubriendo los 16 criterios obligatorios de la misión, ejecutadas con pytest (100% aprobadas).
