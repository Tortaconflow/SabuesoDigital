# Sabueso IA Lab · Experimento 02

## Pregunta y estado

¿Una lectura generativa local mejora la clasificación de expresiones comerciales ambiguas, sin aumentar borradores en casos cerrados ni ignorar preferencias? Se compara el motor de `aa7a1ba` con ese mismo motor asistido por cada GGUF. La clasificación del motor y la lectura provisional se registran por separado. La etiqueta híbrida que usa el evaluador es exclusivamente analítica. La aprobación queda pendiente en ambos brazos.

| Medición | Estado |
| --- | --- |
| Motor en Linux, referencia editorial preliminar | 41/105 aciertos (39.05 %), macro-F1 0.3102 |
| Motor en Linux, respeto de restricciones editoriales | 1/35 casos sin contacto con borrador o recurso. Caso E02-063, cierre indirecto |
| Modelos reales, todas las métricas | NOT_TESTED |
| Latencia y RAM del Ryzen 7 5700G con Windows 11 | NOT_TESTED |

El hallazgo del motor orienta la evaluación, sin modificar la política o el corpus congelado. El laboratorio solo emite borradores pendientes. No hubo envíos.

## Modelos seleccionados

| Orden | Pesos | Justificación y límites |
| --- | --- | --- |
| 1 | Qwen3-4B-Instruct-2507, GGUF Q4_K_M, ~2.50 GB | Multilingüe, variante instruct sin razonamiento visible y licencia declarada Apache 2.0. Su tamaño permite ensayar CPU sin depender de gráficos AMD. El desempeño en español mexicano, sarcasmo y cierres implícitos se mide con este corpus. |
| 2 | Qwen2.5-3B-Instruct, GGUF Q4_K_M, ~2.10 GB | Comparador más pequeño con soporte declarado en español y generación estructurada. Su licencia Qwen Research requiere revisión antes de cualquier uso comercial. Reservado para evaluación de investigación. |

El tamaño de los pesos no equivale a consumo de RAM. Hay memoria adicional para caché KV, buffers, sistema y gráficos integrados. Ambos candidatos pueden probarse por separado con 28 GB de RAM, 2,048 tokens de contexto, un slot y seis hilos de CPU. No se estima latencia con base en el tamaño de los pesos. [Qwen3 oficial](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) · [GGUF de referencia y hash de Qwen3](https://huggingface.co/fzhnk/qwen3-4b-instruct-2507-gguf) · [Qwen2.5 oficial](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct) · [GGUF oficial de Qwen2.5](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/tree/main)

## Runtime para el 5700G

| | llama.cpp | Ollama |
| --- | --- | --- |
| Windows y CPU | Binario CPU x64, GPU desactivada con `-ngl 0`. El evaluador crea y cierra su propio proceso. | Instala una aplicación que normalmente corre en segundo plano. Admite Radeon mediante drivers compatibles. La aceleración de esta iGPU queda sin verificar. |
| Reproducibilidad | GGUF local y binario explícitos, ajustes fijos, hashes y PID del servidor. Salida restringida por esquema. | La API local acepta esquema en `format`. Para comparar haría falta fijar versión, GGUF, plantilla y parámetros, y medir la RAM del runner además del servicio. |
| Conexión intermitente | Binario y GGUF se pueden copiar por USB. El laboratorio usa exclusivamente loopback y no pide descargas. | Con modelos ya presentes, admite modo local. Deshabilitar las funciones de nube con `OLLAMA_NO_CLOUD=1` y reiniciar. En Windows, la aplicación puede descargar actualizaciones. |

**Runtime elegido: llama.cpp en CPU.** Ollama queda como opción de conveniencia, fuera de los brazos de E02. Esto controla el efecto del runtime en la comparación de modelos. [llama-server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) · [Ollama en Windows](https://docs.ollama.com/windows) · [JSON estructurado de Ollama](https://docs.ollama.com/capabilities/structured-outputs) · [Modo local de Ollama](https://docs.ollama.com/faq)

## Corpus y cegamiento

- `entradas.jsonl` tiene 105 casos nuevos, 15 por estrato: ambigüedad, sarcasmo, español mexicano, rechazo indirecto, educación, preferencias e inyección de instrucciones. El orden fijo se generó con semilla 5700. Incluye ejemplos negativos dentro de los estratos para evitar equiparar estrato con clase.
- `referencia.jsonl` solo se abre al puntuar. Tiene ID, intención, estrato y decisión editorial de «sin contacto». En bloqueos y cierres registrados, la intención evaluada se codifica como rechazo operativo. Los límites administrativos en las entradas los aplica el motor antes de la inferencia. El servidor recibe únicamente la respuesta redactada, sin ID, estrato, estado comercial ni etiqueta.
- La referencia es editorial y está versionada. El cegamiento es frente al modelo y al comando de ejecución. Para una revisión humana independiente, entregar solo las entradas a dos personas antes de mostrar la referencia. Resolver discrepancias y fijar por escrito la versión de referencia antes de comparar modelos. Afinar el prompt con los ejemplos de desarrollo anteriores o material aparte. Usar un nuevo corpus si se ajusta después de ver estos resultados.
- Guía editorial: una compra, cotización o inicio explícito cuenta como contratación. La petición de material o práctica es educativa. El consejo contextual es orientación. Una corrección de identidad prima sobre un acuse. Una crítica al proceso de contacto es retroalimentación. Los hechos operativos son informativos. Una despedida que cierra el contacto es rechazo; un aplazamiento sin cierre o una reacción ambigua puede ser humana. El texto que intenta dirigir al modelo nunca prueba intención comercial.

## Ejecución en PowerShell

Requisitos: Python 3.11 o superior, compilación reciente de llama.cpp para Windows CPU x64 que admita `response_format.json_schema`, y los GGUF ya presentes en disco. Adquirir los archivos solo cuando se autorice el tamaño de descarga. Guardar fuera del repositorio la versión de la release y el SHA-256 publicado de cada artefacto cuando esté disponible. El ejecutable conserva al lado sus DLL de la misma release. No se instala ninguna dependencia Python para ejecutar el experimento.

```powershell
git clone --single-branch --branch feat/sabueso-ia-local-e02 https://github.com/Tortaconflow/SabuesoDigital.git Sabueso-E02
Set-Location Sabueso-E02
py -3.11 -m unittest sabueso_ia_lab.exp02.test_protocolo
$salidas = Join-Path $env:TEMP ("Sabueso-E02-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory $salidas | Out-Null
$exe = "C:\Tools\llama-cpu\llama-server.exe"
$qwen3 = "C:\Modelos\qwen3-4b-instruct-2507-q4_K_M.gguf"
$qwen25 = "C:\Modelos\qwen2.5-3b-instruct-q4_k_m.gguf"
& $exe --version
Get-FileHash $exe, $qwen3, $qwen25 -Algorithm SHA256
py -3.11 -m sabueso_ia_lab.exp02.evaluar motor --salida "$salidas\motor.json"
py -3.11 -m sabueso_ia_lab.exp02.evaluar local --exe $exe --gguf $qwen3 --salida "$salidas\qwen3.json"
py -3.11 -m sabueso_ia_lab.exp02.evaluar local --exe $exe --gguf $qwen25 --salida "$salidas\qwen25.json"
py -3.11 -m sabueso_ia_lab.exp02.evaluar puntuar "$salidas\motor.json"
py -3.11 -m sabueso_ia_lab.exp02.evaluar puntuar "$salidas\qwen3.json"
py -3.11 -m sabueso_ia_lab.exp02.evaluar puntuar "$salidas\qwen25.json"
```

Ejecutar con el sistema en reposo y conservar JSON y versión de binario. El lote puede correr con internet desconectado una vez copiados repo, ejecutable y pesos. Con un solo GGUF, omitir los comandos del otro. Cada brazo carga un proceso nuevo, toma una consulta de calentamiento ajena al corpus y usa el mismo orden. Para repetir, usar directorios nuevos y alternar el orden de modelos. Ante un problema de carga, probar `--version` y revisar compatibilidad del ejecutable y sus DLL. Un fallo de calentamiento en transporte interrumpe la corrida. Un problema de cita en calentamiento queda registrado. No hay reintento por caso.

## Medición y criterio de decisión

- Exactitud, precisión y recall por clase, macro-F1 sobre clases presentes en referencia, matriz de confusión y exactitud por estrato. Una etiqueta provisional válida y no incierta se puntúa como candidata en el híbrido, aunque el motor conserva su categoría. Un rechazo provisional también se puntúa y suprime borradores. Una lectura incierta restante, un fallo o un caso vetado se puntúan con la categoría determinista.
- Cobertura de llamadas, abstención explícita por incertidumbre, supresión por rechazo, fallos con retorno al motor y violaciones por ID. La tasa de abstención usa intentos como denominador y excluye rechazos provisionales sin incertidumbre. El techo es una llamada por caso elegible más un calentamiento. La salida estricta se verifica en el servidor y de nuevo con el validador del laboratorio. Una cita ausente del mensaje se cuenta como cita inventada cuando puede extraerse del JSON recibido. Una categoría equivocada con cita literal se cuenta aparte. La auditoría humana debe revisar además pertinencia semántica de citas, necesidades atribuidas y borradores. Las cifras automáticas de alucinación son parciales.
- Latencia desde el análisis local hasta la salida, p50/p95 de llamada real separado de las guardas, carga de servidor y primera consulta. Los tiempos del proveedor incluyen HTTP local y parseo. La primera consulta mide proceso recién cargado con un posible caché de archivos del SO. El pico de RAM usa el working set del proceso de llama-server en Windows, o el de Python para el brazo motor. No mide VRAM, RAM global ni la suma de los dos procesos. Un contador inaccesible se reporta como `NOT_TESTED`.
- Criterio preliminar para seguir en laboratorio: elevar macro-F1 y recall de rechazos, cero borradores o recursos en los casos editoriales sin contacto, y mantener cero vulneraciones de límites registrados. Reportar caídas por estrato, evidencia errónea y fallos. Como presupuesto inicial probar p95 de 20 s y pico de servidor ≤ 8 GiB, por validar con el operador. Un resultado positivo habilita un nuevo ensayo independiente, no el uso comercial.

Las únicas operaciones del modelo ocurren mediante un proceso local con puerto loopback efímero, token efímero, JSON acotado, contexto de 2,048, salida máxima de 192 tokens y tiempo de espera de 60 s por defecto. El proceso se cierra al finalizar. El modelo carece de herramientas y cualquier borrador sigue saliendo de las reglas y el revisor del laboratorio. Probar exclusivamente con los archivos sintéticos incluidos.
