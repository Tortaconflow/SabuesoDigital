# Experimento 02-A · Ollama local

E02-A agrega un brazo al [Experimento 02](PROTOCOLO.md). Usa sus guardas, su prompt, sus categorías, el validador de citas y las métricas. El corpus principal y sus etiquetas se conservan byte por byte. Ollama 0.40.16 y `qwen3.5:4b` ya están disponibles en la PC del operador según su prueba. La versión y el digest local se registran al iniciar. El piloto y el corpus completo quedan **NOT_TESTED** con el modelo hasta ejecutar los comandos en esa PC.

El comando usa `127.0.0.1:11434`. Verifica el modelo en `/api/tags` antes de consultar `/api/chat`. No invoca descargas. Mantener Ollama en modo local con nube desactivada y CPU, tal como en la prueba previa. El esquema JSON es obligatorio, con temperatura 0, `think: false`, contexto 2048, máximo 192 tokens y semilla 5700. El validador del laboratorio comprueba después el contrato y la presencia literal de la cita. Cada borrador queda pendiente de aprobación. [API local de Ollama](https://docs.ollama.com/api/chat)

## PowerShell

Utiliza Python 3.11 o posterior. Ejecuta primero el piloto, revisa que el esquema funcione y que se omitan las llamadas cuando hay preferencias registradas. Puede haber menos de siete llamadas por las guardas. Las siete entradas son independientes del corpus previo y del corpus congelado. Usa el mismo código y prompt en la evaluación completa.

```powershell
git clone --single-branch --branch feat/sabueso-ia-ollama-e02a https://github.com/Tortaconflow/SabuesoDigital.git Sabueso-E02A
Set-Location Sabueso-E02A
$piloto = Join-Path $env:TEMP "sabueso-e02a-piloto.json"
$completo = Join-Path $env:TEMP "sabueso-e02a-105.json"
py -3.11 -m sabueso_ia_lab.exp02.evaluar ollama --piloto --salida $piloto
py -3.11 -m sabueso_ia_lab.exp02.evaluar puntuar --piloto $piloto
py -3.11 -m sabueso_ia_lab.exp02.evaluar ollama --salida $completo
py -3.11 -m sabueso_ia_lab.exp02.evaluar puntuar $completo
```

Ante una interrupción, repite el comando `ollama` con la misma ruta de salida y las mismas opciones. Cada caso completa un guardado atómico con su ID. Los casos ya guardados se omiten. Si la interrupción llegó antes del guardado, solo se repite el caso en curso. Los errores reportados y guardados también forman parte de esa corrida y conservan su resultado de retorno al motor. Una corrida nueva usa otra ruta. Usa un proceso por archivo de salida. El evaluador rechaza reanudar si cambian el corpus, el modelo, el runtime, el código experimental o los parámetros. El comando `puntuar` requiere el corpus terminado.

Cada caso conserva latencia, estado, errores y abstención, además de los tokens de entrada y salida y duraciones del runtime cuando Ollama los informa. Los casos vetados carecen de medición de inferencia. La RAM del proceso Ollama queda `NOT_TESTED` en este adaptador. Para comparar contra el motor se usa el mismo evaluador y la referencia del corpus completo. Contrastar E02-A con llama.cpp no permite atribuir las diferencias al runtime, porque también cambia el modelo. Conserva los resultados y mantén el prompt fijo después de abrir las etiquetas o puntuar los 105 casos.
