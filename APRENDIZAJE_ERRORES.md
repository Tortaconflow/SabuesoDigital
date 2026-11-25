# Aprendizaje basado en errores reales — Fases 0 y 1

Rama: `feat/aprendizaje-errores` (no fusionada). Base: `claude/upbeat-wozniak-vht8fn` @ `24764f9`.
Metodología: cada error observado se convirtió primero en una prueba reproducible
(`tests/test_aprendizaje_aceptacion.py`); después se corrigió el código hasta que pasó.

| Prueba de aceptación | Fase | Antes | Después |
| :--- | :---: | :---: | :---: |
| 1. Mobiliario nunca recibe propuesta de habitaciones (4 pruebas) | 1 | ❌ | ✅ |
| 2. El nombre de otro negocio bloquea la generación (4 pruebas) | 1 | ❌ | ✅ |
| 7. La necesidad confirmada prevalece sobre la inferencia | 1 | ❌ | ✅ |
| 3. Si quiere conservar su página, no se insiste | 2 | ❌ | ⏳ xfail estricto |
| 4. Respuesta automática no cuenta como oportunidad | 2 | ❌ | ⏳ xfail estricto |
| 5. QR recibido se interpreta antes de recomendar | 3 | ❌ | ⏳ xfail estricto |
| 6. Rechazo explícito cierra la prospección | 2 | ❌ | ⏳ xfail estricto |

«xfail estricto»: la prueba documenta el error y falla en rojo si alguien lo corrige sin actualizarla.

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
| `feat/aprendizaje-errores` (esta) | — | 124 (119 + 4 xfail + 1 solo Windows) |

El número **129 no aparece en ningún archivo ni commit** de ninguna rama. Lo más probable es que salga de la copia local en tu PC (el README apunta a `C:\Users\user\.gemini\antigravity\scratch\prospector`), con pruebas o commits que nunca se subieron. Para comprobarlo en Windows:

```powershell
cd C:\Users\user\.gemini\antigravity\scratch\prospector
git status
git log --oneline origin/HEAD..HEAD
pytest --collect-only -q | Select-Object -Last 1
```

## Pendiente (no autorizado todavía)

- **Fase 2:** memoria comercial, clasificación de respuestas, consentimiento y un solo seguimiento manual a los 5–7 días, y cierre por rechazo (casos 3, 4 y 6).
- **Fase 3:** lectura local de QR (caso 5).
- **Fase 4:** registro seudonimizado de errores y correcciones, y métricas por estrategia y de tokens.
- **Después:** modalidades de prospección comercial, reciprocidad comunitaria, comunidad universitaria y validación tecnológica. Las reglas ya tienen `modalidades` para agregarlas como datos.
