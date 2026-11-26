"""Pruebas de contrato y recuperación con doble de transporte, sin inferencia."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sabueso_ia_lab.evaluar import CASOS
from sabueso_ia_lab.exp02.evaluar import RAIZ, ejecutar, ejecutar_ollama, leer
from sabueso_ia_lab.exp02.ollama import Ollama


class OllamaE02A(unittest.TestCase):
    def test_piloto_independiente(self):
        filas = leer(RAIZ / "piloto.jsonl")
        ref = leer(RAIZ / "piloto_referencia.jsonl")
        congelado = {f["respuesta"] for f in leer(RAIZ / "entradas.jsonl")}
        self.assertEqual(len({f["estrato"] for f in ref}), 7)
        self.assertEqual([f["id"] for f in filas], [f["id"] for f in ref])
        self.assertFalse({f["respuesta"] for f in filas} & (congelado | {c.respuesta for c in CASOS}))

    def test_contrato_cita_y_telemetria(self):
        ollama = Ollama(60)
        fila = leer(RAIZ / "piloto.jsonl")[0]
        contenido = {"categoria": "contratacion", "servicio": "web",
                     "certeza": "explicita", "cita": "ya deposité el anticipo"}
        cuerpo = {"done": True, "done_reason": "stop", "eval_count": 36,
                  "message": {"content": json.dumps(contenido)}}
        with patch.object(ollama, "solicitar", return_value=cuerpo) as http:
            salida, = ejecutar([fila], ollama)
        (ruta, payload), _ = http.call_args
        self.assertEqual(ruta, "/api/chat")
        self.assertEqual(payload["options"]["num_ctx"], 2048)
        self.assertEqual(payload["options"]["temperature"], 0)
        self.assertEqual(payload["options"]["num_predict"], 192)
        self.assertIs(payload["think"], False)
        self.assertIs(payload["format"]["additionalProperties"], False)
        self.assertEqual(json.loads(payload["messages"][1]["content"]), {"respuesta": fila["respuesta"]})
        self.assertTrue(salida["cita_inventada"])
        self.assertEqual(salida["estado"], "fallback")
        self.assertEqual(salida["ollama"]["eval_count"], 36)
        self.assertEqual(salida["aprobacion"], "pendiente")

    def test_reanuda_sin_repetir_y_rechaza_cambio(self):
        filas = leer(RAIZ / "piloto.jsonl")[:2]
        identidad = {"ejecucion": {"digest": "A"}}
        predicciones = ejecutar(filas)
        with tempfile.TemporaryDirectory() as directorio:
            salida = Path(directorio) / "salida.json"

            def interrumpir(faltantes, servicio, guardar_caso):
                self.assertEqual(faltantes, filas)
                guardar_caso(predicciones[0])
                raise KeyboardInterrupt

            def continuar(faltantes, servicio, guardar_caso):
                self.assertEqual(faltantes, filas[1:])
                guardar_caso(predicciones[1])

            with patch("sabueso_ia_lab.exp02.evaluar.ejecutar", side_effect=interrumpir):
                with self.assertRaises(KeyboardInterrupt):
                    ejecutar_ollama(salida, filas, identidad, None)
            with patch("sabueso_ia_lab.exp02.evaluar.ejecutar", side_effect=continuar):
                ejecutar_ollama(salida, filas, identidad, None)
            lote = json.loads(salida.read_text(encoding="utf8"))
            self.assertEqual(lote["predicciones"], predicciones)
            with self.assertRaises(ValueError):
                ejecutar_ollama(salida, filas, {"ejecucion": {"digest": "B"}}, None)
