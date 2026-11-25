"""
Fase 4: registro seudonimizado de errores y correcciones, huella de envíos confirmados,
comparación por estrategia con aviso de muestra chica y contador de tokens (0).
"""
import io
import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import aprendizaje as A
import db
from app import app, _regenerar_borradores
import conversacion


@pytest.fixture
def client(tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    backups.mkdir()
    monkeypatch.setattr(db, "BACKUPS_DIR", backups)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


HOTEL = {"nombre": "Posada del Sol", "sector": "Turismo y hospedaje", "municipio": "Puerto Escondido",
         "web": "https://posadadelsol.com", "whatsapp": "529541240793", "whatsapp_estado": "WHATSAPP_COMPROBADO"}


def _negocio(**extra):
    n = db.save_or_update_negocio(dict(HOTEL, **extra))
    _regenerar_borradores(n["id"])  # borradores del copiloto, como en la app
    return n


def _enviar(client, nid, mensaje):
    client.post("/api/prospects/whatsapp-open", json={"id": nid, "mensaje": mensaje})
    assert client.post("/api/prospects/contact-confirm", json={"id": nid, "canal": "whatsapp"}).status_code == 200


def test_seudonimo_hmac_con_clave_local_estable(tmp_path):
    a, b = A.seudonimo(7), A.seudonimo(7)
    assert a == b and a.startswith("p_") and len(a) == 18 and a != A.seudonimo(8)
    ruta = A.ruta_clave()
    assert ruta.parent == Path(db.config.get_database_path()).resolve().parent and len(ruta.read_bytes()) == 32
    ruta.write_bytes(b"corta")
    with pytest.raises(RuntimeError):
        A.seudonimo(7)  # nunca reemplaza una clave dañada en silencio


def test_anonimizar_quita_datos_personales():
    t = A.anonimizar("Soy Ana López de Posada del Sol, escríbeme a ana@correo.com o al 954 123 4567, ve posadadelsol.com y https://x.example/a",
                     nombres=["Posada del Sol"], dominios=["posadadelsol.com"])
    for dato in ("Ana", "López", "Posada del Sol", "ana@correo.com", "954 123 4567", "posadadelsol.com", "x.example"):
        assert dato not in t
    assert "[nombre]" in t and "[negocio]" in t and "[correo]" in t and "[teléfono]" in t


def test_correcciones_quedan_en_el_registro_sin_datos_personales(client):
    n = _negocio()
    texto = "Soy Ana de Posada del Sol, les comparto nuestro menú: 954 123 4567"
    sugerida = conversacion.clasificar_respuesta(texto)["categoria"]
    assert sugerida != "retroalimentacion"
    client.post("/api/interacciones/confirmar", json={"id": n["id"], "texto": texto, "clasificacion": "retroalimentacion"})
    client.post("/api/interacciones/confirmar", json={"id": n["id"], "texto": "Número equivocado", "clasificacion": "correccion", "sugerida": "correccion"})
    r = client.post("/api/prospects/identity-review", json={"id": n["id"], "decision": "corregir", "sector": "Restaurante", "nota": "Es restaurante"})
    assert r.status_code == 200, r.get_json()
    rep = client.get("/api/aprendizaje").get_json()
    tipos = sorted(x["tipo"] for x in rep["registro"])
    assert tipos == ["clasificacion_corregida", "dato_incorrecto", "identidad_corregida"]
    texto = json.dumps(rep, ensure_ascii=False)
    for dato in ("Posada del Sol", "Ana", "954 123 4567", "posadadelsol", f'"negocio_id"'):
        assert dato not in texto
    corr = next(x for x in rep["registro"] if x["tipo"] == "clasificacion_corregida")
    assert (corr["sugerido"], corr["corregido"]) == (sugerida, "retroalimentacion") and corr["seudonimo"] == A.seudonimo(n["id"])
    ident = next(x for x in rep["registro"] if x["tipo"] == "identidad_corregida")
    assert (ident["codigo"], ident["sugerido"], ident["corregido"]) == ("sector", "Turismo y hospedaje", "Restaurante")


def test_huella_de_envio_confirmado(client):
    n = _negocio()
    d = db.get_negocio_detail(n["id"])
    _enviar(client, n["id"], d["mensaje_personalizado"])  # sin editar
    n2 = _negocio(nombre="Hotel Marbella", web="https://hotelmarbella.example", whatsapp="529541111111")
    _enviar(client, n2["id"], "Hola, equipo de Hotel Marbella. ¿Tienen catálogo? ¿Cuándo platicamos?")  # editado, 2 preguntas
    rep = client.get("/api/aprendizaje").get_json()
    h1, h2 = sorted(rep["huellas"], key=lambda h: h["editado"])
    assert h1["plantilla"] == "mensaje_personalizado" and not h1["editado"] and h1["caracteres"] == len(d["mensaje_personalizado"])
    assert h2["editado"] and h2["preguntas"] == 2 and h2["estrategia"].startswith("comercial|mensaje_personalizado|")
    assert any(x["tipo"] == "mensaje_editado" for x in rep["registro"])
    assert "Hotel Marbella" not in json.dumps(rep, ensure_ascii=False)
    # una llamada no tiene mensaje
    n3 = _negocio(nombre="Cabañas Luna", web="https://lunaz.example", whatsapp="529583334455")
    client.post("/api/prospects/contact-confirm", json={"id": n3["id"], "canal": "llamada"})
    assert any(h["plantilla"] == "sin_mensaje" for h in client.get("/api/aprendizaje").get_json()["huellas"])


def test_comparacion_por_estrategia_y_muestra_chica(client):
    n = _negocio()
    _enviar(client, n["id"], db.get_negocio_detail(n["id"])["mensaje_personalizado"])
    client.post("/api/interacciones/confirmar", json={"id": n["id"], "texto": "¿Cuánto cobran?", "clasificacion": "contratacion"})
    est = client.get("/api/aprendizaje").get_json()["estrategias"]
    assert len(est) == 1 and est[0]["enviados"] == 1 and est[0]["interes"] == 1 and est[0]["respuestas_humanas"] == 1
    assert not est[0]["muestra_suficiente"] and "Muestra chica" in est[0]["aviso"]
    # Con muestra suficiente desaparece el aviso; una respuesta automática no cuenta como respuesta
    envios = [{"estrategia": "e", "resultado": A.resultado_envio(["automatica"])}] * 10
    e = A.comparar_estrategias(envios)[0]
    assert e["muestra_suficiente"] and e["aviso"] == "" and e["respuestas_humanas"] == 0 and e["tasa_respuesta"] == 0


def test_educativo_no_cuenta_como_interes():
    assert A.resultado_envio(["educativa"]) == "educativa" and A.resultado_envio(["orientacion"]) == "educativa"
    e = A.comparar_estrategias([{"estrategia": "educativa|mensaje_personalizado|general", "resultado": "educativa"}])[0]
    assert e["interes"] == 0 and e["educativas"] == 1


def test_huella_del_celular_y_tokens_en_cero(client):
    n = _negocio()
    huella = {"plantilla": "mensaje_calido", "estrategia": "comercial|mensaje_calido|catalogos", "caracteres": 90, "preguntas": 1, "editado": True}
    eventos = [{"id": "evt-hue-00000001", "tipo": "contacto_confirmado", "uid": f"pc-{n['id']}", "fecha": "2026-11-25T10:00:00",
                "datos": {"canal": "whatsapp", "fecha": "2026-11-25T10:00:00", "huella": huella}},
               {"id": "evt-hue-00000002", "tipo": "contacto_confirmado", "uid": f"pc-{n['id']}", "fecha": "2026-11-26T10:00:00",
                "datos": {"canal": "whatsapp", "fecha": "2026-11-26T10:00:00", "huella": {"plantilla": "<script>", "estrategia": "x"}}}]
    data = {"file": (io.BytesIO(json.dumps({"formato": "sabueso-movil-avances", "version": 1, "eventos": eventos}).encode()), "a.json")}
    assert client.post("/api/movil/import", data=data, content_type="multipart/form-data").get_json()["resumen"]["aplicados"] == 2
    client.post("/api/interacciones/analizar", json={"id": n["id"], "texto": "Hola"})
    client.post("/api/qr/interpretar", json={"texto": "https://wa.me/1"})
    rep = client.get("/api/aprendizaje").get_json()
    movil = [h for h in rep["huellas"] if h["fecha"].startswith("2026-11-25")][0]
    assert movil["estrategia"] == "comercial|mensaje_calido|catalogos" and movil["editado"]
    assert all("<script>" not in h["plantilla"] for h in rep["huellas"])
    tokens = {t["funcion"]: t for t in rep["tokens"]}
    assert set(tokens) >= {"copiloto", "clasificacion", "qr", "revision"}
    assert tokens["clasificacion"]["llamadas"] >= 1 and tokens["qr"]["llamadas"] == 1
    assert rep["tokens_total"] == 0 and all(t["tokens"] == 0 for t in rep["tokens"])


def test_exportar_informe_seudonimizado(client):
    n = _negocio()
    client.post("/api/interacciones/confirmar", json={"id": n["id"], "texto": "Les comparto nuestro menú", "clasificacion": "retroalimentacion"})
    r = client.get("/api/aprendizaje/exportar")
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"]
    rep = json.loads(r.data)
    assert "seudonimización, no anonimización" in rep["seudonimizacion"] and "Posada" not in r.data.decode()
