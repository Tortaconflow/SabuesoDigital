import os
import sys
import time
import json
import socket
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
import launch
import db

def test_full_real_launch_lifecycle():
    print("\n============================================================")
    print("   PRUEBA REAL DE ARRANQUE Y CICLO DE VIDA - SABUESO 2.0")
    print("============================================================")

    # Si estamos en entorno aislado de pytest, sembrar un registro en la base temporal
    if config.is_test_environment() and len(db.get_all_negocios()) == 0:
        db.save_or_update_negocio({
            "nombre": "Hotel Arranque Aislado",
            "sector": "Turismo y hospedaje",
            "municipio": "Puerto Escondido",
            "prioridad": "high",
            "estado_comercial": "investigado"
        })

    # Paso 1: Asegurar estado inicial limpio
    print("\n[Paso 1] Asegurando que el puerto 5000 esté libre al inicio...")
    launch.stop_server()
    time.sleep(1.0)
    assert not launch.is_port_busy(), "El puerto 5000 debería estar libre antes de comenzar"
    print("  -> Puerto 5000 libre correctamente.")

    # Paso 2: Arranque inicial en frío mediante el lanzador
    print("\n[Paso 2] Ejecutando arranque en frío con launch.py...")
    started = launch.start_server(open_browser=False)
    assert started is True, "El servidor debió arrancar exitosamente"
    print("  -> Servidor arrancó y reportó confirmación de salud.")

    # Paso 3: Consultas HTTP reales al servidor activo
    print("\n[Paso 3] Verificando endpoints y consulta de prospectos en SQLite...")
    # 3.1 Interfaz web principal
    req_index = urllib.request.urlopen("http://127.0.0.1:5000/", timeout=3.0)
    assert req_index.status == 200
    html = req_index.read().decode("utf-8")
    assert "Sabueso Digital 2.0" in html, "El HTML debe contener la marca Sabueso Digital 2.0"
    print("  -> GET /: OK (HTTP 200, interfaz cargada)")

    # 3.2 Endpoint de estado
    req_status = urllib.request.urlopen("http://127.0.0.1:5000/api/status", timeout=3.0)
    assert req_status.status == 200
    status_data = json.loads(req_status.read().decode("utf-8"))
    assert "search_engine" in status_data
    print(f"  -> GET /api/status: OK ({status_data.get('search_engine')})")

    # 3.3 Consulta de prospectos de base de datos
    req_prospects = urllib.request.urlopen("http://127.0.0.1:5000/api/prospects", timeout=3.0)
    assert req_prospects.status == 200
    prospects = json.loads(req_prospects.read().decode("utf-8"))
    assert len(prospects) > 0, "La base SQLite debe contener los prospectos preservados"
    print(f"  -> GET /api/prospects: OK ({len(prospects)} prospectos recuperados de SQLite)")

    # Paso 4: Detección y prevención de servidores duplicados
    print("\n[Paso 4] Probando protección contra instancias duplicadas...")
    pid_inicial = launch.find_pid_on_port(5000)
    assert pid_inicial is not None
    # Intentar arrancar otra vez mientras ya está activo
    second_launch = launch.start_server(open_browser=False)
    assert second_launch is True
    pid_actual = launch.find_pid_on_port(5000)
    assert pid_inicial == pid_actual, "No debe crearse un nuevo proceso ni cambiar el PID del servidor ya activo"
    print(f"  -> Protección anti-duplicados: OK (PID conservado: {pid_actual})")

    # Paso 5: Cerrar el servidor
    print("\n[Paso 5] Probando detención controlada del servidor...")
    stopped = launch.stop_server()
    assert stopped is True
    time.sleep(1.0)
    assert not launch.is_port_busy(), "El puerto 5000 debe quedar libre tras detener el servidor"
    print("  -> Servidor detenido exitosamente y puerto liberado.")

    # Paso 6: Segundo arranque y persistencia tras reinicio
    print("\n[Paso 6] Probando segundo arranque y conservación de datos...")
    restarted = launch.start_server(open_browser=False)
    assert restarted is True

    req_prospects2 = urllib.request.urlopen("http://127.0.0.1:5000/api/prospects", timeout=3.0)
    prospects2 = json.loads(req_prospects2.read().decode("utf-8"))
    assert len(prospects2) == len(prospects), "Los prospectos deben ser idénticos tras reiniciar el servidor"
    print(f"  -> Segundo arranque: OK ({len(prospects2)} prospectos intactos en SQLite)")

    # Paso 7: Detección de conflicto de puerto
    print("\n[Paso 7] Probando detección de conflicto en puerto 5000...")
    launch.stop_server()
    time.sleep(1.0)
    # Crear socket ficticio que ocupe el puerto 5000 pero no sea Sabueso
    dummy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dummy_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    dummy_sock.bind(("127.0.0.1", 5000))
    dummy_sock.listen(1)
    print("  -> Socket simulador de conflicto abierto en 127.0.0.1:5000.")

    # launch.py debe detectar el conflicto y no crashear
    conflict_detected = launch.start_server(open_browser=False)
    assert conflict_detected is False, "El lanzador debe rechazar iniciar cuando el puerto está ocupado por otro servicio"
    print("  -> Detección de conflicto: OK (Servidor rechazó duplicar y reportó el problema de forma controlada)")

    dummy_sock.close()
    time.sleep(0.5)

    # Paso 8: Arranque final limpio
    print("\n[Paso 8] Arranque final para verificar disponibilidad...")
    final_start = launch.start_server(open_browser=False)
    assert final_start is True
    if config.is_test_environment():
        # En pytest, detener el servidor temporal para no retener el archivo en tmp_path
        launch.stop_server()
    else:
        print("  -> Aplicación Sabueso Digital 2.0 lista y activa en http://127.0.0.1:5000/")
    print("\n============================================================")
    print("   ¡TODAS LAS PRUEBAS DE ARRANQUE REAL FUERON EXITOSAS!")
    print("============================================================")

if __name__ == "__main__":
    test_full_real_launch_lifecycle()
