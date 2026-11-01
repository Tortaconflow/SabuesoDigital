import os
import sys
import time
import socket
import http.client
import json
import subprocess
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def check_sabueso_health(host="127.0.0.1", port=5000, timeout=1.0):
    """
    Comprobación de salud HTTP pura, segura y rápida.
    NO interpreta HTML, NO usa Internet Explorer y NO invoca PowerShell.
    """
    conn = None
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", "/api/status")
        resp = conn.getresponse()
        if resp.status == 200:
            data = resp.read()
            parsed = json.loads(data.decode("utf-8"))
            if "search_engine" in parsed or "gemini_configured" in parsed:
                return True, "Sabueso Digital 2.0 saludable y activo", parsed
            return True, "Servicio respondiendo en /api/status", parsed
        return False, f"HTTP {resp.status}", None
    except Exception as e:
        return False, str(e), None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

def is_port_busy(host="127.0.0.1", port=5000):
    """Verifica de forma no invasiva si un puerto TCP está abierto."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

def find_pid_on_port(port=5000):
    """Identifica el PID que tiene en escucha el puerto indicado en Windows."""
    try:
        cmd = f'netstat -ano | findstr ":{port}"'
        output = subprocess.check_output(cmd, shell=True, text=True)
        for line in output.strip().splitlines():
            if "LISTENING" in line:
                parts = line.strip().split()
                return int(parts[-1])
    except Exception:
        pass
    return None

def stop_server():
    """Detiene cualquier instancia de Sabueso que esté corriendo en el puerto 5000."""
    pid = find_pid_on_port(5000)
    if not pid:
        print("[SABUESO] No hay ningún servidor en ejecución en el puerto 5000.")
        return True

    is_healthy, msg, _ = check_sabueso_health()
    print(f"[SABUESO] Deteniendo servidor (PID {pid})...")
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, 15)
        time.sleep(1.0)
        print("[SABUESO] Servidor detenido correctamente.")
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo detener el proceso {pid}: {e}")
        return False

def start_server(open_browser=True):
    """Inicia el servidor Flask local de forma segura y sin duplicaciones."""
    # 1. Comprobar si ya existe una instancia activa y saludable
    is_healthy, msg, info = check_sabueso_health()
    if is_healthy:
        print(f"[SABUESO] El servidor ya se encuentra activo en http://127.0.0.1:5000/ ({msg}).")
        if open_browser:
            webbrowser.open("http://127.0.0.1:5000/")
        return True

    # 2. Comprobar si el puerto 5000 está ocupado por otro proceso
    if is_port_busy():
        pid = find_pid_on_port(5000)
        print(f"[ALERTA] El puerto 5000 está ocupado (PID {pid}). Verificando si es Sabueso iniciando...")
        for _ in range(3):
            time.sleep(1.0)
            is_healthy, msg, _ = check_sabueso_health()
            if is_healthy:
                print("[SABUESO] Servidor listo.")
                if open_browser:
                    webbrowser.open("http://127.0.0.1:5000/")
                return True

        print(f"[ERROR] Conflicto en el puerto 5000: proceso PID {pid} no responde como Sabueso Digital.")
        print("[SUGERENCIA] Ejecuta 'python launch.py --stop' para liberar el puerto si es una instancia colgada.")
        return False

    # 3. Iniciar el servidor local
    # Preferir pythonw si existe para no dejar consolas negras flotantes
    pythonw_candidate = Path(sys.prefix) / "pythonw.exe"
    executable = str(pythonw_candidate) if pythonw_candidate.exists() else sys.executable
    app_script = str(BASE_DIR / "app.py")
    log_file = BASE_DIR / "app.log"

    print(f"[SABUESO] Iniciando servidor Flask local con {Path(executable).name}...")

    # Registrar en app.log
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n--- [LAUNCHER] Inicio de Sabueso Digital 2.0: {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    except Exception:
        pass

    # En Windows, CREATE_NO_WINDOW (0x08000000) y CREATE_NEW_PROCESS_GROUP (0x00000200)
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = 0x08000000 | 0x00000200

    subprocess.Popen(
        [executable, app_script],
        cwd=str(BASE_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags
    )

    # 4. Esperar a que el servidor confirme salud mediante consulta HTTP segura
    print("[SABUESO] Esperando confirmación de inicio (salud HTTP)...")
    max_wait = 10.0
    start_t = time.time()
    while time.time() - start_t < max_wait:
        time.sleep(0.4)
        healthy, reason, _ = check_sabueso_health()
        if healthy:
            print("[SABUESO] ¡Servidor listo y verificado en http://127.0.0.1:5000/!")
            if open_browser:
                print("[SABUESO] Abriendo navegador...")
                webbrowser.open("http://127.0.0.1:5000/")
            return True

    print(f"[ERROR] El servidor no respondió dentro de los {max_wait} segundos previstos.")
    print(f"[ERROR] Revisa '{log_file}' para ver el detalle de la excepción.")
    return False

def main():
    args = sys.argv[1:]
    if "--status" in args:
        is_healthy, msg, info = check_sabueso_health()
        pid = find_pid_on_port(5000)
        print(f"Estado: {'SALUDABLE' if is_healthy else 'APAGADO/NO_DISPONIBLE'}")
        print(f"Detalle: {msg}")
        print(f"PID en puerto 5000: {pid or 'Ninguno'}")
        if info:
            print(f"Info: {json.dumps(info, ensure_ascii=False)}")
        return 0 if is_healthy else 1

    if "--stop" in args:
        return 0 if stop_server() else 1

    # Modo estándar de arranque (doble clic / lanzador)
    success = start_server(open_browser=True)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
