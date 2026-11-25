# Sabueso Móvil (iPhone)

Versión de bolsillo de Sabueso Digital para trabajar **desde el celular, con o sin internet**.
Esta carpeta (`docs/`) es una app web instalable (PWA) que se publica gratis con GitHub Pages.

> Este sitio solo entrega el **código** de la app. Tus prospectos, mensajes y avances se guardan
> **solo en tu iPhone** (IndexedDB de Safari) y pasan a la PC con archivos que tú mandas.

## Qué puedes hacer en el celular

| Función | ¿Necesita internet? |
| :--- | :--- |
| Ver tus prospectos, filtrarlos y buscarlos | No |
| Abrir WhatsApp con el mensaje listo, llamar, copiar el mensaje | No (WhatsApp sí necesita señal para enviar) |
| Confirmar contacto (siempre de forma manual) | No |
| Registrar respuesta, necesidad, siguiente paso, fecha de seguimiento | No |
| Registrar propuesta, venta acordada e ingreso cobrado (por separado) | No |
| Notas | No |
| Agregar negocios que encuentres en Maps, Facebook o en la calle (con mensaje CÍDIKS Modalidad B) | No |
| Buscar negocios en Google Maps / Google / Facebook | **Sí** |
| Búsqueda automática + auditoría web como en la PC | Fase 2 (necesita un servidor) |

## Instalación (una sola vez)

1. Publica la carpeta con GitHub Pages (ver abajo) y abre la dirección en **Safari** del iPhone.
2. Toca **Compartir (□↑) → Agregar a pantalla de inicio**.
3. Abre Sabueso desde el ícono. Desde ahí funciona sin internet y iOS no borra los datos
   (las páginas que no se instalan pueden perder sus datos tras 7 días sin uso).

### Publicar con GitHub Pages

En GitHub: **Settings → Pages → Build and deployment → Source: Deploy from a branch**,
elige la rama y la carpeta **`/docs`**, y guarda. En 1–2 minutos queda en:

```
https://tortaconflow.github.io/SabuesoDigital/
```

## Flujo PC ⇄ celular

```
Sabueso PC ── «Celular → Descargar archivo para el celular» ──► sabueso_para_celular_….json ──► iPhone (pestaña PC → Elegir archivo)
iPhone ── «Enviar avances» (menú Compartir) ──► sabueso_avances_….json ──► Sabueso PC («Celular → Importar avances del celular»)
```

- Pasa los archivos como prefieras: WhatsApp a ti mismo, correo, Drive o iCloud.
- Si la PC no tiene internet: en el iPhone activa **Ajustes → Compartir Internet** y conecta la PC.
- La PC hace un **respaldo verificado de SQLite** antes de aplicar avances y nunca aplica dos veces
  el mismo avance (cada evento tiene un identificador único).
- Después de importar avances en la PC, vuelve a descargar el archivo para el celular: así el iPhone
  sabe qué avances ya llegaron («✓ en la PC»).
- También acepta el **CSV** de «Exportar CSV» de la PC, aunque trae menos datos (no incluye la fecha
  de seguimiento ni el bloqueo de identidad).

## Pendientes, Abiertos y Contactados

- **Pendientes:** prospectos que todavía no abres. Cada número aparece una sola vez.
- **Abiertos:** tocaste «Abrir en WhatsApp». Eso queda registrado, pero **no** cuenta como mensaje enviado.
  Desde ahí puedes abrir WhatsApp otra vez, confirmar que lo enviaste o regresarlo a Pendientes.
- **Contactados:** solo cuando tú confirmas que enviaste el mensaje.
- Un número que ya está en Abiertos o Contactados no vuelve a aparecer en Pendientes, aunque llegue
  con otro formato (por ejemplo `954 123 4567` y `+52 (954) 123-4567`). Si el número no tiene lada de
  país y no se sabe el país del negocio, no se compara con otros.

## Reglas CÍDIKS que respeta

- Abrir WhatsApp o copiar un mensaje **no** marca a nadie como contactado: hay que confirmarlo.
- Prospectos bloqueados (identidad no verificada / investigar más) no permiten enviar mensaje y exigen
  nota para registrar un contacto que ya ocurrió.
- El estado «Contactado» solo llega por confirmación de contacto, nunca editando el estado.
- Una venta acordada nunca se suma como ingreso cobrado.
- Los negocios nuevos que se parezcan a uno existente (mismo teléfono o nombre) quedan en
  «Duplicados» para revisión humana; no se fusionan solos.

## Archivos

| Archivo | Para qué |
| :--- | :--- |
| `index.html` | Estructura de la app y política de seguridad (CSP: sin scripts ni conexiones externas) |
| `app.js` | Lógica: almacenamiento local, sincronización, ficha, CRM, copiloto de bolsillo |
| `app.css` | Estilos (misma paleta que Sabueso PC) |
| `sw.js` | Service worker: guarda la app para abrir sin internet |
| `manifest.webmanifest`, `icons/` | Instalación en pantalla de inicio |

Al cambiar cualquier archivo, sube la constante `VERSION` en `sw.js` (y `APP_VERSION` en `app.js`)
para que los iPhone instalados reciban el aviso «Hay una versión nueva».
