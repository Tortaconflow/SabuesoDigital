# Sabueso Digital 2.0 — CÍDIKS Sales Engine

Sistema interno de prospección B2B ética y motor comercial local para **CÍDIKS** en Oaxaca, México. Diseñado bajo filosofía *local-first*: funciona de manera autónoma en Windows, con o sin conexión a internet y sin exponer credenciales ni datos comerciales a terceros.

---

## Filosofía Comercial CÍDIKS
El flujo comercial sigue una cadena de valor estricta:
$$\text{Problema Observable} \longrightarrow \text{Evidencia Comprobada} \longrightarrow \text{Necesidad Hipotética} \longrightarrow \text{Propuesta Concreta} \longrightarrow \text{Contacto Humano} \longrightarrow \text{Venta Real} \longrightarrow \text{Ingreso Cobrado}$$

### Reglas Irrenunciables del Sistema:
1. **Cero invenciones:** No inventa negocios, teléfonos, emails, problemas técnicos ni testimonios.
2. **Evidencia real:** Distingue contenido recuperado en HTML de contenido visible comprobado en navegador (Playwright). El contenido oculto nunca se presenta como un fallo observable.
3. **Acción humana requerida:** Copiar un mensaje o abrir WhatsApp **NUNCA** marca automáticamente a un prospecto como contactado. Se requiere confirmación humana explícita.
4. **Respeto y naturalidad:** Los mensajes no utilizan jerga técnica ni promesas exageradas. El Copiloto CÍDIKS ofrece dos modalidades: **Modalidad A (Problema Verificado)** y **Modalidad B (Oportunidad Exploratoria)**.
5. **Privacidad y Costos:** No almacena credenciales en código. Funciona con reglas determinísticas locales y búsqueda gratuita por defecto (DuckDuckGo), sin requerir APIs pagadas para operar.

---

## Instalación y Arranque Rápido

### Requisitos:
- Windows 10/11 con Python 3.11+.
- Navegador Google Chrome o Chromium (para Playwright).

### 1. Iniciar con Doble Clic:
Haz doble clic en el acceso directo del Escritorio:
```text
C:\Users\user\Desktop\Sabueso Digital.lnk
```
El script lanzador (`iniciar_sabueso.bat`):
- Comprueba si el servidor Flask en `http://127.0.0.1:5000/` ya está activo.
- Si está apagado, lo levanta en segundo plano de forma automática.
- Abre tu navegador predeterminado en `http://127.0.0.1:5000/`.

### 2. Iniciar desde Terminal:
```powershell
cd C:\Users\user\.gemini\antigravity\scratch\prospector
python app.py
```

---

## Sabueso Móvil (iPhone, sin internet)

Para trabajar desde el celular cuando estás fuera o la PC no tiene internet. Es una app web instalable que vive en `docs/` y se publica gratis con GitHub Pages. Los datos se guardan **solo en el iPhone**; la PC y el celular se pasan archivos, sin servidores de por medio.

1. **Publicar una vez:** GitHub → *Settings → Pages → Deploy from a branch* → carpeta `/docs`. Queda en `https://tortaconflow.github.io/SabuesoDigital/`.
2. **Instalar:** ábrela en Safari → Compartir → *Agregar a pantalla de inicio*.
3. **PC → celular:** en Sabueso PC, botón **Celular → Descargar archivo para el celular**. En el iPhone: pestaña **PC → Elegir archivo de la PC**.
4. **En la calle:** lista y filtros, botón de WhatsApp con el mensaje listo, confirmar contacto, CRM (respuesta, seguimiento, propuesta, venta y cobro por separado), notas y alta de negocios encontrados en Maps o Facebook.
5. **Celular → PC:** en el iPhone, **Enviar avances** (menú Compartir). En Sabueso PC: **Celular → Importar avances del celular**. Se hace respaldo de SQLite antes de aplicar, y reimportar el mismo archivo no duplica nada.

Detalles en [`docs/LEEME.md`](docs/LEEME.md). La búsqueda automática con auditoría web sigue siendo exclusiva de la PC (ver `PENDIENTES.md`).

---

## Estructura del Proyecto

```text
prospector/
├── app.py                  # API REST local (Flask) y servidor loopback
├── config.py               # Configuración centralizada y rutas absolutas
├── security.py             # Filtros defensivos (anti-SSRF, validación DNS/IP, límites)
├── db.py                   # Capa SQLite local (negocios, contactos, evidencias, CRM)
├── evidence_engine.py      # Motor de comprobación visual con Playwright
├── copilot.py              # Copiloto de redacción ética CÍDIKS (Modalidades A y B)
├── importer.py             # Importador con vista previa, validación y rollback
├── movil_sync.py           # Sincronización por archivo con Sabueso Móvil (iPhone)
├── iniciar_sabueso.bat     # Lanzador autónomo con detección de puerto 5000
├── create_shortcut.py      # Generador del acceso directo .lnk en el Escritorio
├── requirements.txt        # Dependencias fijadas del proyecto
├── data/
│   └── sabueso_cidiks.db   # Base de datos SQLite local
├── static/
│   ├── css/style.css       # Estilos interfaz CÍDIKS
│   ├── js/main.js          # Lógica frontend con defensas XSS
│   └── screenshots/        # Capturas de evidencia visual Playwright
├── templates/
│   └── index.html          # Panel de control comercial y CRM
├── docs/                   # Sabueso Móvil: PWA para iPhone (GitHub Pages)
└── tests/
    ├── test_acceptance.py  # 16 Pruebas de aceptación obligatorias
    └── test_movil_sync.py  # Sincronización PC ⇄ celular
```

---

## Restauración a la Versión Anterior (Backup)
Se conserva una copia de seguridad íntegra previa a la evolución en:
```text
C:\Users\user\.gemini\antigravity\scratch\prospector_backup_original
```
Para restaurar el estado original:
```powershell
Remove-Item -Path "C:\Users\user\.gemini\antigravity\scratch\prospector" -Recurse -Force
Copy-Item -Path "C:\Users\user\.gemini\antigravity\scratch\prospector_backup_original" -Destination "C:\Users\user\.gemini\antigravity\scratch\prospector" -Recurse
```
