import os
import sys
import subprocess
from pathlib import Path

def create_windows_shortcuts():
    project_dir = Path(__file__).resolve().parent
    bat_path = project_dir / "iniciar_sabueso.bat"
    ico_path = project_dir / "sabueso_app_icon.ico"
    desktop = Path(os.path.expanduser("~/Desktop"))

    # 1. Crear / Actualizar acceso directo .lnk en Escritorio
    lnk_path = desktop / "Sabueso Digital.lnk"
    ps_command = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{lnk_path}')
    $Shortcut.TargetPath = '{bat_path}'
    $Shortcut.WorkingDirectory = '{project_dir}'
    $Shortcut.IconLocation = '{ico_path}, 0'
    $Shortcut.Description = 'Sabueso Digital 2.0 - CÍDIKS Sales Engine'
    $Shortcut.WindowStyle = 7
    $Shortcut.Save()
    """

    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[ACCESO DIRECTO] Acceso directo .lnk creado exitosamente en {lnk_path}")
    else:
        print(f"[ERROR] No se pudo crear acceso directo .lnk: {res.stderr}")

    # 2. Actualizar también el archivo .url para usar 127.0.0.1
    url_path = desktop / "Sabueso Digital.url"
    url_content = f"""[InternetShortcut]
URL=http://127.0.0.1:5000/
IconIndex=0
IconFile={ico_path}
"""
    try:
        url_path.write_text(url_content, encoding="utf-8")
        print(f"[ACCESO DIRECTO] Acceso directo .url actualizado en {url_path}")
    except Exception as e:
        print(f"[AVISO] No se pudo actualizar archivo .url: {e}")

if __name__ == "__main__":
    create_windows_shortcuts()
