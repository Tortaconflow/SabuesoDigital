# Evaluación de Sabueso Digital IA

## Ejecución reproducible

Desde la raíz, con Python 3.10 o posterior:

```bash
python -m sabueso_ia_lab.evaluar
python -m pytest -q tests/test_sabueso_ia_lab.py
python -m pytest -q --ignore=tests/test_real_launch.py
```

Las pruebas usan las dependencias de prueba existentes y SQLite temporal por fixture. El evaluador usa exclusivamente la biblioteca estándar y funciones puras del repositorio. Imprime JSON con resultados por caso, borradores presentes, hallazgos de revisión, recursos, tiempos y uso aproximado de memoria de Python.

## Diseño y observaciones

Los brazos comparten las guardas locales del laboratorio. **Motor** desactiva el simulador. **Híbrido simulado** contabiliza la categoría provisional si existe y la determinista en caso contrario. La **referencia editorial** registra la decisión esperada según una lectura manual de los 12 casos por el autor del prototipo. Fixtures y referencia fueron escritos en el mismo ejercicio. No hay anotación ciega ni revisión humana independiente. Un bloqueo administrativo se cuenta como «rechazo» para medir la decisión de atención. Los aciertos comparan decisiones de laboratorio y no representan la precisión poblacional del clasificador.

| Métrica de esta corrida | Motor | Híbrido simulado |
| --- | ---: | ---: |
| Coincidencia con referencia editorial | 8/12 | 10/12 |
| Casos de rechazo o bloqueo con borrador | 0/3 | 0/3 |
| Lecturas con cita literal validada | — | 6 |
| Lecturas con cita válida que discrepan de referencia | — | 1 |
| Salidas inválidas o ausentes con retorno al motor | — | 2 |
| Mediana de tiempo con instrumentación | 5.282 ms | 5.579 ms |
| Pico de asignaciones Python por caso | 12,311 B | 19,772 B |
| USD de API por consulta | 0 | 0 |

La medición de tiempo incluye validación y trazado de asignaciones, tras cargar las reglas. El JSON incluye tiempo de CPU por caso. El pico de asignaciones excluye RSS, procesos externos y pesos. Las cifras varían por ejecución. El diferencial de aciertos verifica que el mecanismo puede presentar otra lectura. La simulación carece de un modelo inferente y sus cifras no respaldan superioridad de arquitectura.

| Caso de interés | Lectura editorial del resultado |
| --- | --- |
| Ambigua sobre pedidos | Comunidad y Meta WhatsApp son opciones educativas plausibles. «Catálogos» sigue siendo una hipótesis. El borrador pide permiso para orientar. |
| Petición de guía | Ambos brazos proponen Comunidad y Conocimiento. La solicitud es general y una guía temática más precisa requiere aclarar el objetivo. |
| Rechazo indirecto | El simulador se abstuvo y ambos brazos dejaron el borrador vacío. Se preservó la categoría principal. |
| Cita inventada ante texto no confiable | El esquema rechazó la cita inexistente y se recuperó el resultado guiado. |
| Curiosidad interpretada como contratación | Una cita auténtica acompañó una inferencia errónea. La plantilla de aclaración fue demasiado proactiva aquí. El hallazgo exige revisión humana y casos de abstención antes de usar un modelo real. |
| Conservación de un servicio | Se suprimieron recursos y borrador aunque ambos brazos discreparon de la etiqueta editorial. |

### Protocolo para medir un modelo real

- Congelar corpus sintético de desarrollo y otro de prueba ciega, estratificados por intención, sector, español mexicano, negativas implícitas, bloqueos, preferencias, lenguaje ambiguo e instrucciones incrustadas. Registrar versión y semilla. Dos anotadores independientes etiquetan intención, evidencia, servicio, explícito/inferido, restricciones y recursos pertinentes. Resolver discrepancias con un tercer criterio y publicar acuerdo inicial.
- Comparar motor, híbrido y referencia con idénticas guardas. Reportar matriz de confusión, precisión y recall por clase, macro-F1 y cobertura de abstención. Ponderar especialmente falsos positivos en contratación y falsos negativos en rechazo. Revisar citas literalmente y puntuar relación semántica. Contar hechos, links o promesas inventados y necesidades inferidas promovidas a explícitas.
- Evaluar recursos y borradores a ciegas. Puntuar de 0 a 2 por dimensión: relevancia, brevedad, naturalidad, fidelidad a evidencia y respeto de preferencias. Cualquier presión tras un rechazo o contenido prohibido invalida la salida. Un recurso sin permiso, evidencia temática o vigencia no puntúa como pertinente.
- Registrar p50/p95 frío y caliente, tokens reales, CPU, RSS, energía y costo por consulta y por recomendación aceptada. Para remoto sumar reintentos y reservas inciertas. Calcular intervalos y diferencias pareadas. Medir siempre el motor como respaldo durante fallo, cuota y desconexión.
- Umbral preliminar para considerar integración: cero violaciones de rechazo o preferencias en el corpus de prueba, mejora pareada en intenciones ambiguas y en pertinencia educativa, sin aumento de propuestas sin evidencia, y p95 y costo aceptados antes de habilitarlo. El tamaño de muestra y los presupuestos operativos se definen antes de correr la comparación.

## Regresión

Commit base en entorno Linux: **176 pruebas aprobadas** al excluir el ciclo completo de arranque de Windows. Rama experimental: **190 aprobadas** con la misma exclusión, incluidas **14 del lab**. En el intento de suite completa, el ciclo de arranque sí respondió por HTTP con base temporal, pero falló en detección del PID porque el lanzador usa `netstat` y `findstr`. Esa prueba requiere validación en Windows.
