"""
Paridad PC ⇄ celular: docs/motor.js debe dar exactamente lo mismo que Python
(reglas.py, validacion.py, contact_identity.py, copilot.py) para los mismos casos.
Se omite si Node no está instalado (p. ej. en Windows sin Node).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import contact_identity
import copilot
import reglas as R
import validacion as V

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js no está instalado")

CONTEXTO = [
    {"id": 50, "nombre": "Posada Mar Azul", "web": "https://posadamarazul.example", "whatsapp": "529541234567"},
    {"id": 51, "nombre": "Diseños Web Costa", "web": "https://disenoscosta.example", "telefono": "958 111 2233", "municipio": "Mazunte"},
]

CASOS = [
    {"id": 1, "nombre": "Muebles Rústicos del Valle", "sector": "Mobiliario", "municipio": "Oaxaca de Juárez", "web": "https://mueblesrusticos.example", "whatsapp": "529511234567", "whatsapp_estado": "WHATSAPP_COMPROBADO", "telefono": "9511234567"},
    {"id": 2, "nombre": "Muebles Rústicos del Valle", "sector": "Turismo y hospedaje", "municipio": "Oaxaca de Juárez", "web": "https://mueblesrusticos.example", "whatsapp": "529511234567"},
    {"id": 3, "nombre": "Hotel Casa Azul", "sector": "Turismo y hospedaje", "municipio": "Puerto Escondido", "web": "https://hotelmarbella-pxm.example", "whatsapp": "529547778899", "whatsapp_estado": "WHATSAPP_COMPROBADO"},
    {"id": 4, "nombre": "Posada del Sol", "sector": "Turismo y hospedaje", "municipio": "Puerto Escondido", "web": "https://posadadelsol.com", "whatsapp": "529541240793", "whatsapp_estado": "WHATSAPP_COMPROBADO", "servicio_sugerido": "catalogos", "_force_explicit": True},
    {"id": 5, "nombre": "Hotel Las Palmas", "sector": "Turismo y hospedaje", "municipio": "Mazunte", "web": "", "telefono": "9581112222", "necesidad_expresada": "Necesitamos un CRM para dar seguimiento a nuestros clientes"},
    {"id": 29, "nombre": "Hotel El Alquimista Yoga Spa", "web": "https://elalquimistahotel.mx/contacto/", "telefono": "+52 958 587 8961", "whatsapp": "529585878961", "whatsapp_estado": "WHATSAPP_PENDIENTE_VERIFICACION", "fuente_whatsapp": "subpagina_contacto", "servicio_sugerido": "flyers"},
    {"id": 4, "nombre": "Hotel Escondido", "web": "https://www.hotelescondido.com/", "whatsapp": "", "whatsapp_estado": "SIN_WHATSAPP_COMPROBABLE"},
    {"id": 2, "nombre": "Hotel Monte Casino", "web": "https://www.jmcs.org.mx/plugins/generic/pdfJsViewer/pdf.js/web/viewer.html?file=test"},
    {"nombre": "Cabañas Luna Nueva", "sector": "Hospedaje", "municipio": "Mazunte", "whatsapp": "+529581112233", "whatsapp_estado": "confirmado", "fuente": "maps", "identidad_verificada": 1},
    {"id": 7, "nombre": "Hotel Uno", "municipio": "Mazunte", "web": "https://hoteluno.example", "whatsapp": "529581112233"},
    {"id": 8, "nombre": "Hotel Mar", "web": "https://www.tripadvisor.com.mx/Hotel_Review-x", "telefono": "9541112233"},
    {"id": 9, "nombre": "Hotel Posada Real Resort", "sector": "Hospedaje", "municipio": "Puerto Escondido", "web": "https://hotelenpuertoescondido.com", "whatsapp": "529541639198", "whatsapp_estado": "WHATSAPP_COMPROBADO"},
    {"id": 10, "nombre": "Clínica Dental Sonrisa", "sector": "Salud", "municipio": "Oaxaca de Juárez", "web": "https://dentalsonrisa.example", "whatsapp": "529511112222", "whatsapp_estado": "WHATSAPP_COMPROBADO"},
    {"id": 11, "nombre": "Artesanías Don Benito", "sector": "Comercio", "municipio": "Oaxaca Centro", "web": "https://artesaniasdonbenito.com", "checks": {"responsive": False}},
    {"id": 12, "nombre": "Señor Ñandú & Cía", "municipio": "", "web": "https://senornandu.example", "telefono": "954 123 4567"},
    {"id": 13, "nombre": "Restaurante La Palapa de Mazunte", "sector": "Restaurante", "municipio": "Mazunte", "web": "", "whatsapp": "529581239876", "whatsapp_estado": "WHATSAPP_COMPROBADO"},
]
CASOS.append(dict(CASOS[2], id=14))
# Fase 2: conversación, memoria, cierre, relación educativa y seguimiento (fecha fija)
CONTACTADO = {"fecha_contacto_confirmada": "2026-11-20T10:00:00", "primer_contacto_fecha": "2026-11-20T10:00:00",
              "contactos_confirmados_n": 1, "estado_comercial": "contactado"}
CASOS += [
    {"id": 20, "nombre": "Hotel Las Palmas", "sector": "Turismo y hospedaje", "municipio": "Puerto Escondido", "web": "https://laspalmas.example",
     "telefono": "9541112222", "servicio_sugerido": "web", "respuesta": "Gracias, estamos contentos con nuestra página y queremos conservarla."},
    dict({"id": 21, "nombre": "Cabañas Luna", "sector": "Turismo y hospedaje", "municipio": "Zipolite", "web": "https://lunaz.example",
          "whatsapp": "529583334455", "respuesta": "No nos interesa, por favor no vuelvan a escribir."}, **CONTACTADO),
    {"id": 22, "nombre": "Posada del Sol", "sector": "Turismo y hospedaje", "municipio": "Puerto Escondido", "web": "https://posadadelsol.com",
     "whatsapp": "529541240793", "whatsapp_estado": "WHATSAPP_COMPROBADO", "servicio_sugerido": "web", "_force_explicit": True,
     "memoria": [{"tipo": "necesidad", "servicio": "crm", "texto": "Necesitamos ordenar clientes", "fuente": "humano"},
                 {"tipo": "servicio_rechazado", "servicio": "web", "texto": "No queremos página", "fuente": "prospecto", "vigente": None}]},
    {"id": 23, "nombre": "Dulces de la Facultad", "sector": "Comercio", "municipio": "Oaxaca de Juárez", "whatsapp": "529511230000",
     "whatsapp_estado": "confirmado", "tipo_relacion": "educativa", "_hoy": "2026-11-25"},
    dict({"id": 24, "nombre": "Posada del Sol", "sector": "Hospedaje", "municipio": "Puerto Escondido", "web": "https://posadadelsol.com",
          "whatsapp": "529541240793", "whatsapp_estado": "WHATSAPP_COMPROBADO", "_hoy": "2026-11-22"}, **CONTACTADO),
    dict({"id": 25, "nombre": "Posada del Sol", "sector": "Hospedaje", "municipio": "Puerto Escondido", "web": "https://posadadelsol.com",
          "whatsapp": "529541240793", "whatsapp_estado": "WHATSAPP_COMPROBADO", "_hoy": "2026-11-26",
          "respuesta": "Gracias por comunicarte, en breve te atenderemos"}, **CONTACTADO),
    dict({"id": 26, "nombre": "Posada del Sol", "sector": "Hospedaje", "municipio": "Puerto Escondido", "web": "https://posadadelsol.com",
          "whatsapp": "529541240793", "prospeccion_reabierta": 1, "ultima_clasificacion": "rechazo", "_hoy": "2026-11-26"}, **CONTACTADO),
]
RESPUESTAS = [
    "¡Hola! Gracias por comunicarte con Posada Sol. En breve te atenderemos.", "No nos interesa, gracias.",
    "Número equivocado, no somos un hotel.", "Me sirvió mucho la guía, gracias", "Quiero aprender a vender por WhatsApp con catálogo",
    "¿Por dónde empiezo para tener catálogo?", "¿Cuánto cobran por una página web?", "Les comparto nuestro menú", "Me interesa, platiquemos",
    "¿Tienen algún curso gratis de WhatsApp Business?", "Quiero aprender inteligencia artificial para mi negocio",
    "Estamos contentos con nuestra página y queremos conservarla. Solo nos interesa algo para Instagram. No tenemos presupuesto, escríbanme a ana@correo.com o al 954 123 4567.",
]
CASOS[-1]["identidad_revisada_firma"] = V.firma_identidad(CASOS[-1])

MENSAJES = [
    ("Hola, equipo de Hotel Marbella. Les escribo de CÍDIKS. ¿Atienden reservaciones por WhatsApp?", 2),
    ("Hola, equipo de Muebles Rústicos del Valle. Les escribo de CÍDIKS. ¿Comparten tarifas de habitaciones por WhatsApp?", 0),
    ("Hola. Le ofrecemos soluciones integrales para llevar su negocio al siguiente nivel con SEO. ¿Le interesa? ¿Cuándo?", 3),
    ("Hola, equipo de Hotel Casa Azul. Trabajamos con Posada Mar Azul. ¿Atienden por WhatsApp?", 2),
    ("Hola, buen día. Equipo de Posada del Sol: les escribo de CÍDIKS. ¿Atienden por WhatsApp? " + "x " * 70, 3),
    ("Hola, equipo de Muebles Rústicos del Valle. ¿Venden muebles para habitación por WhatsApp?", 0),
    ("Hola, borrador editado antes de abrir WhatsApp", 3),
    ("Hola, soy Ana de CÍDIKS. Vi la página. ¿Atienden por WhatsApp?", 3),
    ("Buen día, equipo de Hotel Marbella de nuevo. ¿Atienden por WhatsApp?", 2),
]
TELEFONOS = ["+52 (954) 123-4567", "954 123 4567", "529541234567", "5219541234567", "0052 954 123 4567", "954-FLORES", "1234", "+1 (555) 123-4567"]

CAMPOS = ("servicio_sugerido", "fuente_servicio", "sector_id", "bloqueado_envio", "identidad_verificada", "tipo_observacion",
          "pregunta_comercial", "mensaje_personalizado", "mensaje_calido", "mensaje_seguimiento", "hipotesis_comercial",
          "observacion_verificada", "modalidad", "consumo_tokens")


def _resumen_generacion(res):
    out = {k: res.get(k) for k in CAMPOS}
    out["identidad"] = [(h["codigo"], h["severidad"]) for h in res["revision"]["identidad"]]
    out["requiere_revision"] = res["revision"]["identidad_requiere_revision"]
    out["firma"] = res["revision"]["firma_identidad"]
    out["revision_mensajes"] = {k: sorted((h["codigo"], h["severidad"]) for h in v["hallazgos"]) for k, v in res["revision"]["mensajes"].items()}
    out["conversacion"] = res.get("conversacion")
    out["seguimiento"] = res.get("seguimiento")
    out["recursos"] = [x["id"] for x in res.get("recursos_sugeridos") or []]
    return out


def _python():
    r = R.cargar_reglas(forzar=True)
    gen = [_resumen_generacion(copilot.generate_cidiks_messages(dict(c), contexto=CONTEXTO + CASOS)) for c in CASOS]
    qa = []
    for texto, i in MENSAJES:
        res = V.revisar_mensaje(texto, CASOS[i], contexto=CONTEXTO, r=r)
        qa.append({"hallazgos": [(h["codigo"], h["severidad"]) for h in res["hallazgos"]], "metricas": res["metricas"],
                   "bloqueado": res["bloqueado"], "requiere_aprobacion": res["requiere_aprobacion"], "mensajes": [h["mensaje"] for h in res["hallazgos"]]})
    tel = [contact_identity.normalizar_telefono(t, "MX") for t in TELEFONOS]
    import conversacion
    conv = [{"clasif": conversacion.clasificar_respuesta(t), "memoria": conversacion.extraer_memoria(t),
             "analisis": conversacion.analizar_respuesta(t, CASOS[3], hoy="2026-11-25"), "redactado": conversacion.redactar(t)}
            for t in RESPUESTAS]
    sectores = [R.detectar_sector(t) for t in ("Turismo y hospedaje", "Turismo", "Hotel y Restaurante El Mirador", "Muebles Rústicos", "Clínica")]
    return {"gen": gen, "qa": qa, "tel": tel, "sectores": sectores, "conv": conv}


NODE_SCRIPT = r"""
const fs = require('fs');
const M = require(process.argv[2]);
const r = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const entrada = JSON.parse(fs.readFileSync(0, 'utf8'));
const CAMPOS = entrada.campos;
const todos = entrada.contexto.concat(entrada.casos);
const gen = entrada.casos.map((c) => {
  const res = M.generarMensajes(JSON.parse(JSON.stringify(c)), r, todos);
  const out = {}; CAMPOS.forEach((k) => out[k] = res[k] === undefined ? null : res[k]);
  out.identidad = res.revision.identidad.map((h) => [h.codigo, h.severidad]);
  out.requiere_revision = res.revision.identidad_requiere_revision;
  out.firma = res.revision.firma_identidad;
  out.revision_mensajes = {};
  for (const [k, v] of Object.entries(res.revision.mensajes)) out.revision_mensajes[k] = v.hallazgos.map((h) => [h.codigo, h.severidad]).sort();
  out.conversacion = res.conversacion === undefined ? null : res.conversacion;
  out.seguimiento = res.seguimiento === undefined ? null : res.seguimiento;
  out.recursos = (res.recursos_sugeridos || []).map((x) => x.id);
  return out;
});
const qa = entrada.mensajes.map(([texto, i]) => {
  const res = M.revisarMensaje(texto, entrada.casos[i], entrada.contexto, 'inicial', r);
  return { hallazgos: res.hallazgos.map((h) => [h.codigo, h.severidad]), metricas: res.metricas, bloqueado: res.bloqueado,
           requiere_aprobacion: res.requiere_aprobacion, mensajes: res.hallazgos.map((h) => h.mensaje) };
});
const tel = entrada.telefonos.map((t) => M.normalizarTelefono(t, 'MX'));
const sectores = ['Turismo y hospedaje', 'Turismo', 'Hotel y Restaurante El Mirador', 'Muebles Rústicos', 'Clínica'].map((t) => M.detectarSector(t, r));
const conv = entrada.respuestas.map((t) => ({ clasif: M.clasificarRespuesta(t, r), memoria: M.extraerMemoria(t, r),
  analisis: M.analizarRespuesta(t, entrada.casos[3], '2026-11-25', r), redactado: M.redactar(t) }));
process.stdout.write(JSON.stringify({ gen, qa, tel, sectores, conv }));
"""


def _node(tmp_path):
    script = tmp_path / "paridad.js"
    script.write_text(NODE_SCRIPT, encoding="utf-8")
    entrada = {"casos": CASOS, "contexto": CONTEXTO, "mensajes": MENSAJES, "telefonos": TELEFONOS, "campos": list(CAMPOS), "respuestas": RESPUESTAS}
    proc = subprocess.run([NODE, str(script), str(BASE_DIR / "docs" / "motor.js"), str(R.RUTA_REGLAS)],
                          input=json.dumps(entrada, ensure_ascii=False), capture_output=True, text=True, timeout=60, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _normalizar(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False, default=list))


def test_paridad_generacion_identidad_y_revision(tmp_path):
    py = _normalizar(_python())
    js = _node(tmp_path)
    for i, (a, b) in enumerate(zip(py["gen"], js["gen"])):
        assert a == b, f"Caso {i} ({CASOS[i].get('nombre')}) difiere:\nPython: {a}\nJS:     {b}"
    for i, (a, b) in enumerate(zip(py["qa"], js["qa"])):
        assert a == b, f"Mensaje {i} difiere:\nPython: {a}\nJS:     {b}"
    assert py["tel"] == js["tel"]
    for i, (a, b) in enumerate(zip(py["conv"], js["conv"])):
        assert a == b, f"Respuesta {i} ({RESPUESTAS[i][:40]}) difiere:\nPython: {a}\nJS:     {b}"
    assert py["sectores"] == js["sectores"]
