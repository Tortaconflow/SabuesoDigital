# Registro de Cambios: Sabueso Digital 2.0 (CÍDIKS Sales Engine)

## [2.1.1] - 2026-11-25 — Prospectos repetidos y bandeja «Abiertos»

### Corregido
- **Prospectos repetidos:** la búsqueda solo descartaba por dominio web; ahora también descarta números de WhatsApp/teléfono que ya existen (en cualquier formato) y nunca vuelve a guardar un número que está en Pendientes, Abiertos o Contactados.
- **Identidad por número (`contact_identity.py`):** comparación por número E.164 (+52…), sin espacios, guiones ni paréntesis. Si falta el código de país se usa el país del prospecto (campo `pais` o ubicación mexicana reconocible); números ambiguos o inválidos nunca se fusionan.
- **Registros anteriores respetados:** nada se borra ni se fusiona. Los registros viejos con un número repetido solo se ocultan de Pendientes (siguen en «Todos») y se muestra cuántos están ocultos.

### Nuevo flujo Pendientes → Abiertos → Contactados (PC y Sabueso Móvil)
- «Abrir en WhatsApp» registra el intento (tabla `intentos_contacto`) y mueve el prospecto a **Abiertos**, conservando ficha y borrador. No confirma el envío ni cambia el estado comercial.
- Desde Abiertos se puede volver a abrir WhatsApp o **Regresar a Pendientes** (el historial de intentos se conserva y el prospecto aparece una sola vez).
- «Contactado» sigue llegando solo por la confirmación humana existente (`record_human_contact` / «Confirmar contacto»).
- Sabueso Móvil 1.1.0: bandejas, borrador persistente, diario síncrono para no perder el intento si iOS congela la app, alta manual bloqueada si el número ya existe y eventos `whatsapp_abierto` / `regresar_pendientes` sincronizados con la PC.

### Pruebas
- `tests/test_contact_flow.py`: 18 pruebas (formatos equivalentes, ambiguos sin fusionar, abrir sin marcar enviado, regresar una sola vez, confirmar y no reaparecer en búsquedas nuevas, eventos del celular).

## [2.1.0] - 2026-11-24 — Sabueso Móvil (iPhone)

### Nuevo
- **Sabueso Móvil (`docs/`):** app web instalable para iPhone que funciona sin internet (service worker + IndexedDB). Lista y filtros de prospectos, ficha comercial, botón de WhatsApp con mensaje prellenado, confirmación humana de contacto, CRM (respuesta, necesidad, siguiente paso, fecha de seguimiento, propuesta, venta acordada e ingreso cobrado por separado), notas, alta manual de negocios con copiloto CÍDIKS Modalidad B, atajos de búsqueda a Google Maps/Google/Facebook, respaldo y restauración.
- **Sincronización por archivo (`movil_sync.py`):** `GET /api/movil/export` genera el paquete para el celular (incluye acuses de eventos aplicados) y `POST /api/movil/import` aplica los avances del celular de forma idempotente (tabla `movil_sync`), con respaldo verificado de SQLite previo.
- **Botón «Celular» en Sabueso PC** con ventana para descargar el archivo del celular e importar avances, mostrando aplicados, omitidos, errores y posibles duplicados.

### Reglas preservadas
- El estado `contactado` solo se registra con un evento de confirmación humana; la actualización genérica lo rechaza.
- Prospectos bloqueados exigen nota para registrar contacto, igual que en la PC.
- Altas desde el celular que coinciden en teléfono o nombre van a `duplicados_candidatos` (sin fusión automática).
- Campos no permitidos desde el celular (identidad, prioridad, puntuación, etc.) se rechazan.

### Pruebas
- `tests/test_movil_sync.py`: 13 pruebas nuevas (exportación, cuarentena, idempotencia, bloqueo, CRM, altas, duplicados, archivos inválidos).

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
