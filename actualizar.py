"""
Sabueso Digital — actualización segura de la base de datos (Windows, macOS o Linux).

Uso (con Sabueso CERRADO):
    python actualizar.py estado              # qué tablas y cuántos registros hay
    python actualizar.py respaldo            # respaldo verificado (base + clave de seudónimos)
    python actualizar.py probar              # migra una COPIA temporal y compara; la base no se toca
    python actualizar.py migrar              # respaldo verificado + migración + verificación (revierte sola si falla)
    python actualizar.py revertir RESPALDO   # vuelve a un respaldo (antes respalda la base actual)

Para practicar con una copia:  $env:SABUESO_DB_PATH = "data\\copia_prueba.db"   (PowerShell)
Las migraciones solo AGREGAN tablas y columnas: nunca borran ni cambian registros.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault("SABUESO_SKIP_LEGACY_MIGRATION", "1")  # la herramienta nunca importa datos viejos por su cuenta

import config  # noqa: E402
import db  # noqa: E402

NOMBRE_CLAVE = "clave_seudonimos.key"


def _base() -> Path:
    return Path(config.get_database_path()).resolve()


def _conteos(ruta: Path) -> dict:
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        tablas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}
    finally:
        con.close()


def _columnas(ruta: Path) -> dict:
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        return {t: [c[1] for c in con.execute(f'PRAGMA table_info("{t}")')] for t in _conteos(ruta)}
    finally:
        con.close()


def _integridad(ruta: Path) -> str:
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()


def _copiar_sqlite(origen: Path, destino: Path):
    src = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    dst = sqlite3.connect(str(destino))
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()


def _exigir_cerrado(ruta: Path):
    """Si Sabueso está abierto la base puede estar en uso: se pide cerrarlo antes de cambiarla."""
    con = sqlite3.connect(str(ruta), timeout=1)
    try:
        con.execute("BEGIN EXCLUSIVE")
        con.rollback()
    except sqlite3.OperationalError:
        raise SystemExit("La base está en uso. Cierra Sabueso Digital y vuelve a intentarlo.")
    finally:
        con.close()


def _comparar(antes: dict, despues: dict) -> list:
    """Registros que se perdieron (debe quedar vacío)."""
    return [f"{t}: {n} → {despues.get(t, 0)}" for t, n in antes.items() if despues.get(t, 0) < n]


def estado():
    ruta = _base()
    if not ruta.exists():
        print(f"No existe la base {ruta}. Se creará al abrir Sabueso por primera vez.")
        return 0
    print(f"Base: {ruta}\nIntegridad: {_integridad(ruta)}")
    for t, n in _conteos(ruta).items():
        print(f"  {t}: {n}")
    clave = ruta.parent / NOMBRE_CLAVE
    print(f"Clave de seudónimos: {'presente' if clave.exists() else 'aún no creada (se crea al primer envío confirmado)'}")
    return 0


def respaldo(etiqueta="manual") -> dict:
    ruta = _base()
    if not ruta.exists():
        raise SystemExit(f"No existe la base {ruta}.")
    man = db.backup_and_verify_db(ruta, label=etiqueta)
    clave = ruta.parent / NOMBRE_CLAVE
    if clave.exists():
        destino = Path(man["backup_db_path"]).with_suffix(".key")
        shutil.copy2(clave, destino)
        man["clave_respaldo"] = str(destino)
    print(f"Respaldo verificado: {man['backup_db_path']}")
    if man.get("clave_respaldo"):
        print(f"Clave de seudónimos respaldada: {man['clave_respaldo']}")
    return man


def probar():
    ruta = _base()
    if not ruta.exists():
        raise SystemExit(f"No existe la base {ruta}.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copia = Path(tmp) / "copia.db"
        _copiar_sqlite(ruta, copia)
        antes, cols_antes = _conteos(copia), _columnas(copia)
        db.init_db(target_path=copia)
        despues, cols_despues = _conteos(copia), _columnas(copia)
        integ = _integridad(copia)
    perdidos = _comparar(antes, despues)
    nuevas = [t for t in despues if t not in antes]
    columnas = [f"{t}.{c}" for t in cols_despues for c in cols_despues[t] if t in cols_antes and c not in cols_antes[t]]
    print(f"Prueba sobre una copia de {ruta} (la base real no se tocó)")
    print(f"  Integridad después de migrar: {integ}")
    print(f"  Tablas nuevas: {', '.join(nuevas) or 'ninguna'}")
    print(f"  Columnas nuevas: {', '.join(columnas) or 'ninguna'}")
    print(f"  Registros perdidos: {', '.join(perdidos) or 'ninguno'}")
    ok = integ == "ok" and not perdidos
    print("RESULTADO: la migración es segura." if ok else "RESULTADO: NO migres; revisa los mensajes de arriba.")
    return 0 if ok else 1


def migrar():
    ruta = _base()
    if not ruta.exists():
        print("No hay base todavía: se creará con el esquema nuevo al abrir Sabueso.")
        return 0
    _exigir_cerrado(ruta)
    man = respaldo("antes_de_actualizar")
    antes = _conteos(ruta)
    try:
        db.init_db(target_path=ruta)
        integ, despues = _integridad(ruta), _conteos(ruta)
        perdidos = _comparar(antes, despues)
        if integ != "ok" or perdidos:
            raise RuntimeError(f"Verificación fallida (integridad: {integ}; perdidos: {perdidos}).")
    except Exception as exc:
        _copiar_sqlite(Path(man["backup_db_path"]), ruta)
        print(f"La migración falló y se restauró el respaldo automáticamente: {exc}")
        return 1
    print(f"Migración completa y verificada. Tablas nuevas: {', '.join(t for t in despues if t not in antes) or 'ninguna'}.")
    print(f"Si algo no te convence: python actualizar.py revertir \"{man['backup_db_path']}\"")
    return 0


def revertir(respaldo_ruta: str):
    origen = Path(respaldo_ruta).resolve()
    ruta = _base()
    if not origen.exists():
        raise SystemExit(f"No existe el respaldo {origen}.")
    if _integridad(origen) != "ok":
        raise SystemExit("El respaldo no pasa la verificación de integridad; no se usa.")
    if ruta.exists():
        _exigir_cerrado(ruta)
        respaldo("antes_de_revertir")
    _copiar_sqlite(origen, ruta)
    if _conteos(ruta) != _conteos(origen) or _integridad(ruta) != "ok":
        raise SystemExit("La restauración no coincide con el respaldo. No abras Sabueso y pide ayuda.")
    clave = ruta.parent / NOMBRE_CLAVE
    clave_resp = origen.with_suffix(".key")
    if not clave.exists() and clave_resp.exists():
        shutil.copy2(clave_resp, clave)
    print(f"Base restaurada desde {origen} ({datetime.now():%Y-%m-%d %H:%M}).")
    return 0


def main(argv):
    if len(argv) < 2 or argv[1] not in ("estado", "respaldo", "probar", "migrar", "revertir"):
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "revertir":
        if len(argv) < 3:
            print("Indica el archivo de respaldo: python actualizar.py revertir data\\backups\\sabueso_cidiks_....db")
            return 2
        return revertir(argv[2])
    if cmd == "respaldo":
        respaldo()
        return 0
    return {"estado": estado, "probar": probar, "migrar": migrar}[cmd]()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
