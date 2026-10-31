import re
import json
from config import GEMINI_API_KEY

def generate_cidiks_messages(prospect: dict, evidencias: list = None, use_ai: bool = True, api_key: str = None) -> dict:
    """
    Genera mensajes de prospección ética con el estilo CÍDIKS.
    Distingue:
    - Modalidad A: Problema verificado (basado en evidencia comprobada)
    - Modalidad B: Oportunidad exploratoria (pregunta respetuosa sin afirmar fallas)
    """
    nombre = prospect.get("nombre") or prospect.get("Nombre del negocio") or "Estimado equipo"
    web = prospect.get("web") or prospect.get("Web") or ""
    sector = prospect.get("sector") or "su sector"
    municipio = prospect.get("municipio") or prospect.get("Ubicación") or "Oaxaca"

    # Revisar evidencias verificadas
    verificadas = []
    if evidencias:
        for ev in evidencias:
            if ev.get("estado_comprobacion") == "VERIFICADA_VISIBLE":
                verificadas.append(ev)

    checks = prospect.get("checks") or {}
    if isinstance(checks, str):
        try:
            checks = json.loads(checks)
        except Exception:
            checks = {}

    # Determinar modalidad
    has_verified_issue = False
    issue_desc = ""

    if not web:
        has_verified_issue = True
        modalidad = "A_PROBLEMA_VERIFICADO"
        issue_desc = "notamos que actualmente atienden clientes principalmente por redes sociales y no cuentan con un sitio web oficial propio"
    elif verificadas:
        for ev in verificadas:
            if ev.get("elemento_observado") and ev.get("estado_comprobacion") == "VERIFICADA_VISIBLE":
                has_verified_issue = True
                modalidad = "A_PROBLEMA_VERIFICADO"
                issue_desc = f"al revisar su página desde celular, observamos que {ev.get('elemento_observado')}"
                break
        if not has_verified_issue:
            modalidad = "B_OPORTUNIDAD_EXPLORATORIA"
    elif not checks.get("responsive", True):
        has_verified_issue = True
        modalidad = "A_PROBLEMA_VERIFICADO"
        issue_desc = "al abrir su sitio desde un teléfono móvil, el menú y los textos quedan difíciles de leer sin hacer zoom"
    elif not checks.get("whatsapp", True):
        has_verified_issue = True
        modalidad = "A_PROBLEMA_VERIFICADO"
        issue_desc = "su página no tiene un botón directo para que los visitantes les escriban a WhatsApp con un solo clic"
    elif checks.get("load_time_seconds", 0) > 4.0:
        has_verified_issue = True
        modalidad = "A_PROBLEMA_VERIFICADO"
        issue_desc = "la página tarda varios segundos en terminar de cargar, lo que a veces hace que los visitantes salgan antes de ver sus servicios"
    else:
        modalidad = "B_OPORTUNIDAD_EXPLORATORIA"

    # 1. Mensajes determinísticos con estilo CÍDIKS (Offline / Local-first)
    if modalidad == "A_PROBLEMA_VERIFICADO":
        msg_frio = (
            f"Hola, buen día al equipo de {nombre}.\n\n"
            f"Les escribo desde CÍDIKS en {municipio}. Estuve revisando opciones de {sector} y visité su presencia digital.\n\n"
            f"Noté un detalle puntual: {issue_desc}. "
            f"Hoy muchos clientes buscan y reservan directo desde el celular, por lo que ajustar esto les facilitaría recibir más consultas.\n\n"
            f"¿Tendrían 5 minutos esta semana para compartirles una recomendación sencilla sobre cómo resolverlo?"
        )
        msg_calido = (
            f"Hola, equipo de {nombre}, un gusto saludarlos. "
            f"Estuve viendo su trabajo en {municipio} y me parece una propuesta excelente. "
            f"Al revisar su enlace web noté que {issue_desc}. "
            f"En CÍDIKS ayudamos a negocios locales a dejar su canal directo impecable. ¿Les gustaría que les comparta un breve ejemplo de cómo optimizarlo?"
        )
        msg_seg = (
            f"Hola, equipo de {nombre}. Espero que estén teniendo una buena semana. "
            f"Solo quería dar seguimiento a mi mensaje anterior respecto a la mejora en su canal de atención en línea. "
            f"Si están ocupados lo entiendo perfectamente; si les interesa comentarlo con calma, quedo a su disposición. Saludos."
        )
    else:
        # Modalidad B: Oportunidad exploratoria (pregunta sin afirmar fallas)
        msg_frio = (
            f"Hola, buen día al equipo de {nombre}.\n\n"
            f"Les escribo desde CÍDIKS en {municipio}. Estuvimos conociendo negocios del área de {sector} y nos llamó la atención su servicio.\n\n"
            f"Queríamos consultarles: ¿cómo sienten que les está funcionando su canal digital para captar clientes en {municipio}? "
            f"Nos dedicamos a crear soluciones digitales a la medida para negocios locales.\n\n"
            f"Si les parece bien, ¿podríamos conversar brevemente sobre qué herramientas les vendrían mejor para agilizar sus contactos este año?"
        )
        msg_calido = (
            f"Hola, un saludo al equipo de {nombre}. Me gusta mucho lo que ofrecen en {municipio}. "
            f"En CÍDIKS apoyamos a negocios locales a facilitar que nuevos clientes los contacten y conozcan sus servicios. "
            f"¿Tienen previsto renovar o fortalecer sus herramientas digitales en estos meses? Con gusto podemos platicar 5 minutos sin compromiso."
        )
        msg_seg = (
            f"Hola de nuevo, equipo de {nombre}. Espero que todo vaya excelente con sus actividades. "
            f"Paso a dejar un saludo rápido por si en algún momento desean revisar opciones para facilitar el contacto directo con sus clientes en {municipio}. ¡Mucho éxito en la semana!"
        )

    result = {
        "modalidad": modalidad,
        "mensaje_personalizado": msg_frio,
        "mensaje_calido": msg_calido,
        "mensaje_seguimiento": msg_seg,
        "evidencia_origen": issue_desc if has_verified_issue else "Exploratorio sin falla afirmada"
    }

    # 2. Refinamiento con IA si hay API key y se solicita
    effective_key = api_key or GEMINI_API_KEY
    if use_ai and effective_key and effective_key not in ["", "placeholder", "None"]:
        try:
            import google.generativeai as genai
            genai.configure(api_key=effective_key)
            model = genai.GenerativeModel('gemini-2.5-flash')

            prompt = f"""
            Actúa como un asesor comercial de CÍDIKS en Oaxaca, México.
            Escribe 3 borradores de mensajes de prospección comercial para un negocio local:
            
            Negocio: {nombre}
            Sector: {sector}
            Ubicación: {municipio}
            Modalidad: {modalidad}
            Evidencia observada: {issue_desc if has_verified_issue else 'Ninguna falla confirmada (Modalidad B exploratoria)'}

            REGLAS ESTRICTAS DE COMUNICACIÓN CÍDIKS:
            1. Tono respetuoso, cálido, profesional y humano. Cero arrogancia ni tono de 'auditor regañón'.
            2. Prohibido usar jerga técnica (nada de SSL, DOM, CSS, SSRF, meta-tags).
            3. Prohibido hacer promesas exageradas o falsas ('duplicará sus ventas', 'garantizado').
            4. Si la modalidad es B, NO afirmes ningún error; haz una pregunta respetuosa para entender cómo les va con sus clientes.
            5. Si la modalidad es A, menciona la observación con prudencia ('notamos que...', 'al revisar desde el celular...').
            6. Brevedad: cada mensaje debe poder leerse en menos de 30 segundos.

            Devuelve estrictamente un JSON con esta estructura exacta:
            {{
              "mensaje_personalizado": "Texto del mensaje frío formal",
              "mensaje_calido": "Texto para redes sociales o WhatsApp informal",
              "mensaje_seguimiento": "Texto de seguimiento prudente sin presionar"
            }}
            """
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\n|```$", "", raw_text, flags=re.MULTILINE).strip()
            ai_data = json.loads(raw_text)

            if "mensaje_personalizado" in ai_data:
                result["mensaje_personalizado"] = ai_data["mensaje_personalizado"]
            if "mensaje_calido" in ai_data:
                result["mensaje_calido"] = ai_data["mensaje_calido"]
            if "mensaje_seguimiento" in ai_data:
                result["mensaje_seguimiento"] = ai_data["mensaje_seguimiento"]
        except Exception as e:
            print(f"[COPILOT] IA no disponible, usando plantilla CÍDIKS determinística: {e}")

    return result
