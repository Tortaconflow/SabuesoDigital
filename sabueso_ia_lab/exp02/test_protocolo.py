"""Verificaciones del corpus y evaluador. No ejecutan un modelo."""
import unittest

from sabueso_ia_lab.evaluar import CASOS
from sabueso_ia_lab.exp02.evaluar import RAIZ, ejecutar, leer, por_id, puntuar


class Protocolo(unittest.TestCase):
    def test_corpus_separado_y_nuevo(self):
        entradas = leer(RAIZ / "entradas.jsonl")
        referencia = leer(RAIZ / "referencia.jsonl")
        self.assertEqual(len(por_id(entradas)), 105)
        self.assertEqual(set(por_id(entradas)), set(por_id(referencia)))
        textos = {f["respuesta"] for f in entradas}
        self.assertEqual(len(textos), 105)
        self.assertFalse(textos & {c.respuesta for c in CASOS})
        self.assertTrue(all(set(f) == {"id", "respuesta", "limite"} for f in entradas))

    def test_motor_y_matriz(self):
        entradas = leer(RAIZ / "entradas.jsonl")
        predicciones = ejecutar(entradas)
        referencia = leer(RAIZ / "referencia.jsonl")
        self.assertTrue(all(f["aprobacion"] == "pendiente" for f in predicciones))
        for entrada, pred in zip(entradas, predicciones):
            if entrada["limite"] != "ninguno":
                self.assertFalse(pred["borrador"] or pred["recursos"])
        m = puntuar(predicciones, referencia)
        self.assertEqual(sum(sum(f.values()) for f in m["confusion"].values()), 105)
        self.assertEqual(m["llamadas_modelo"], 0)
        self.assertEqual(m["latencia_inferencia_ms"], "NOT_TESTED")
        with self.assertRaises(ValueError):
            puntuar(predicciones[:-1], referencia)
