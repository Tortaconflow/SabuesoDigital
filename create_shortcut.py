import os
import subprocess
from pathlib import Path

def create_windows_shortcut():
    project_dir = Path(__file__).resolve().parent
    bat_path = project_dir / "iniciar_sabueso.bat"
    ico_path = project_dir / "sabueso_app_icon.ico"
    desktop = Path(os.path.expanduser("~/Desktop"))
    lnk_path = desktop / "Sabueso Digital.lnk"

    # PowerShell script to create Windows shell shortcut
    ps_command = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{lnk_path}')
    $Shortcut.TargetPath = '{bat_path}'
    $Shortcut.WorkingDirectory = '{project_dir}'
    $Shortcut.IconLocation = '{ico_path}, 0'
    $Shortcut.Description = 'Sabueso Digital 2.0 - CÍDIKS Sales Engine'
    $Shortcut.Save()
    """

    print(f"[ACCESO DIRECTO] Creando acceso directo en: {lnk_path}")
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], capture_output=True, text=True)
    if res.returncode == 0:
        print("[ACCESO DIRECTO] Acceso directo .lnk creado exitosamente con icono y lanzador automático.")
    else:
        print(f"[ERROR] No se pudo crear acceso directo .lnk: {res.stderr}")

if __name__ == "__main__":
    create_windows_shortcut()
