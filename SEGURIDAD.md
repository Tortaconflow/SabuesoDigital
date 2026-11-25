# Políticas y Controles de Seguridad: Sabueso Digital 2.0

Este documento resume las correcciones de seguridad defensiva aplicadas durante la evolución del sistema.

---

## 1. Vulnerabilidades Mitigadas

| Vulnerabilidad Original | Riesgo | Mitigación Implementada en 2.0 |
| :--- | :--- | :--- |
| **Flask en `0.0.0.0` con `debug=True`** | RCE y consola interactiva expuesta a la red Wi-Fi/LAN local. | Servidor confinado estrictamente a `127.0.0.1` (loopback) y `debug=False` por defecto. |
| **CORS Abierto (`CORS(app)`)** | Cualquier sitio malicioso abierto en el navegador podía controlar la API local. | Restringido exclusivamente a los orígenes `http://127.0.0.1:5000` y `http://localhost:5000`. |
| **API Keys Hardcodeadas** | Exposición de credenciales de Google Gemini, Maps y SerpAPI en código fuente. | Extraídas a variables de entorno (`.env` local ignorado por `.gitignore`). `.env.example` provisto sin secretos. |
| **DOM XSS vía `innerHTML`** | Inyección de JavaScript malicioso desde títulos de webs externas o nombres modificados. | Función `escapeHtml()` implementada en `main.js`; sanitización de URLs contra esquemas `javascript:`. |
| **SSRF en Auditoría Web** | Escaneo de servicios locales, routers hogareños o metadatos de nube mediante la API. | Validación DNS previa con `socket.getaddrinfo`, bloqueo de IPs privadas/loopback y control de redirecciones en `security.py`. |
| **Denegación de Servicio por OOM** | Descarga ilimitada en memoria de archivos pesados (videos, zips) en peticiones HTTP. | Lectura por *streaming* con tope estricto de 5 MB (`MAX_RESPONSE_SIZE_BYTES`). |
| **Uso de `verify=False` ciego** | Exposición a ataques Man-in-the-Middle (MITM). | Verificación de certificados TLS por defecto con `verify=True`; captura controlada de errores SSLError sin degradar la seguridad global. |

---

## 2. Recomendación de Rotación de Credenciales

> [!WARNING]
> Las siguientes credenciales estaban previamente escritas en texto plano en la versión 1.0 del proyecto. **Deben ser rotadas de inmediato por el propietario en sus respectivos paneles de administración**:
> 1. **Google Gemini API Key:** (Generada en Google AI Studio). Debe revocarse y crearse una nueva clave para colocar en `.env`.
> 2. **SerpAPI Key:** (Generada en el panel de SerpAPI). Debe rotarse para evitar consumo indebido si el repositorio fue compartido previamente.
> 3. **Google Maps API Key:** (Consola de Google Cloud). Debe revisarse en la consola y regenerarse.

---

## 3. Prácticas de Operación Segura
- El archivo `.env` **NUNCA** debe comitearse a repositorios públicos ni compartirse por mensajería.
- Las capturas generadas por Playwright se guardan localmente en `static/screenshots/` y están excluidas de los respaldos remotos mediante `.gitignore`.
- La base de datos `data/sabueso_cidiks.db` contiene nombres, teléfonos y notas comerciales privadas de clientes en Oaxaca; debe mantenerse bajo permisos de usuario local en la laptop de trabajo.

---

## 4. Sabueso Móvil (iPhone)
- El servidor Flask **sigue confinado a `127.0.0.1`**: el celular no se conecta a la PC. Todo viaja en archivos que la persona decide enviar.
- GitHub Pages solo publica el código de `docs/`; **ningún dato comercial** está en el repositorio ni en el sitio. Los datos viven en IndexedDB del iPhone.
- `docs/index.html` declara una CSP estricta (`script-src 'self'`, `connect-src 'self'`): la app no puede cargar scripts externos ni enviar datos a otros dominios.
- La importación en la PC valida formato, versión, tamaño (10 MB), tipos de evento y campos permitidos; hace respaldo verificado de SQLite antes de aplicar cambios y registra cada evento en `movil_sync`.
- Los archivos `sabueso_para_celular_*.json`, `sabueso_avances_*.json` y los respaldos del celular contienen datos de clientes: compártelos solo hacia tus propias cuentas (tu WhatsApp, tu correo o tu iCloud) y bórralos de chats compartidos.

## 5. Aprendizaje y QR (Fases 3 y 4)

- **Seudónimos:** el registro de aprendizaje identifica a cada prospecto con HMAC-SHA256 y una clave local (`data/clave_seudonimos.key`, ignorada por Git).
  - Es **seudonimización, no anonimización**: con la clave y la base se puede volver a vincular.
  - Respáldala con `python actualizar.py respaldo` y no la compartas.
- **Exportación:** el informe descargable no incluye ids, nombres, teléfonos, correos, enlaces ni dominios del negocio.
- **QR:** la interpretación nunca abre el enlace ni consulta internet. No se guardan contraseñas de Wi-Fi ni datos de tarjetas de contacto.
- **jsQR:** jsQR 1.4.0 (Apache-2.0) se incluye tal cual en `docs/vendor/` y `static/js/vendor/`, con su licencia. No hace peticiones de red.
