"""Dos comandos separados preservan las referencias fuera de la ejecución del modelo."""
import argparse
import hashlib
import http.client
import json
import os
import platform
import statistics
import time
from pathlib import Path

import reglas

from sabueso_ia_lab.core import MAX_ENTRADA, MAX_SALIDA, Laboratorio, Simulador, _interpretar
from sabueso_ia_lab.exp02.local import iniciar, pico_ram, ruta_local, sha256
from sabueso_ia_lab.exp02.ollama import OPCIONES, Ollama, guardar

RAIZ = Path(__file__).resolve().parent
LIMITES = {
    "ninguno": {},
    "preferencia": {"preferencias": ["Usar solo herramientas ya adoptadas"]},
    "conserva_web": {"memoria": [{"tipo": "servicio_conservado", "servicio": "web"}]},
    "bloqueado": {"bloqueado": True},
    "cerrado": {"prospeccion_cerrada": 1},
}


def leer(path):
    return [json.loads(linea) for linea in path.read_text(encoding="utf8").splitlines()]


def por_id(filas):
    indice = {fila["id"]: fila for fila in filas}
    if len(indice) != len(filas):
        raise ValueError("IDs duplicados")
    return indice


class LaboratorioLocal(Laboratorio):
    def __init__(self, servicio, categorias):
        super().__init__(Simulador({}))
        self.servicio = servicio
        self.categorias = categorias
        self.intento = "omitido"
        self.cita_inventada = False
        self.latencia = None
        self.error = None

    def _responder(self, entrada):
        inicio = time.perf_counter()
        self.intento = "recibido"
        texto = entrada["respuesta"]
        try:
            raw = self.servicio.responder(texto, self.categorias)
        except (OSError, ValueError, http.client.HTTPException, KeyError, IndexError, TypeError) as error:
            self.intento = "timeout" if isinstance(error, TimeoutError) else "error_proveedor"
            codigo = str(error)
            self.error = codigo if isinstance(error, ValueError) and (
                codigo in {"generacion_incompleta", "contenido_invalido", "http_longitud"}
                or (codigo.startswith("http_") and codigo[5:].isdigit())
            ) else type(error).__name__
            raise ValueError(self.intento) from error
        finally:
            self.latencia = round((time.perf_counter() - inicio) * 1000, 3)
        if len(raw.encode("utf8")) <= MAX_SALIDA:
            try:
                dato = json.loads(raw)
            except ValueError:
                dato = None
            cita = dato.get("cita") if isinstance(dato, dict) else None
            self.cita_inventada = isinstance(cita, str) and bool(cita.strip()) and cita not in texto
        return raw


def ejecutar(filas, servicio=None, *, guardar_caso=None):
    categorias = reglas.cargar_reglas()["respuestas"]["categorias"]
    resultados = []
    for fila in filas:
        if set(fila) != {"id", "respuesta", "limite"} or not 8 <= len(fila["respuesta"]) <= MAX_ENTRADA:
            raise ValueError("entrada de corpus inválida")
        # Un lab nuevo por caso. Un máximo de una consulta por fila y sin reintentos.
        lab = LaboratorioLocal(servicio, categorias) if servicio else Laboratorio(Simulador({}))
        prospecto = {**LIMITES[fila["limite"]], "respuesta": fila["respuesta"]}
        inicio = time.perf_counter()
        resultado = lab.analizar(prospecto, activar=servicio is not None)
        latencia = (time.perf_counter() - inicio) * 1000
        lectura = resultado["lectura"]
        certeza = lectura["certeza"] if lectura else None
        prediccion = lectura["categoria"] if lectura and (certeza != "incierta" or lectura["categoria"] == "rechazo") else resultado["categoria"]
        fila_resultado = {
            "id": fila["id"], "prediccion": prediccion, "motor": resultado["categoria"],
            "estado": resultado["estado"], "lectura_provisional": lectura,
            "borrador": resultado["borrador"], "recursos": resultado["recursos"],
            "aprobacion": resultado["aprobacion"],
            "latencia_total_ms": round(latencia, 3),
            "latencia_inferencia_ms": lab.latencia if servicio else None,
            "intento": lab.intento if servicio else "no_aplica",
            "cita_inventada": lab.cita_inventada if servicio else False,
        }
        if isinstance(servicio, Ollama):
            intento = lab.intento != "omitido"
            fila_resultado.update(
                error=lab.error or ("contrato_o_evidencia_invalidos" if intento and resultado["estado"] == "fallback" else None),
                abstencion=certeza == "incierta",
                ollama=servicio.medicion if intento else None,
            )
        resultados.append(fila_resultado)
        if guardar_caso is not None:
            guardar_caso(fila_resultado)
    return resultados


def percentiles(muestras):
    if not muestras:
        return "NOT_TESTED"
    orden = sorted(muestras)
    return {"p50": statistics.median(orden), "p95": orden[(95 * len(orden) + 99) // 100 - 1]}


def puntuar(predicciones, referencias):
    pred = por_id(predicciones)
    ref = por_id(referencias)
    if set(pred) != set(ref) or not ref:
        raise ValueError("conjuntos de IDs diferentes o vacíos")
    clases = sorted({f["categoria"] for f in referencias})
    matriz = {cat: {} for cat in clases}
    for id_, fila in ref.items():
        conteo = matriz[fila["categoria"]]
        categoria = pred[id_]["prediccion"]
        conteo[categoria] = conteo.get(categoria, 0) + 1
    metricas = {}
    for cat in clases:
        tp = matriz[cat].get(cat, 0)
        fp = sum(matriz[otra].get(cat, 0) for otra in clases if otra != cat)
        fn = sum(matriz[cat].values()) - tp
        metricas[cat] = {"precision": tp / (tp + fp) if tp + fp else 0,
                         "recall": tp / (tp + fn),
                         "f1": 2 * tp / (2 * tp + fp + fn)}
    intentos = [f for f in predicciones if f["intento"] not in {"omitido", "no_aplica"}]
    restringidos = [id_ for id_, f in ref.items() if f["sin_contacto"]]
    por_estrato = {}
    for id_, f in ref.items():
        desglose = por_estrato.setdefault(f["estrato"], {"aciertos": 0, "total": 0})
        desglose["total"] += 1
        desglose["aciertos"] += pred[id_]["prediccion"] == f["categoria"]
    inciertas = sum((f["lectura_provisional"] or {}).get("certeza") == "incierta" for f in intentos)
    return {
        "casos": len(ref),
        "exactitud": sum(matriz[c].get(c, 0) for c in clases) / len(ref),
        "macro_f1": statistics.mean(x["f1"] for x in metricas.values()),
        "por_clase": metricas, "confusion": matriz, "por_estrato": por_estrato,
        "llamadas_modelo": len(intentos),
        "abstenciones_incertidumbre": inciertas,
        "tasa_abstencion": inciertas / len(intentos) if intentos else "NOT_TESTED",
        "supresiones_por_rechazo_provisional": sum(f["estado"] == "abstencion" for f in intentos),
        "fallos_con_retorno_al_motor": sum(f["estado"] == "fallback" for f in intentos),
        "citas_inventadas_detectadas": sum(f["cita_inventada"] for f in intentos),
        "intenciones_con_cita_que_discrepan": sum(
            bool(f["lectura_provisional"]) and f["lectura_provisional"]["categoria"] != ref[f["id"]]["categoria"]
            for f in intentos),
        "casos_sin_contacto": len(restringidos),
        "violaciones": [id_ for id_ in restringidos if pred[id_]["borrador"] or pred[id_]["recursos"]],
        "latencia_total_ms": percentiles([f["latencia_total_ms"] for f in predicciones]),
        "latencia_inferencia_ms": percentiles([f["latencia_inferencia_ms"] for f in intentos]),
    }


def huella(path):
    return hashlib.sha256(path.read_text(encoding="utf8").encode("utf8")).hexdigest()


def ejecutar_ollama(path, filas, identidad, servicio):
    """Reanuda el prefijo guardado con la misma configuración y el mismo corpus."""
    if path.exists():
        lote = json.loads(path.read_text(encoding="utf8"))
        if any(lote.get(k) != v for k, v in identidad.items()):
            raise ValueError("El archivo pertenece a otra configuración, runtime, modelo o corpus.")
    else:
        lote = {**identidad, "predicciones": []}
    predicciones = lote["predicciones"]
    ids = [fila["id"] for fila in filas]
    if [fila["id"] for fila in predicciones] != ids[:len(predicciones)]:
        raise ValueError("El progreso no es un prefijo válido del corpus.")

    def avanzar(fila):
        predicciones.append(fila)
        guardar(path, lote)
        print(f"{len(predicciones)}/{len(filas)} {fila['id']} {fila['estado']}", flush=True)

    ejecutar(filas[len(predicciones):], servicio, guardar_caso=avanzar)


def main():
    parser = argparse.ArgumentParser()
    modos = parser.add_subparsers(dest="modo", required=True)
    motor = modos.add_parser("motor")
    local = modos.add_parser("local")
    ollama = modos.add_parser("ollama")
    ollama.add_argument("--piloto", action="store_true")
    ollama.add_argument("--timeout", type=int, default=60)
    puntaje = modos.add_parser("puntuar")
    puntaje.add_argument("--piloto", action="store_true")
    for sub in (motor, local, ollama):
        sub.add_argument("--salida", type=Path, required=True)
    local.add_argument("--exe", type=ruta_local, required=True)
    local.add_argument("--gguf", type=ruta_local, required=True)
    local.add_argument("--hilos", type=int, default=6)
    local.add_argument("--timeout", type=int, default=60)
    puntaje.add_argument("predicciones", type=Path)
    args = parser.parse_args()
    piloto = getattr(args, "piloto", False)
    entradas = RAIZ / ("piloto.jsonl" if piloto else "entradas.jsonl")
    if args.modo == "puntuar":
        lote = json.loads(args.predicciones.read_text(encoding="utf8"))
        if lote["entradas_sha256"] != huella(entradas):
            parser.error("La huella del corpus no coincide con el lote.")
        referencia = RAIZ / ("piloto_referencia.jsonl" if piloto else "referencia.jsonl")
        metricas = puntuar(lote["predicciones"], leer(referencia))
        if lote["ejecucion"]["brazo"] == "ollama":
            mediciones = [f["ollama"] for f in lote["predicciones"] if f["ollama"] is not None]
            metricas["ollama"] = {
                "errores": {f["id"]: f["error"] for f in lote["predicciones"] if f["error"]},
                "total_tokens_entrada": sum(m.get("prompt_eval_count", 0) for m in mediciones)
                if any("prompt_eval_count" in m for m in mediciones) else "NOT_TESTED",
                "total_tokens_salida": sum(m.get("eval_count", 0) for m in mediciones)
                if any("eval_count" in m for m in mediciones) else "NOT_TESTED",
                "respuestas_con_conteo": sum("eval_count" in m for m in mediciones),
            }
        print(json.dumps({"ejecucion": lote["ejecucion"], "referencia_sha256": huella(referencia),
                          "metricas": metricas}, ensure_ascii=False, indent=2))
        return

    filas = leer(entradas)
    esperadas = 7 if piloto else 105
    if len(por_id(filas)) != esperadas:
        parser.error(f"Esta corrida requiere exactamente {esperadas} entradas.")
    meta = {"brazo": args.modo, "plataforma": platform.platform(), "python": platform.python_version()}
    if args.modo == "ollama":
        if not 1 <= args.timeout <= 180:
            parser.error("El timeout debe estar entre 1 y 180 segundos.")
        servicio = Ollama(args.timeout)
        try:
            meta.update({
                "protocolo": "E02-A", "piloto": piloto, **servicio.identificar(),
                "opciones": OPCIONES, "think": False, "timeout_s": args.timeout,
                "pico_ram_proceso_bytes": "NOT_TESTED",
                "codigo_sha256": {
                    archivo.name: huella(archivo) for archivo in (
                        RAIZ / "evaluar.py", RAIZ / "local.py", RAIZ / "ollama.py", RAIZ.parent / "core.py"
                    )
                },
            })
            ejecutar_ollama(args.salida, filas, {
                "ejecucion": meta, "entradas_sha256": huella(entradas),
            }, servicio)
        except (OSError, ValueError, http.client.HTTPException) as error:
            parser.error(str(error))
        return
    if args.salida.exists():
        parser.error("El archivo de salida ya existe.")
    if args.modo == "local":
        if not 1 <= args.hilos <= 16 or not 1 <= args.timeout <= 180:
            parser.error("Rangos: 1–16 hilos y 1–180 segundos.")
        meta.update({"gguf": args.gguf.name, "gguf_sha256": sha256(args.gguf),
                     "exe_sha256": sha256(args.exe), "hilos": args.hilos,
                     "ctx": 2048, "timeout_s": args.timeout})
        with iniciar(args.exe, args.gguf, args.timeout, args.hilos) as (servicio, carga):
            # Medición aparte con texto ajeno al corpus, sin pasar referencias.
            primero = time.perf_counter()
            texto = "Ya recibimos tu mensaje. Buen día."
            categorias = reglas.cargar_reglas()["respuestas"]["categorias"]
            raw = servicio.responder(texto, categorias)
            try:
                _interpretar(raw, texto, categorias)
            except ValueError:
                meta["calentamiento_contrato"] = "invalidado"
            else:
                meta["calentamiento_contrato"] = "valido"
            meta.update({"carga_ms": carga, "primera_consulta_ms": (time.perf_counter() - primero) * 1000})
            predicciones = ejecutar(filas, servicio)
            meta["pico_ram_proceso_bytes"] = pico_ram(servicio.proceso.pid)
    else:
        reglas.cargar_reglas()
        predicciones = ejecutar(filas)
        meta["pico_ram_proceso_bytes"] = pico_ram(os.getpid())
    with args.salida.open("x", encoding="utf8") as destino:
        json.dump({"ejecucion": meta, "entradas_sha256": huella(entradas),
                   "predicciones": predicciones}, destino, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
