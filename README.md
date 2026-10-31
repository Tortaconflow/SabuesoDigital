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
└── tests/
    └── test_acceptance.py  # 16 Pruebas de aceptación obligatorias
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
