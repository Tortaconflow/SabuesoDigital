# Aprendizaje basado en errores reales — Fases 0 a 4

Rama: `feat/aprendizaje-errores` (no fusionada). Base: `claude/upbeat-wozniak-vht8fn` @ `24764f9`.
Metodología: cada error observado se convirtió primero en una prueba reproducible
(`tests/test_aprendizaje_aceptacion.py`); después se corrigió el código hasta que pasó.

| Prueba de aceptación | Fase | Antes | Después |
| :--- | :---: | :---: | :---: |
| 1. Mobiliario nunca recibe propuesta de habitaciones (4 pruebas) | 1 | ❌ | ✅ |
| 2. El nombre de otro negocio bloquea la generación (4 pruebas) | 1 | ❌ | ✅ |
| 7. La necesidad confirmada prevalece sobre la inferencia | 1 | ❌ | ✅ |
| 3. Si quiere conservar su página, no se insiste | 2 | ❌ | ✅ |
| 4. Respuesta automática no cuenta como oportunidad | 2 | ❌ | ✅ |
| 5. QR recibido se interpreta antes de recomendar | 3 | ❌ | ✅ |
| 6. Rechazo explícito cierra la prospección | 2 | ❌ | ✅ |

Los 7 casos pasan. Ya no queda ninguna prueba en «fallo esperado».

---

## Caso 1 — Una mueblería recibió una propuesta de habitaciones

**Evidencia (código anterior).** Para «Muebles Rústicos del Valle» (giro *Mobiliario*):
> «…vi que cuentan con enlace directo de WhatsApp **para reservaciones**. Trabajamos con negocios **de hospedaje** desarrollando catálogos digitales y fichas ligeras **de habitaciones y tarifas**…» (551 caracteres)

**Causa raíz.**
- Las capacidades CÍDIKS, preguntas e hipótesis estaban redactadas solo para hospedaje (`copilot.py`, antes líneas 18–325).
- El servicio se elegía por palabras del *nombre* e ignoraba el campo *sector*.
- La frase de apertura daba por hecho «WhatsApp para reservaciones».

**Cambio.**
- `docs/reglas/sabueso_reglas.json`: giros comerciales con palabras clave, vocabulario, reglas de servicio, preguntas e hipótesis propias. Agregar un giro = agregar un objeto (sin tocar el núcleo).
- `reglas.py`: el giro registrado manda; si el nombre sugiere otro giro con certeza, se pide **revisión humana** y mientras tanto se redacta con el giro neutral.
- `validacion.revisar_mensaje`: un término de otro giro se marca como **«requiere revisión»** (no prohibición absoluta). Se permite si aparece en la evidencia del prospecto o dentro de una frase propia de su giro (p. ej. «muebles para habitación»).

**Después.**
> «Buen día, equipo de Muebles Rústicos del Valle. Les escribo de CÍDIKS. Vi su página y su WhatsApp. ¿Comparten su catálogo de muebles por WhatsApp o mandan fotos en cada mensaje?» (177 caracteres, 1 pregunta)

**Limitaciones.** Detección por palabras clave, no por significado. Nombres ambiguos («Casa X», «Palapa») quedan en giro general. Los borradores viejos de tu base no cambian solos: el revisor los marca y hay botón para regenerarlos.

---

## Caso 2 — Mensaje listo para un negocio cuyo sitio era de otro

**Evidencia.** «Hotel Casa Azul» con sitio `hotelmarbella-pxm` pasaba como verificado y generaba mensaje.

**Causa raíz.** La verificación solo exigía un nombre y algún canal. No se comparaba nombre vs dominio, ni se revisaba si el borrador saludaba o mencionaba a otro negocio. El nombre viene del título del resultado de búsqueda.

**Cambio.**
- `validacion.analizar_identidad`: nombre vs dominio (tolera dominios descriptivos como `hotelenpuertoescondido`), sitio de directorio, número compartido con otro negocio y giro discrepante.
- Todo genera **revisión humana**, nunca invalidación: no cambia `identidad_verificada` ni marca «no contactar».
- Mientras no se revise, el borrador es «[REVISIÓN HUMANA REQUERIDA]» y no se puede enviar.
- Confirmar o corregir guarda una huella de los datos revisados. Si los datos cambian, se vuelve a pedir revisión. Queda en la bitácora `auditoria_cambios_datos`.
- Revisor de borradores: un saludo dirigido a otro nombre propio, o la mención de otro prospecto, **bloquea** el envío.

**Limitaciones.** Heurística por palabras (dominios con abreviaturas raras pueden pedir revisión de más). El saludo a otro negocio solo se detecta si el nombre va con mayúscula. Solo se compara contra prospectos guardados.

---

## Caso 7 — La necesidad confirmada no se usaba

**Evidencia.** Necesidad «Necesitamos un CRM para dar seguimiento a nuestros clientes» y el copiloto seguía proponiendo «web».

**Causa raíz.** `necesidad_expresada` se guardaba, pero ningún módulo la leía.

**Cambio.** El servicio se decide así: necesidad confirmada por el prospecto > elección humana > reglas del giro. La hipótesis cita la necesidad textual. Si no se reconoce, se muestra y se pide revisar; no se ignora.

**Limitaciones.** Se reconoce por palabras de necesidad. La memoria estructurada con fuente y jerarquía es Fase 2.

---

## Errores encontrados durante la implementación (también corregidos)

| # | Error | Cómo se detectó | Corrección |
| :- | :--- | :--- | :--- |
| A | Con WhatsApp sin verificar, la pregunta daba por hecho que atienden por WhatsApp | Prueba existente `test_copilot_pending_whatsapp_does_not_assert_direct_wa` | Regla general: si el WhatsApp no está verificado, primero se confirma el canal |
| B | El seguimiento de una clínica decía «citas o pedidos» | El propio revisor de vocabulario | Texto general del servicio sin palabras de un giro |
| C | «Hola, borrador…», «Hola, soy Ana…» se tomaban como saludo a otro negocio | Prueba en el celular simulado | Solo cuenta como destinatario un nombre propio con mayúscula; 8 pruebas nuevas |
| D | La auditoría web regeneraba el borrador sin id ni confirmación humana | Revisión de código | Se conservan id, confirmación y necesidad al auditar |
| E | Sin municipio se escribía «la Costa de Oaxaca» (dato inventado) | Revisión de código | Sin dato real, se omite la ubicación |

---

## Fase 2 — Conversación, memoria comercial y ecosistema CÍDIKS

Todo funciona sin internet y sin IA (0 tokens), con las mismas reglas en la PC y en el celular (`docs/reglas/sabueso_reglas.json` → `conversacion.py` y `docs/motor.js`; `tests/test_paridad_motor.py` lo comprueba). **Nada se envía solo:** Sabueso sugiere y una persona confirma.

### Caso 3 — Si quiere conservar su página, no se insiste

**Evidencia (antes).** Si el hotel respondía «Gracias, estamos contentos con nuestra página y queremos conservarla.», el borrador seguía proponiendo `web` y el seguimiento volvía a hablar de la página.

**Causa raíz.** La respuesta se guardaba como texto libre. Ninguna parte del copiloto la leía para saber qué servicio quería conservar o rechazar el negocio.

**Cambio.**
- Nueva **memoria comercial** (`memoria_comercial`, `conversacion.memoria_efectiva`): necesidad, servicio conservado, servicio rechazado, restricción, prioridad y dato corregido.
- Cada dato guarda la frase literal del negocio (≤160 caracteres, con correos y teléfonos ocultos) y su fuente.
- Jerarquía de fuentes: prospecto > humano > QR > regla > IA.
- El copiloto quita los servicios conservados o rechazados antes de elegir.
- El revisor marca **«requiere revisión»** (`MSG_SERVICIO_EXCLUIDO`) si un borrador vuelve a mencionarlos.

**Después.** Servicio `catalogos`. Seguimiento: «Hola de nuevo, equipo de Hotel Las Palmas. Les escribí hace unos días sobre un catálogo digital para WhatsApp. Si no es buen momento, no hay problema.» Además, el seguimiento solo se habilita si ya hubo un contacto confirmado.

### Caso 4 — Una respuesta automática no es una oportunidad

**Evidencia (antes).** «¡Hola! Gracias por comunicarte con Posada Sol. En breve te atenderemos.» sumaba 1 en «respuestas recibidas».

**Causa raíz.** La métrica contaba cualquier texto en el campo `respuesta`.

**Cambio.**
- **Clasificación de respuestas** por frases, en este orden: automática, rechazo, corrección, retroalimentación, educativa, orientación, contratación e informativa. Si ninguna coincide, se pide revisión humana.
- Las conversaciones educativas se evalúan antes que las comerciales.
- Solo «contratación» es oportunidad comercial.
- Las métricas separan respuestas humanas, automáticas, oportunidades, conversaciones educativas, retroalimentaciones y prospecciones cerradas.

**Después.** `respuestas_recibidas = 0` y `respuestas_automaticas = 1`.

### Caso 6 — Un rechazo explícito cierra la prospección

**Evidencia (antes).** Con «No nos interesa, por favor no vuelvan a escribir.», el negocio seguía con borrador y seguimiento listos.

**Causa raíz.** No existía el estado «prospección cerrada».

**Cambio.**
- Confirmar un rechazo guarda `prospeccion_cerrada = 1`, el motivo y la fecha, y pone el estado `no_interesa`.
- El borrador queda bloqueado (`MSG_PROSPECCION_CERRADA`), igual que cualquier seguimiento (`SEG_NO_PERMITIDO`).
- El negocio sale de Pendientes y el botón de WhatsApp se desactiva.
- **Solo se reabre** con una nota de al menos 10 caracteres que explique la nueva solicitud expresa del negocio. La reapertura queda auditada.

**Después.** «[BLOQUEADO — PROSPECCIÓN CERRADA] Motivo: El negocio respondió con un rechazo explícito. No se envían mensajes comerciales ni seguimientos a Cabañas Luna. Solo se reabre si el negocio lo solicita expresamente.»

### Ecosistema CÍDIKS: recursos gratuitos y servicios profesionales

- **Intención antes que venta.** Una pregunta educativa («¿tienen algún curso gratis…?») o de orientación («¿por dónde empiezo?») se responde con un recurso gratuito. No cambia el estado comercial ni convierte a la persona en prospecto.
- **Un recurso por respuesta.** El catálogo `recursos_gratuitos` tiene 3 rutas CÍDIKS (Comunidad, Conocimiento, Asesor IA) y 4 cursos externos gratuitos (Meta, HubSpot, Microsoft y Google).
  - Cada recurso tiene condiciones, temas y una fecha de revisión (`revisar_antes: 2027-02-21`). Si vence, deja de sugerirse.
  - Un curso externo solo se sugiere si coincide con el tema o con lo que la persona pidió con sus palabras. Si hay empate, va primero lo de CÍDIKS.
- **Contactos educativos.** Se pueden registrar como «Tipo de contacto: educativo».
  - Su mensaje es un saludo corto con un recurso gratuito y una pregunta («¿Les sirve?»).
  - Tienen su propio filtro y no aparecen en Pendientes comerciales.
- **Servicios profesionales.** Solo se proponen cuando hay una necesidad observable: dicha por el negocio o vista en sus canales. Sabueso no inventa presupuestos ni necesidades. Ante «¿cuánto cuesta?», la respuesta sugerida invita a una llamada de 15 minutos, sin precios ni propuestas largas.
- **Retroalimentación.** Los comentarios sobre CÍDIKS o sus recursos quedan en `interacciones` y se consultan en `/api/retroalimentacion`. Solo se muestran el giro, la fecha y el texto con datos de contacto ocultos, sin el nombre del negocio.
- **Corrección de datos.** «Número equivocado» o «no somos un hotel» se guardan como «dato corregido» y vuelven a pedir la revisión de identidad.
- **Seguimiento único.** Máximo 1, manual, desde el día 5 (se sugiere entre el 5 y el 7). Requiere un contacto confirmado y que el negocio no haya contestado.
- **Celular.** Las mismas funciones están en la ficha («Analizar respuesta» → «Confirmar y guardar»). Se sincronizan con dos eventos nuevos: `interaccion` y `reabrir_prospeccion`.

**Fuente.** Las rutas y cursos salen del documento estratégico de Notion. Las páginas de reilycastro.com no se pudieron leer desde esta sesión: la red del entorno bloquea ese sitio (403). Por eso se usan solo las direcciones que tú indicaste y no se inventaron textos de esas páginas.

### Limitaciones de la Fase 2

- **Detección por frases.** Se clasifica por frases, no por significado. El español muy informal, los emojis, los audios y las imágenes no se reconocen: quedan como «requiere revisión humana» y tú eliges la categoría.
- **«No por ahora» cuenta como rechazo.** Es una decisión conservadora. Si el negocio vuelve a escribir, se reabre con una nota.
- **Datos ya marcados.** En la pantalla de confirmación, los datos de memoria detectados aparecen marcados. Desmarca los que no correspondan antes de guardar.
- **Revisión de recursos.** El catálogo debe revisarse antes del 21-feb-2027. Después, los recursos dejan de sugerirse hasta que se actualicen.
- **Versión de la PC.** Para importar los eventos nuevos del celular, la PC necesita esta versión. Una PC anterior marca como error solo esos eventos y sí importa los demás. Después de actualizarla, basta con volver a importar el mismo archivo: los eventos que fallaron se aplican y los que ya estaban no se repiten.

## Fase 3 — QR local (caso 5)

**Evidencia (antes).** Un restaurante que enviaba el QR de su menú digital seguía recibiendo la propuesta de un catálogo digital. El QR no se leía, así que lo que mostraba no llegaba a la recomendación.

**Causa raíz.** Sabueso no tenía forma de leer un QR ni de convertir lo que contiene en un hecho observable.

**Cambio.**
- **Lectura en el navegador:** la foto o captura se lee en la PC y en el celular con jsQR 1.4.0 (Apache-2.0), incluido en el proyecto (`docs/vendor/`, `static/js/vendor/`). No usa internet. Si la foto está borrosa, se puede pegar el enlace a mano.
- **Interpretación (`qr_local.py`, `interpretarQr` en `docs/motor.js`):** reconoce WhatsApp, menú o catálogo (incluido el catálogo de `wa.me/c/`), redes, mapa, tarjeta de contacto, Wi-Fi, enlace y texto. El enlace se muestra como texto y **nunca se abre**. Los tipos y patrones están en `qr` dentro de las reglas.
- **Lo que se guarda:** solo el **tipo y el dominio**, en `negocios.qr_recibidos`. Nunca se guarda la contraseña del Wi-Fi, ningún dato de las tarjetas de contacto ni el número que lleva un enlace de WhatsApp. Todo lo que llega del celular se vuelve a sanear.
- **Antes de recomendar:** lo que el QR demuestra que el negocio ya tiene entra en la memoria como `canal_existente`, con fuente `qr`, y ese servicio se excluye. Además el hecho se suma a la observación verificada.

**Después.** «Sitio web oficial activo (lapalapa.example); WhatsApp público comprobado (+529581239876) en su sitio oficial; **ya cuenta con menú digital (QR: menu.example)**.» El servicio deja de ser `catalogos`, y el borrador pregunta si su menú impreso y digital está actualizado.

**Limitaciones.**
- La interpretación se hace por dominio y por palabras del enlace («menu», «carta», «catalogo»). Un menú publicado en un dominio genérico, sin esas palabras, queda como «Enlace web».
- jsQR puede no leer fotos muy borrosas, oscuras o con el QR muy pequeño. En ese caso, pega el enlace a mano.

## Fase 4 — Aprendizaje y métricas

**Evidencia (antes).** Las correcciones que hacía una persona se perdían. Por ejemplo, cambiar la clasificación sugerida o corregir el giro no dejaba rastro. Tampoco había forma de saber qué plantilla obtenía más respuestas humanas.

**Cambio.**
- **Seudónimos (`aprendizaje.py`):** cada prospecto se identifica con un **HMAC-SHA256 con una clave local** (`clave_seudonimos.key`, junto a la base). Esto es **seudonimización, no anonimización**. La clave nunca se reemplaza sola: si está dañada, se avisa.
- **Registro de errores y correcciones** (`aprendizaje_registro`):
  - Tipos: clasificación corregida (sugerida ≠ confirmada), dato incorrecto (el negocio corrige un dato), identidad corregida (giro o nombre), mensaje editado antes de enviarlo y observación del revisor aprobada por una persona.
  - Los textos se guardan sin correos, teléfonos, enlaces, nombre ni dominio del negocio, ni nombres de personas («soy…», «me llamo…»).
- **Huella de cada envío confirmado** (`envios_huella`): plantilla, estrategia (`relación|plantilla|servicio`), caracteres, preguntas, si se editó y los códigos del revisor. El texto del mensaje no se guarda.
  - El celular calcula la huella contra *sus* borradores y la manda con el contacto confirmado. La PC la valida campo por campo.
- **Comparación por estrategia:**
  - Cuenta envíos, respuestas humanas, interés, rechazos y conversaciones educativas.
  - Avisa si la muestra es chica: menos de `muestra_minima`, que es 10.
  - Las respuestas automáticas no cuentan como respuesta, y lo educativo no cuenta como interés.
- **Contador por función** (`consumo_ia`): copiloto, clasificación, QR y revisión. Registra cuántas veces se usa cada una y siempre **0 tokens**.
- **Pantallas:**
  - **PC:** botón «Aprendizaje», con el informe descargable seudonimizado.
  - **Celular:** sección «Qué estrategia funciona» en Hoy.
  - **API:** `/api/aprendizaje` y `/api/aprendizaje/exportar`.

**Limitaciones.**
- `envios_huella` guarda el `negocio_id` para unir cada envío con sus respuestas. Ese dato vive solo en tu base local y **nunca se exporta**.
- En el celular, el resultado de cada envío se calcula con la última respuesta registrada. En la PC se calcula con todas las respuestas recibidas entre un envío y el siguiente.
- Con menos de 10 envíos por estrategia, los porcentajes no son concluyentes, y la pantalla lo avisa.
- El registro empieza a llenarse desde esta versión. Lo que pasó antes no se reconstruye.

## Consumo de tokens

**0.** La integración con Gemini nunca se ejecutaba: `use_ai` y `api_key` llegaban al copiloto pero se ignoraban (el README decía lo contrario). Ahora se ignoran a propósito y está documentado. Cada resultado reporta `consumo_tokens: 0` y `motor: reglas_deterministas`. Una prueba verifica que el copiloto, la validación y las reglas no importan clientes de IA ni de red.

## Seudonimización (corrección 7, para la Fase 4)

- Un **HMAC-SHA256 con clave local** es **seudonimización**, no anonimización: con la clave y los datos se puede volver a vincular. Un hash simple de un teléfono de 10 dígitos se revierte probando todas las combinaciones.
- La huella usada en la revisión de identidad (FNV-1a) **no** es seudonimización ni seguridad. Solo detecta que los datos cambiaron y vive junto a ellos en la base local.

## 129 pruebas documentadas vs. 69 ejecutadas (corrección 8)

Pruebas que recolecta `pytest` en cada rama del repositorio en GitHub:

| Rama | Commit | Pruebas |
| :--- | :--- | ---: |
| `main` | 12ed811 | 17 |
| `fix/iteracion-1-crm-responsive` | f8ae8b7 | 22 |
| `feat/whatsapp-first-mvp` (predeterminada) | 76c676e | 38 |
| `claude/upbeat-wozniak-vht8fn` | 24764f9 | 69 (68 aquí + 1 solo Windows) |
| `feat/aprendizaje-errores` (esta) | Fase 1: 0121cfb | 124 (119 + 4 xfail + 1 solo Windows) |
| `feat/aprendizaje-errores` (esta) | Fase 2: b46cf55 | 147 (145 + 1 xfail + 1 solo Windows) |
| `feat/aprendizaje-errores` (esta) | Fases 3 y 4 | 177 (176 + 1 solo Windows) |

El número **129 no aparece en ningún archivo ni commit** de ninguna rama. Lo más probable es que salga de la copia local en tu PC (el README apunta a `C:\Users\user\.gemini\antigravity\scratch\prospector`), con pruebas o commits que nunca se subieron. Para comprobarlo en Windows:

```powershell
cd C:\Users\user\.gemini\antigravity\scratch\prospector
git status
git log --oneline origin/HEAD..HEAD
pytest --collect-only -q | Select-Object -Last 1
```

## Pendiente (fuera del alcance de esta iteración)

- **Después:** modalidades de prospección comercial, reciprocidad comunitaria, comunidad universitaria y validación tecnológica. Las reglas ya tienen `modalidades` para agregarlas como datos.
