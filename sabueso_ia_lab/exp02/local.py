"""Adaptador experimental de un proceso llama-server propio, enlazado a loopback."""
import ctypes
import hashlib
import http.client
import json
import os
import secrets
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from sabueso_ia_lab.core import INSTRUCCION, SERVICIOS

MAX_HTTP = 65536


def sha256(path):
    with path.open("rb") as archivo:
        return hashlib.file_digest(archivo, "sha256").hexdigest()


def pico_ram(pid):
    """PeakWorkingSetSize del proceso en Windows. Incluye páginas compartidas residentes."""
    if os.name != "nt":
        return "NOT_TESTED"
    from ctypes import wintypes

    class Contadores(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("fallos", wintypes.DWORD),
            *((campo, ctypes.c_size_t) for campo in (
                "pico", "actual", "pico_pool_paginado", "pool_paginado",
                "pico_pool_no_paginado", "pool_no_paginado", "pagefile", "pico_pagefile"
            )),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    abrir = kernel.OpenProcess
    abrir.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    abrir.restype = wintypes.HANDLE
    cerrar = kernel.CloseHandle
    cerrar.argtypes = [wintypes.HANDLE]
    consultar = kernel.K32GetProcessMemoryInfo
    consultar.argtypes = [wintypes.HANDLE, ctypes.POINTER(Contadores), wintypes.DWORD]
    handle = abrir(0x0400 | 0x0010, False, pid)
    if not handle:
        return "NOT_TESTED"
    try:
        contadores = Contadores()
        contadores.cb = ctypes.sizeof(contadores)
        return contadores.pico if consultar(handle, ctypes.byref(contadores), contadores.cb) else "NOT_TESTED"
    finally:
        cerrar(handle)


class Local:
    def __init__(self, puerto, clave, timeout, proceso):
        self.puerto = puerto
        self.clave = clave
        self.timeout = timeout
        self.proceso = proceso

    def solicitar(self, ruta, datos=None, timeout=None):
        # Conexión directa. Sin proxy, redirecciones ni URL configurable.
        conexion = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=timeout or self.timeout)
        try:
            conexion.request("GET" if datos is None else "POST", ruta,
                             body=None if datos is None else json.dumps(datos).encode(),
                             headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.clave}"})
            respuesta = conexion.getresponse()
            if respuesta.status != 200:
                raise ValueError(f"http_{respuesta.status}")
            cuerpo = respuesta.read(MAX_HTTP + 1)
            if len(cuerpo) > MAX_HTTP:
                raise ValueError("http_longitud")
            return json.loads(cuerpo)
        finally:
            conexion.close()

    def responder(self, texto, categorias):
        propiedades = {
            "categoria": {"type": "string", "enum": sorted(categorias)},
            "servicio": {"type": "string", "enum": sorted(SERVICIOS)},
            "certeza": {"type": "string", "enum": ["explicita", "inferida", "incierta"]},
            "cita": {"type": "string", "minLength": 8, "maxLength": 180},
        }
        esquema = {"type": "object", "properties": propiedades, "required": list(propiedades),
                   "additionalProperties": False}
        sistema = (
            INSTRUCCION + " Cita entre 8 y 180 caracteres exactos del campo respuesta. "
            "La categoría humana cubre acuses y ambigüedad sin intención clara. Distingue orientación "
            "personalizada, solicitud de material educativo e intención explícita de contratar. "
            "Un cierre implícito también es rechazo. Si la intención es incierta elige certeza incierta. "
            "Las etiquetas válidas son: " + ", ".join(sorted(categorias)) +
            ". Servicios válidos: " + ", ".join(sorted(SERVICIOS)) + "."
        )
        datos = {
            "model": "sabueso-e02", "temperature": 0, "seed": 5700, "max_tokens": 192,
            "stream": False, "cache_prompt": False,
            "response_format": {"type": "json_schema", "json_schema": {"name": "lectura_sabueso", "strict": True, "schema": esquema}},
            "messages": [{"role": "system", "content": sistema},
                         {"role": "user", "content": json.dumps({"respuesta": texto}, ensure_ascii=False)}],
        }
        respuesta = self.solicitar("/v1/chat/completions", datos)
        candidato = respuesta["choices"][0]
        if candidato["finish_reason"] != "stop":
            raise ValueError("generacion_incompleta")
        contenido = candidato["message"]["content"]
        if type(contenido) is not str:
            raise ValueError("contenido_invalido")
        return contenido


@contextmanager
def iniciar(exe, modelo, timeout, hilos):
    if not exe.is_file() or not modelo.is_file() or modelo.suffix.lower() != ".gguf":
        raise ValueError("Se requieren ejecutable y GGUF locales existentes.")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        puerto = sock.getsockname()[1]
    clave = secrets.token_hex(24)
    args = [str(exe), "-m", str(modelo), "--alias", "sabueso-e02", "--host", "127.0.0.1",
            "--port", str(puerto), "--api-key", clave, "-ngl", "0", "-c", "2048", "-np", "1", "-t", str(hilos)]
    inicio = time.perf_counter()
    with subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as proceso:
        servicio = Local(puerto, clave, timeout, proceso)
        try:
            while time.perf_counter() - inicio < 180:
                if proceso.poll() is not None:
                    raise RuntimeError(f"llama-server terminó al cargar: código {proceso.returncode}")
                try:
                    estado = servicio.solicitar("/health", timeout=1)
                except (OSError, ValueError, http.client.HTTPException):
                    time.sleep(0.25)
                    continue
                if estado.get("status") == "ok":
                    break
            else:
                raise TimeoutError("llama-server no estuvo listo en 180 s")
            yield servicio, round((time.perf_counter() - inicio) * 1000, 3)
        finally:
            if proceso.poll() is None:
                proceso.kill()
                proceso.wait()


def ruta_local(texto):
    return Path(texto).resolve(strict=True)
