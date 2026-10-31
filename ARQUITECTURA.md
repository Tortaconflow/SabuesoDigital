# Arquitectura del Sistema: Sabueso Digital 2.0 (CÍDIKS Sales Engine)

## 1. Visión General y Principios de Diseño
Sabueso Digital 2.0 adopta una arquitectura desacoplada, orientada a la privacidad y centrada en la resiliencia offline (*local-first*):

```mermaid
graph TD
    UI["Frontend SPA (HTML5 + Vanilla JS + CSS)"] -->|HTTP / JSON (127.0.0.1:5000)| API["Flask Application (app.py)"]
    API --> SEC["Módulo de Seguridad (security.py)"]
    API --> DB["Base de Datos SQLite (db.py)"]
    API --> EVID["Motor de Evidencia Visual (evidence_engine.py)"]
    API --> COP["Copiloto CÍDIKS (copilot.py)"]
    API --> IMP["Importador Histórico (importer.py)"]
    
    SEC -->|Anti-SSRF & DNS Validation| EXT_WEB["Sitios Web de Prospectos"]
    EVID -->|Headless Chromium| PW["Playwright Browser"]
    COP -->|Opcional / Fallback a Reglas| GEMINI["Google Gemini API"]
    DB --> SQLITE[("sabueso_cidiks.db")]
```

---

## 2. Componentes Principales

### 2.1 Backend y Configuración (`config.py` y `app.py`)
- **Interfaz Loopback Estricta:** El servidor escucha únicamente en `127.0.0.1:5000`. No se publica en `0.0.0.0`.
- **CORS Restringido:** Solo se aceptan peticiones provenientes del origen local (`localhost:5000` y `127.0.0.1:5000`).
- **Modo Debug Desactivado por Defecto:** Se controla mediante variable de entorno `FLASK_DEBUG=false`.

### 2.2 Capa de Datos SQLite (`db.py`)
Reemplaza el almacenamiento rudimentario en archivos JSON planos por un esquema relacional normalizado:
- `negocios`: Entidad principal con ID único, nombre comercial, sector, municipio, URL, prioridad normalizada (`critical`, `high`, `medium`, `low`) y estado del ciclo de ventas.
- `contactos`: Registro detallado de teléfonos, emails, enlaces y estado de comprobación de WhatsApp (`confirmado`, `declarado`, `no_verificado`).
- `evidencias`: Almacena el elemento observado, el contenido visible comprobado, la hipótesis de necesidad comercial, la ruta de captura de pantalla y el estado de comprobación (`VERIFICADA_VISIBLE`, `PENDIENTE_REVISION`, `DESCARTADA`, `NO_VERIFICABLE`).
- `actividad_comercial`: Registro cronológico estricto que separa:
  1. *Primer contacto* y *Fecha confirmada de contacto*.
  2. *Respuesta del cliente*.
  3. *Propuesta enviada* (con monto).
  4. *Venta acordada* (con monto).
  5. *Ingreso efectivamente cobrado* (con monto).
- `duplicados_candidatos`: Almacena pares de prospectos que comparten dominio, teléfono o nombre normalizado similar, manteniéndolos en espera de revisión humana (sin fusiones ciegas).

### 2.3 Motor de Seguridad Defensiva (`security.py`)
- **Anti-SSRF:** Antes de realizar cualquier petición saliente, se analizan el esquema (`http`/`https`), el nombre de host y se realiza resolución DNS previa. Si el host o alguna de sus direcciones IP resueltas pertenece a rangos privados (RFC 1918), loopback (`127.0.0.0/8`), link-local o metadatos en la nube (`169.254.169.254`), la petición es rechazada de inmediato.
- **Límite de Descarga (Anti-OOM):** Lectura en flujo por fragmentos (*streaming*) hasta un máximo de 5 MB.
- **Control de Redirecciones:** Valida cada salto de redirección de manera independiente para evitar ataques de redirección abierta hacia redes internas.

### 2.4 Motor de Evidencia Visual (`evidence_engine.py`)
- Integra **Playwright** en modo *headless*.
- Comprueba si el texto o elemento que justifica una afirmación comercial es **realmente visible** en el renderizado final del navegador (descartando estilos `display:none`, `visibility:hidden`, `opacity:0` o dimensiones nulas).
- Si el sitio bloquea el acceso mediante CAPTCHA, protección antibot o requiere autenticación, el estado asignado es `NO_VERIFICABLE`, nunca defectuoso.

### 2.5 Copiloto Comercial CÍDIKS (`copilot.py`)
- Determina automáticamente la modalidad de contacto:
  - **Modalidad A (Problema Verificado):** Utiliza únicamente observaciones comprobadas (`VERIFICADA_VISIBLE`).
  - **Modalidad B (Oportunidad Exploratoria):** Si no hay certeza o el sitio está intacto, formula una pregunta abierta y respetuosa orientada a descubrir necesidades.
- Opera 100% offline con plantillas determinísticas locales y, si se conecta la clave de Gemini, refina el estilo sin violar las directrices de CÍDIKS.
