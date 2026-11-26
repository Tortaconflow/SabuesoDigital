"""Ollama local para E02-A. Usa exclusivamente el modelo ya instalado."""
import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from sabueso_ia_lab.exp02.local import Local, contrato

MODELO = "qwen3.5:4b"
OPCIONES = {"temperature": 0, "num_ctx": 2048, "num_predict": 192, "seed": 5700}


class Ollama(Local):
    def __init__(self, timeout):
        super().__init__(11434, None, timeout)
        self.medicion = None

    def identificar(self):
        version = self.solicitar("/api/version").get("version")
        modelos = self.solicitar("/api/tags").get("models", [])
        digest = next((m.get("digest") for m in modelos if m.get("name") == MODELO), None)
        if not isinstance(version, str) or not isinstance(digest, str) or not re.fullmatch(r"(sha256:)?[0-9a-f]{64}", digest):
            raise ValueError(f"Verifica que Ollama esté disponible y {MODELO} ya instalado.")
        return {"version": version, "modelo": MODELO, "digest": digest}

    def responder(self, texto, categorias):
        self.medicion = None
        esquema, mensajes = contrato(texto, categorias)
        respuesta = self.solicitar("/api/chat", {
            "model": MODELO, "messages": mensajes, "format": esquema,
            "stream": False, "think": False, "options": OPCIONES,
        })
        campos = ("prompt_eval_count", "eval_count", "total_duration", "load_duration",
                  "prompt_eval_duration", "eval_duration")
        self.medicion = {
            campo + ("_ns" if campo.endswith("_duration") else ""): respuesta.get(campo)
            for campo in campos
            if type(respuesta.get(campo)) is int and respuesta[campo] >= 0
        }
        if respuesta.get("done") is not True or respuesta.get("done_reason") != "stop":
            raise ValueError("generacion_incompleta")
        contenido = respuesta["message"]["content"]
        if type(contenido) is not str:
            raise ValueError("contenido_invalido")
        return contenido


def guardar(path, lote):
    """Snapshot atómico por caso, incluso si se interrumpe una escritura."""
    temporal = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf8", dir=path.parent, delete=False) as archivo:
            temporal = Path(archivo.name)
            json.dump(lote, archivo, ensure_ascii=False, indent=2)
            archivo.flush()
            os.fsync(archivo.fileno())
        temporal.replace(path)
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
