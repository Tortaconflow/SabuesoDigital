# Procedimiento único de actualización — PC con Windows y iPhone

Versión de destino: **Sabueso Digital 2.4.0** (rama `feat/aprendizaje-errores`) y **Sabueso Móvil 1.4.0**.
Tiempo aproximado: 20 minutos. Todo funciona sin internet, salvo los pasos marcados con 🌐.

> **Reglas:**
> - Siempre trabaja con Sabueso **cerrado**.
> - Haz los pasos en orden: primero el respaldo, luego la prueba y al final la migración.
> - Las migraciones **solo agregan** tablas y columnas: no borran ni cambian ningún registro.
> - Si un paso dice «NO migres», detente y no sigas.

---

## Parte 1 — Antes de actualizar: deja todo sincronizado

1. **En el iPhone:**
   - Pestaña **Sincronizar** → **«Enviar avances (compartir archivo)»** → mándate el archivo.
   - En la misma pestaña, **«Crear respaldo completo»** → guárdalo en iCloud Drive.
2. **En la PC, con la versión que ya tienes:** botón **Celular** → **«Importar avances del celular»** → elige el archivo de avances.
   Así ningún avance queda solo en el celular.
3. Cierra Sabueso Digital (cierra la ventana de la consola que lo mantiene abierto).

## Parte 2 — Actualizar la PC (Windows, PowerShell)

Abre PowerShell en la carpeta de Sabueso (donde está `iniciar_sabueso.bat`):

```powershell
# 1. Bajar la versión nueva 🌐 (en cualquier lugar con internet; también puedes copiar la carpeta en USB)
git fetch origin feat/aprendizaje-errores
git checkout feat/aprendizaje-errores

# 2. Ver cómo está tu base
python actualizar.py estado

# 3. Respaldo verificado (base + clave de seudónimos)
python actualizar.py respaldo

# 4. Ensayo: migra una COPIA temporal y compara (tu base no se toca)
python actualizar.py probar
#    Debe terminar con: «RESULTADO: la migración es segura.»

# 5. Migración real (hace otro respaldo, migra, verifica y revierte sola si algo falla)
python actualizar.py migrar

# 6. (Recomendado) Pruebas completas, incluida la de arranque real en Windows
python -m pytest -q
```

- **Dependencias:** no hay nuevas. jsQR, el lector de QR, ya viene dentro del proyecto.
- **Ensayo opcional con una copia de práctica:** primero copia tu base y apunta Sabueso a la copia con estos comandos. Luego repite los pasos 2 a 5 sin tocar tu base real.

  ```powershell
  copy data\sabueso_cidiks.db data\copia_prueba.db
  $env:SABUESO_DB_PATH = "data\copia_prueba.db"
  ```

  Al terminar, cierra PowerShell o borra la variable: `Remove-Item Env:SABUESO_DB_PATH`.

7. Abre Sabueso con `iniciar_sabueso.bat` y revisa:
   - **Arriba:** aparece el botón **«Aprendizaje»**. Al abrirlo debe decir «Tokens de IA: 0».
   - **En la ficha de un negocio:** aparece el recuadro **«QR recibido»**.
8. Botón **Celular** → **«Descargar archivo para el celular»** → mándatelo al iPhone.

## Parte 3 — Actualizar el iPhone

**Mientras no se publique la versión nueva en GitHub Pages** (todavía no está autorizado):

- El iPhone sigue con su versión actual. Es **compatible**:
  - La PC nueva acepta los avances del celular viejo.
  - Si un contacto confirmado llega sin huella, la PC la calcula con sus propios borradores.
  - El celular viejo ignora los datos nuevos que le manda la PC (QR, huella).
- Importa en el iPhone el archivo del paso 8: **Sincronizar** → **«Elegir archivo de la PC»**.

**Cuando se autorice publicar en GitHub Pages:** 🌐

1. Con internet, abre Sabueso Móvil. Aparecerá **«Hay una versión nueva»** → tócalo.
2. Comprueba que en la ficha de cada negocio aparece **«QR recibido»**, y en **Hoy**, **«Qué estrategia funciona»**.
3. Vuelve a importar el archivo de la PC del paso 8. Importarlo dos veces no duplica nada.
4. Desde ese momento ya funciona sin internet, como antes.

## Parte 4 — Sincronización diaria (sin cambios)

- **PC → celular:** **Celular** → «Descargar archivo para el celular» → en el iPhone, «Elegir archivo de la PC».
- **Celular → PC:** en el iPhone, «Enviar avances» → en la PC, «Importar avances del celular».
- **Eventos nuevos que viajan del celular a la PC:**
  - `qr_recibido`: solo el tipo y el dominio del QR.
  - `contacto_confirmado` con la **huella** del envío: plantilla, largo, número de preguntas y si lo editaste. El texto no viaja.

## Parte 5 — Reversión (si algo no te convence)

**PC:**

```powershell
# Sabueso cerrado. Usa el respaldo que hizo «migrar» (el nombre exacto se mostró al terminar):
python actualizar.py revertir "data\backups\sabueso_cidiks_antes_de_actualizar_AAAAMMDD_HHMMSS.db"
# Volver al código anterior (fase 2):
git checkout b46cf55
```

- **Respaldo de seguridad:** antes de restaurar, `revertir` respalda la base actual en `..._antes_de_revertir_...db` y verifica que el respaldo esté sano. Si está dañado, no lo usa.
- **Código viejo sobre la base nueva:** se probó que la versión anterior (`b46cf55`) abre una base ya migrada y lista, exporta y calcula métricas. Las tablas nuevas simplemente se ignoran. Por eso volver solo al código, sin restaurar la base, también es posible.
- **Lo que se pierde al restaurar:** lo que registraste después del respaldo. Para recuperar los avances del celular, vuelve a importar sus archivos: importarlos de nuevo no duplica nada.

**iPhone:**

- Tus datos viven en el celular y no se borran al cambiar de versión.
- Si una versión nueva falla, **«Elegir archivo de la PC»** con tu **respaldo completo** restaura todo lo que había al crearlo.
- Volver a la versión anterior de la app requiere volver a publicar en GitHub Pages, y eso necesita tu autorización.

## Qué cambia en la base de datos (solo se agrega)

| Cambio | Para qué |
| :--- | :--- |
| `negocios.qr_recibidos` | QR confirmados: solo tipo y dominio |
| `aprendizaje_registro` | Errores y correcciones con seudónimo y texto anonimizado |
| `envios_huella` | Huella de cada envío confirmado (sin el texto) |
| `consumo_ia` | Usos por función y tokens de IA (siempre 0) |
| `data/clave_seudonimos.key` | Clave local de los seudónimos. No se sube a Git y `respaldo` la copia junto a la base. **No la borres:** sin ella, los seudónimos nuevos no coinciden con los viejos. |
