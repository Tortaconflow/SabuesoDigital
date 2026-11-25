"""
Procedimiento de actualización (actualizar.py): respaldo verificado, prueba sobre copia,
migración aditiva con verificación y reversión. Todo sobre bases temporales.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import actualizar
import db
import config

NUEVAS = ("aprendizaje_registro", "envios_huella", "consumo_ia")


@pytest.fixture
def base_vieja(tmp_path, monkeypatch):
    """Base con datos y SIN las tablas/columnas de las Fases 3 y 4 (como la de una PC sin actualizar)."""
    backups = tmp_path / "backups"
    backups.mkdir()
    monkeypatch.setattr(db, "BACKUPS_DIR", backups)
    ruta = Path(config.get_database_path())
    n = db.save_or_update_negocio({"nombre": "Posada del Sol", "sector": "Turismo y hospedaje", "web": "https://posadadelsol.com"})
    db.record_human_contact(n["id"], "llamada", "Hablé con el dueño")
    con = sqlite3.connect(ruta)
    for t in NUEVAS:
        con.execute(f"DROP TABLE {t}")
    con.execute("ALTER TABLE negocios DROP COLUMN qr_recibidos")
    con.commit()
    con.close()
    return ruta


def _tablas(ruta):
    con = sqlite3.connect(ruta)
    try:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def test_probar_no_toca_la_base(base_vieja, capsys):
    antes = base_vieja.read_bytes()
    assert actualizar.main(["x", "probar"]) == 0
    salida = capsys.readouterr().out
    assert "la migración es segura" in salida and "envios_huella" in salida and "negocios.qr_recibidos" in salida
    assert base_vieja.read_bytes() == antes


def test_migrar_respalda_agrega_y_no_pierde_registros(base_vieja):
    antes = actualizar._conteos(base_vieja)
    assert actualizar.main(["x", "migrar"]) == 0
    despues = actualizar._conteos(base_vieja)
    assert set(NUEVAS) <= set(despues) and all(despues[t] >= n for t, n in antes.items())
    assert "qr_recibidos" in actualizar._columnas(base_vieja)["negocios"]
    assert list(db.BACKUPS_DIR.glob("sabueso_cidiks_antes_de_actualizar_*.db"))


def test_revertir_vuelve_al_respaldo(base_vieja):
    assert actualizar.main(["x", "migrar"]) == 0
    resp = sorted(db.BACKUPS_DIR.glob("sabueso_cidiks_antes_de_actualizar_*.db"))[0]
    db.save_or_update_negocio({"nombre": "Negocio posterior", "web": "https://otro.example"})
    assert actualizar.main(["x", "revertir", str(resp)]) == 0
    assert not set(NUEVAS) & _tablas(base_vieja)
    assert actualizar._conteos(base_vieja)["negocios"] == 1
    assert list(db.BACKUPS_DIR.glob("sabueso_cidiks_antes_de_revertir_*.db"))  # la base previa también quedó respaldada


def test_respaldo_incluye_clave_de_seudonimos(base_vieja):
    import aprendizaje
    aprendizaje.clave_local()
    man = actualizar.respaldo("prueba")
    assert Path(man["clave_respaldo"]).read_bytes() == aprendizaje.ruta_clave().read_bytes()


def test_revertir_rechaza_respaldo_danado(base_vieja, tmp_path):
    malo = tmp_path / "malo.db"
    malo.write_bytes(b"no es sqlite" * 100)
    with pytest.raises((SystemExit, sqlite3.DatabaseError)):
        actualizar.main(["x", "revertir", str(malo)])
    assert actualizar._conteos(base_vieja)["negocios"] == 1
