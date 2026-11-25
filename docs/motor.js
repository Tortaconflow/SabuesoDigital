/*
 * Sabueso — motor determinista compartido (0 tokens).
 * Traducción fiel de reglas.py + validacion.py + contact_identity.py + copilot.py (generación).
 * Funciona en el navegador (window.SabuesoMotor) y en Node (module.exports) para las pruebas
 * de paridad con Python (tests/test_paridad_motor.py). Si cambias la lógica en Python, cámbiala aquí.
 */
(function (raiz, fabrica) {
    if (typeof module === "object" && module.exports) module.exports = fabrica();
    else raiz.SabuesoMotor = fabrica();
}(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    // ------------------------------------------------------------------ texto
    const normalizar = (t) => String(t ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    const textoComparable = (t) => " " + normalizar(t).replace(/[^a-z0-9]+/g, " ").split(" ").filter(Boolean).join(" ") + " ";
    const contieneFrase = (comp, frase) => { const f = textoComparable(frase); return f.trim().length > 0 && comp.includes(f); };
    const tokens = (t) => textoComparable(t).split(" ").filter(Boolean);
    function fnv1a(texto) {
        let h = 0x811c9dc5;
        for (const ch of texto) { h ^= ch.codePointAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
        return h.toString(16).padStart(8, "0");
    }
    function rellenar(plantilla, valores) {
        let out = plantilla;
        for (const [k, v] of Object.entries(valores)) out = out.split(`{${k}}`).join(String(v));
        return out;
    }
    const s = (v) => String(v ?? "").trim();

    // ------------------------------------------------------------ teléfonos (contact_identity.py)
    function paisDelProspecto(p, r) {
        const explicito = normalizar(p.pais || p["país"] || "").trim();
        if (explicito) return ["mx", "mex", "mexico"].includes(explicito) ? "MX" : explicito.toUpperCase().slice(0, 2);
        const ubicacion = normalizar([p.municipio, p["Ubicación"], p.direccion].map((x) => String(x ?? "")).join(" "));
        if (ubicacion.includes("nuevo mexico") || ubicacion.includes("new mexico")) return "";
        return MARCAS_MEXICO_RE.test(ubicacion) ? "MX" : "";
    }
    const MARCAS_MEXICO = ["mexico", "cdmx", "aguascalientes", "baja california", "campeche", "chiapas", "chihuahua",
        "coahuila", "colima", "durango", "guanajuato", "guerrero", "hidalgo", "jalisco", "michoacan", "morelos", "nayarit",
        "nuevo leon", "oaxaca", "puebla", "queretaro", "quintana roo", "san luis potosi", "sinaloa", "sonora", "tabasco",
        "tamaulipas", "tlaxcala", "veracruz", "yucatan", "zacatecas", "puerto escondido", "zicatela", "bacocho",
        "carrizalillo", "mazunte", "zipolite", "huatulco", "chahue", "santa cruz huatulco", "puerto angel",
        "san agustinillo", "pochutla", "chacahua", "juquila", "pinotepa", "salina cruz", "juchitan", "tehuantepec", "mitla", "tlacolula"];
    const MARCAS_MEXICO_RE = new RegExp(`\\b(${MARCAS_MEXICO.join("|")})\\b`);

    function validarMx(nacional) {
        if (nacional.length !== 10 || "01".includes(nacional[0]) || new Set(nacional).size <= 2) {
            return { estado: "invalido", e164: "", motivo: "número mexicano inválido" };
        }
        return { estado: "valido", e164: `+52${nacional}`, motivo: "" };
    }
    function normalizarTelefono(raw, pais = "", esWhatsapp = false) {
        let t = String(raw ?? "").trim();
        if (!t) return { estado: "invalido", e164: "", motivo: "sin número" };
        t = t.replace(/\s*(?:ext\.?|extension|extensión|x)\s*\d+\s*$/i, "").replace(/[\s\-(). ]/g, "");
        let internacional = false;
        if (t.startsWith("+")) { internacional = true; t = t.slice(1); }
        else if (t.startsWith("00") && t.length >= 11) { internacional = true; t = t.slice(2); }
        if (!/^\d+$/.test(t)) return { estado: "invalido", e164: "", motivo: "contiene caracteres que no son dígitos" };
        if (!internacional && ((t.length === 12 && t.startsWith("52")) || (t.length === 13 && t.startsWith("521")))) internacional = true;
        else if (!internacional && esWhatsapp && t.length >= 11 && t.length <= 15) internacional = true;
        if (internacional) {
            if (t.startsWith("52")) {
                let nacional = t.slice(2);
                if (nacional.length === 11 && nacional.startsWith("1")) nacional = nacional.slice(1);
                return validarMx(nacional);
            }
            if (t.length >= 8 && t.length <= 15 && new Set(t).size > 2 && !t.startsWith("0")) return { estado: "valido", e164: `+${t}`, motivo: "" };
            return { estado: "invalido", e164: "", motivo: "número internacional con longitud inválida" };
        }
        if (t.length === 10) {
            if ((pais || "").toUpperCase() === "MX") return validarMx(t);
            return { estado: "ambiguo", e164: "", motivo: pais ? `sin código de país para ${pais}` : "sin código de país y país del prospecto desconocido" };
        }
        if (t.length >= 7 && t.length <= 9) return { estado: "ambiguo", e164: "", motivo: "número local sin lada" };
        return { estado: "invalido", e164: "", motivo: "longitud inválida" };
    }
    function clavesContacto(p) {
        const pais = paisDelProspecto(p);
        const claves = [], estados = [];
        for (const [campo, esWa] of [["whatsapp", true], ["telefono", false]]) {
            const valor = s(p[campo]);
            if (!valor) continue;
            for (const parte of valor.split(/[,;/|\n]|\s+(?:y|o|or|and)\s+/i)) {
                if (!parte || !parte.trim()) continue;
                const r = normalizarTelefono(parte, pais, esWa);
                estados.push(r.estado);
                if (r.estado === "valido" && !claves.includes(r.e164)) claves.push(r.e164);
            }
        }
        const estado = claves.length ? "valido" : estados.includes("ambiguo") ? "ambiguo" : estados.length ? "invalido" : "sin_telefono";
        return { claves, estado, pais };
    }

    // ------------------------------------------------------------ reglas.py
    const CONDICIONES_SIMPLES = new Set(["sin_web", "con_web", "con_whatsapp", "sin_whatsapp", "con_redes", "sin_redes", "con_telefono", "con_email"]);
    const sectorPorId = (sid, r) => r.sectores.find((x) => x.id === sid) || r.sector_general;

    function detectarSector(texto, r) {
        const comp = textoComparable(texto);
        if (!comp.trim()) return null;
        const puntajes = [];
        for (const sec of r.sectores) {
            const fuertes = sec.palabras_clave.fuertes.filter((p) => contieneFrase(comp, p));
            const debiles = sec.palabras_clave.debiles.filter((p) => contieneFrase(comp, p));
            const puntaje = 2 * fuertes.length + debiles.length;
            if (puntaje) puntajes.push([puntaje, sec.id, fuertes.length > 0, fuertes.concat(debiles)]);
        }
        if (!puntajes.length) return null;
        puntajes.sort((a, b) => b[0] - a[0]);
        if (puntajes.length > 1 && puntajes[0][0] === puntajes[1][0]) return null;
        const [puntaje, id, fuerte, coincidencias] = puntajes[0];
        return { id, fuerte, puntaje, coincidencias };
    }

    function sectorDeProspecto(p, r) {
        const porCampo = detectarSector(p.sector || p.Sector || "", r);
        const nombre = p.nombre || p["Nombre del negocio"] || "";
        const porNombre = detectarSector(nombre, r);
        let conflicto = null;
        const nombreComp = textoComparable(nombre);
        const respalda = !!porCampo && sectorPorId(porCampo.id, r).palabras_clave.fuertes.some((k) => contieneFrase(nombreComp, k));
        if (porCampo && porNombre && porCampo.fuerte && porNombre.fuerte && porCampo.id !== porNombre.id && !respalda) {
            conflicto = { registrado: porCampo.id, por_nombre: porNombre.id, palabras_nombre: porNombre.coincidencias };
        }
        const elegido = porCampo || porNombre;
        const sector = elegido ? sectorPorId(elegido.id, r) : r.sector_general;
        return { sector, id: sector.id, fuente: porCampo ? "campo" : (porNombre ? "nombre" : "general"), conflicto };
    }

    function senales(p) {
        const web = s(p.web || p.Web), wa = s(p.whatsapp || p.WhatsApp), waEstado = s(p.whatsapp_estado);
        return {
            web: !!web,
            wa_comprobado: !!wa && ["WHATSAPP_COMPROBADO", "confirmado"].includes(waEstado),
            wa_pendiente: ["WHATSAPP_PENDIENTE_VERIFICACION", "declarado"].includes(waEstado),
            con_whatsapp: !!wa || ["WHATSAPP_COMPROBADO", "confirmado", "WHATSAPP_PENDIENTE_VERIFICACION"].includes(waEstado),
            telefono: !!s(p.telefono || p["Teléfono"]),
            email: !!s(p.email || p.Email),
            redes: !!s(p.redes_sociales || p["Redes sociales"])
        };
    }

    function evaluarCondicion(cond, p, sn) {
        switch (cond) {
            case "sin_web": return !sn.web;
            case "con_web": return sn.web;
            case "con_whatsapp": return sn.con_whatsapp;
            case "sin_whatsapp": return !sn.con_whatsapp;
            case "con_redes": return sn.redes;
            case "sin_redes": return !sn.redes;
            case "con_telefono": return sn.telefono;
            case "con_email": return sn.email;
        }
        const i = cond.indexOf(":");
        const base = cond.slice(0, i), valor = cond.slice(i + 1);
        const campo = base === "nombre" ? normalizar(p.nombre || "") : normalizar(p.problemas_detectados || "");
        return valor.split("|").filter(Boolean).some((v) => campo.includes(normalizar(v)));
    }

    function servicioPorReglas(sector, p) {
        const sn = senales(p);
        for (const regla of sector.reglas_servicio) {
            if ((regla.si || []).every((c) => evaluarCondicion(c, p, sn))) return regla.servicio;
        }
        return sector.reglas_servicio[sector.reglas_servicio.length - 1].servicio;
    }

    function servicioPorNecesidad(texto, r) {
        const comp = textoComparable(texto);
        if (!comp.trim()) return null;
        let mejor = null, mejorPuntaje = 0;
        for (const [sid, serv] of Object.entries(r.servicios)) {
            const puntaje = serv.palabras_necesidad.filter((p) => contieneFrase(comp, p)).length;
            if (puntaje > mejorPuntaje) { mejor = sid; mejorPuntaje = puntaje; }
        }
        return mejor;
    }

    function estadoContacto(servicio, sn) {
        if (servicio === "web" && !sn.web) return "sin_web";
        if (sn.wa_comprobado) return "con_whatsapp";
        if (sn.wa_pendiente) return "whatsapp_pendiente";
        return "sin_whatsapp";
    }

    function pregunta(sector, servicio, estado, r) {
        const gen = r.sector_general.preguntas;
        if (estado === "whatsapp_pendiente") {
            const esp = (sector.preguntas[servicio] || {})[estado] || (gen[servicio] || {})[estado];
            return esp || gen.default.whatsapp_pendiente;
        }
        for (const fuente of [sector.preguntas[servicio], gen[servicio]]) {
            if (fuente) for (const clave of [estado, "default"]) if (fuente[clave]) return fuente[clave];
        }
        return gen.default.default;
    }

    function localidad(p, r) {
        const municipio = s(p.municipio || p["Ubicación"]);
        const comp = textoComparable(`${municipio} ${p.nombre || ""} ${p.web || ""}`);
        const compJunto = comp.split(" ").join("");
        for (const loc of r.localidades) {
            if (loc.patrones.some((pat) => contieneFrase(comp, pat) || compJunto.includes(textoComparable(pat).trim().split(" ").join("")))) return loc.nombre;
        }
        if (municipio && normalizar(municipio) !== "costa de oaxaca") return municipio;
        return "";
    }

    const serviciosValidos = (r) => new Set([...Object.keys(r.servicios), "investigar_mas", "no_contactar"]);

    // ------------------------------------------------------------ validacion.py
    const SUFIJOS = new Set(["com", "mx", "net", "org", "info", "biz", "example", "travel", "co", "site", "online", "store", "shop", "app", "io", "gob", "edu", "www"]);
    const hallazgo = (codigo, severidad, mensaje, detalle = {}) => ({ codigo, severidad, mensaje, detalle });

    function dominioDe(url) {
        if (!url) return "";
        let host = "";
        try { host = new URL(url.includes("://") ? url : `https://${url}`).hostname.toLowerCase(); } catch { return ""; }
        return host.startsWith("www.") ? host.slice(4) : host;
    }
    function etiquetaDominio(dominio) {
        const partes = dominio.split(".").filter((x) => x && !SUFIJOS.has(x));
        return (partes.length ? partes[partes.length - 1] : "").toLowerCase().replace(/[^a-z0-9]/g, "");
    }
    function tokensDistintivos(nombre, r) {
        const genericas = new Set(r.identidad.palabras_genericas_nombre);
        return tokens(nombre).filter((t) => t.length >= 3 && !genericas.has(t));
    }
    function compararNombreDominio(nombre, dominio, municipio, r) {
        const etiqueta = etiquetaDominio(dominio);
        const todos = tokens(nombre);
        if (!etiqueta || !todos.length) return "sin_dato";
        const distintivos = tokensDistintivos(nombre, r);
        const concatenado = todos.join("");
        if (distintivos.some((t) => etiqueta.includes(t))) return "coincide";
        if ((etiqueta.length >= 4 && concatenado.includes(etiqueta)) || etiqueta.includes(concatenado)) return "coincide";
        const acronimo = todos.map((t) => t[0]).join("");
        if (acronimo.length >= 3 && etiqueta.startsWith(acronimo)) return "coincide";
        const quitar = new Set([...r.identidad.palabras_genericas_nombre, ...tokens(municipio || "")]);
        for (const loc of r.localidades) for (const pat of loc.patrones) tokens(pat).forEach((t) => quitar.add(t));
        for (const sec of r.sectores) for (const k of sec.palabras_clave.fuertes) tokens(k).forEach((t) => quitar.add(t));
        let resto = etiqueta;
        [...quitar].filter((w) => w.length >= 2).sort((a, b) => (b.length - a.length) || (a < b ? -1 : a > b ? 1 : 0))
            .forEach((w) => { resto = resto.split(w).join(""); });
        if (resto.length <= 2) return "descriptivo";
        if (!distintivos.length) return "sin_dato";
        return "no_coincide";
    }
    function nombresCompatibles(a, b, r) {
        const ta = new Set(tokensDistintivos(a, r));
        if (tokensDistintivos(b, r).some((t) => ta.has(t))) return true;
        const ca = tokens(a).join(""), cb = tokens(b).join("");
        return !!(ca && cb && (ca.includes(cb) || cb.includes(ca)));
    }
    function firmaIdentidad(p, r) {
        const claves = [...clavesContacto(p).claves].sort();
        const sec = sectorDeProspecto(p, r);
        return fnv1a([tokens(p.nombre || "").join(" "), dominioDe(p.web || ""), claves.join(","), sec.id,
            (sec.conflicto || {}).por_nombre || ""].join("|"));
    }
    function indiceClaves(prospectos) {
        const indice = {};
        for (const o of prospectos || []) for (const k of clavesContacto(o).claves) (indice[k] = indice[k] || []).push([o.id ?? null, o.nombre || ""]);
        return indice;
    }
    function analizarIdentidad(p, contexto, r, indice) {
        const hallazgos = [];
        const nombre = p.nombre || p["Nombre del negocio"] || "";
        const dominio = dominioDe(p.web || p.Web || "");
        const sec = sectorDeProspecto(p, r);
        if (sec.conflicto) {
            const c = sec.conflicto;
            hallazgos.push(hallazgo("IDENT_SECTOR_DISCREPANCIA", "revision",
                `El giro registrado es «${sectorPorId(c.registrado, r).nombre}», pero el nombre sugiere «${sectorPorId(c.por_nombre, r).nombre}» (${c.palabras_nombre.join(", ")}). Confirma el giro antes de escribir.`,
                { registrado: c.registrado, por_nombre: c.por_nombre }));
        } else if (sec.fuente === "general") {
            hallazgos.push(hallazgo("IDENT_SECTOR_DESCONOCIDO", "info", "No se reconoció el giro; se usarán preguntas generales.", { sector: "general" }));
        }
        if (dominio) {
            if (r.identidad.dominios_redes.some((d) => dominio === d || dominio.endsWith("." + d))) {
                hallazgos.push(hallazgo("IDENT_FUENTE_RED_SOCIAL", "info", `La fuente es una red social o enlace (${dominio}); no se compara el nombre con el dominio.`, { dominio }));
            } else if (r.identidad.dominios_directorio.some((d) => dominio.includes(d))) {
                hallazgos.push(hallazgo("IDENT_SITIO_DIRECTORIO", "revision", `El sitio (${dominio}) es un directorio: el nombre o el contacto pueden ser de otro negocio.`, { dominio }));
            } else {
                const comp = compararNombreDominio(nombre, dominio, p.municipio || "", r);
                if (comp === "no_coincide") {
                    hallazgos.push(hallazgo("IDENT_NOMBRE_DOMINIO", "revision", `El nombre «${nombre}» no coincide con el sitio ${dominio}. ¿Es el mismo negocio?`, { nombre, dominio }));
                } else if (comp === "descriptivo") {
                    hallazgos.push(hallazgo("IDENT_DOMINIO_DESCRIPTIVO", "info", `El dominio ${dominio} es descriptivo; no permite confirmar el nombre.`, { dominio }));
                }
            }
        }
        if (contexto || indice) {
            const idx = indice || indiceClaves(contexto);
            let encontrado = null;
            const pid = p.id ?? null;
            for (const k of clavesContacto(p).claves) {
                for (const [otroId, otroNombre] of idx[k] || []) {
                    if (pid !== null && otroId === pid) continue;
                    if (otroId === null && otroNombre === nombre) continue;
                    if (!nombresCompatibles(nombre, otroNombre, r)) { encontrado = [otroId, otroNombre]; break; }
                }
                if (encontrado) break;
            }
            if (encontrado) {
                hallazgos.push(hallazgo("IDENT_CONTACTO_COMPARTIDO", "revision",
                    `El mismo número aparece en «${encontrado[1]}». Puede ser de una agencia o directorio, no de este negocio.`,
                    { otro_id: encontrado[0], otro_nombre: encontrado[1] }));
            }
        }
        const firma = firmaIdentidad(p, r);
        const pide = hallazgos.some((h) => h.severidad === "revision");
        const confirmada = pide && (p.identidad_revisada_firma || "") === firma;
        return { hallazgos, firma, requiere_revision: pide && !confirmada, confirmada_por_humano: confirmada, sector_id: sec.id, sector_fuente: sec.fuente };
    }

    // Destinatarios explícitos del saludo: solo nombres propios (con mayúscula) tras «Hola», «Buen día» o «equipo de».
    const RE_SALUDO = /(?:\b[Ee]quipo del?|\b[Hh]ola,?|\b[Bb]uen dia,?|\b[Bb]uenos dias,?|\b[Bb]uenas tardes,?)\s+((?:[A-Z0-9][A-Za-z0-9'&]*)(?:\s+(?:de|del|la|el|los|las|y|&|[A-Z0-9][A-Za-z0-9'&]*))*)/g;
    const CONECTORES = new Set(["de", "del", "la", "el", "los", "las", "y", "&"]);
    function candidatosSaludo(texto) {
        const fuente = String(texto ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        const out = [];
        RE_SALUDO.lastIndex = 0;
        let m;
        while ((m = RE_SALUDO.exec(fuente)) !== null) {
            const palabras = m[1].split(/\s+/).filter(Boolean);
            while (palabras.length && CONECTORES.has(palabras[palabras.length - 1].toLowerCase())) palabras.pop();
            if (palabras.length) out.push(palabras.join(" "));
        }
        return out;
    }
    const textoEvidencia = (p) => textoComparable(["nombre", "sector", "observacion_verificada", "problemas_detectados",
        "necesidad_expresada", "respuesta", "notas", "redes_sociales"].map((c) => String(p[c] ?? "")).join(" "));
    function metricas(texto) {
        const t = String(texto || "").trim();
        return { caracteres: [...t].length, palabras: t.split(/\s+/).filter(Boolean).length, preguntas: (t.match(/\?/g) || []).length };
    }

    function revisarMensaje(texto, p, contexto, tipo, r) {
        tipo = tipo || "inicial";
        const cfg = r.mensajes;
        const hallazgos = [];
        const t = String(texto || "").trim();
        const met = metricas(t);
        if (t.startsWith("[BLOQUEADO") || t.startsWith("[RECOMENDACIÓN") || t.startsWith("[REVISIÓN")) {
            return { hallazgos: [hallazgo("MSG_NO_ENVIABLE", "bloqueo", "Este texto es un aviso interno, no un mensaje para enviar.")],
                bloqueado: true, requiere_aprobacion: false, metricas: met, en_objetivo: false };
        }
        const comp = textoComparable(t);
        const nombre = p.nombre || p["Nombre del negocio"] || "";
        const propios = new Set([...tokensDistintivos(nombre, r), ...tokens(nombre)]);

        const saludoPalabras = new Set([...r.identidad.palabras_saludo, ...r.identidad.palabras_genericas_nombre]);
        for (const cand of candidatosSaludo(t)) {
            const dist = tokens(cand).filter((w) => !saludoPalabras.has(w) && w.length >= 3);
            if (dist.length && !dist.some((w) => propios.has(w))) {
                hallazgos.push(hallazgo("MSG_SALUDO_OTRO_NOMBRE", "bloqueo", `El saludo va dirigido a «${cand.trim()}», que no es «${nombre}».`, { saludo: cand.trim() }));
                break;
            }
        }

        const nombreComp = textoComparable(nombre);
        const pid = p.id ?? null;
        for (const otro of contexto || []) {
            if (pid !== null && (otro.id ?? null) === pid) continue;
            const dist = tokensDistintivos(otro.nombre || "", r);
            const frase = dist.join(" ");
            if (frase && (dist.length >= 2 || frase.length >= 6) && contieneFrase(comp, frase) && !contieneFrase(nombreComp, frase)) {
                hallazgos.push(hallazgo("MSG_OTRO_NEGOCIO", "bloqueo", `El mensaje menciona a otro prospecto: «${otro.nombre}».`, { otro_id: otro.id ?? null }));
                break;
            }
            const etiqueta = etiquetaDominio(dominioDe(otro.web || ""));
            if (etiqueta.length >= 6 && comp.includes(` ${etiqueta} `) && !tokens(nombre).join("").includes(etiqueta)) {
                hallazgos.push(hallazgo("MSG_OTRO_NEGOCIO", "bloqueo", `El mensaje menciona el sitio de otro prospecto: «${otro.nombre}».`, { otro_id: otro.id ?? null }));
                break;
            }
        }

        const sector = sectorDeProspecto(p, r).sector;
        if (sector.id !== "general") {
            const evidencia = textoEvidencia(p);
            const propio = new Set(sector.vocabulario.map((v) => textoComparable(v).trim()));
            const frasesEnMsg = sector.frases_propias.map((f) => textoComparable(f).trim()).filter((f) => f && comp.includes(` ${f} `));
            let listo = false;
            for (const otroSector of r.sectores) {
                if (otroSector.id === sector.id) continue;
                for (const termino of otroSector.vocabulario) {
                    const tc = textoComparable(termino).trim();
                    if (!tc || propio.has(tc) || !comp.includes(` ${tc} `)) continue;
                    if (evidencia.includes(` ${tc} `) || frasesEnMsg.some((f) => f.includes(tc))) continue;
                    hallazgos.push(hallazgo("MSG_VOCABULARIO_OTRO_GIRO", "revision",
                        `«${termino}» es propio de «${otroSector.nombre}» y este negocio es de «${sector.nombre}». Revisa que la propuesta corresponda a su giro.`,
                        { termino, giro_termino: otroSector.id, giro_negocio: sector.id }));
                    listo = true;
                    break;
                }
                if (listo) break;
            }
        }

        if (met.caracteres >= cfg.advertencia_desde) {
            hallazgos.push(hallazgo("MSG_LARGO", "advertencia", `Mensaje largo: ${met.caracteres} caracteres (objetivo ${cfg.objetivo_min}–${cfg.objetivo_max}).`, { caracteres: met.caracteres }));
        } else if (met.caracteres > cfg.objetivo_max || met.caracteres < cfg.objetivo_min) {
            hallazgos.push(hallazgo("MSG_FUERA_OBJETIVO", "info", `${met.caracteres} caracteres; el objetivo experimental es ${cfg.objetivo_min}–${cfg.objetivo_max}.`, { caracteres: met.caracteres }));
        }
        if (tipo !== "seguimiento" && met.preguntas > cfg.max_preguntas) {
            hallazgos.push(hallazgo("MSG_PREGUNTAS", "advertencia", `Tiene ${met.preguntas} preguntas; conviene una sola.`, { preguntas: met.preguntas }));
        }
        const genericas = cfg.frases_genericas.filter((f) => contieneFrase(comp, f));
        if (genericas.length) hallazgos.push(hallazgo("MSG_GENERICO", "advertencia", "Frases genéricas: " + genericas.map((g) => `«${g}»`).join(", ") + ".", { frases: genericas }));
        const distPropios = tokensDistintivos(nombre, r);
        if (nombre && !(contieneFrase(comp, nombre) || distPropios.some((d) => contieneFrase(comp, d)))) {
            hallazgos.push(hallazgo("MSG_SIN_NOMBRE", "advertencia", "El mensaje no menciona al negocio por su nombre."));
        }
        const jerga = cfg.jerga_tecnica.filter((j) => contieneFrase(comp, j));
        if (jerga.length) hallazgos.push(hallazgo("MSG_JERGA", "advertencia", "Jerga técnica: " + jerga.join(", ") + ".", { terminos: jerga }));

        return {
            hallazgos,
            bloqueado: hallazgos.some((h) => h.severidad === "bloqueo"),
            requiere_aprobacion: hallazgos.some((h) => h.severidad === "revision"),
            metricas: met,
            en_objetivo: cfg.objetivo_min <= met.caracteres && met.caracteres <= cfg.objetivo_max
        };
    }

    // ------------------------------------------------------------ copilot.py (generación)
    const ESPECIALES = {
        investigar_mas: { nombre: "Investigar más antes de contactar" },
        no_contactar: { nombre: "No contactar todavía" }
    };
    function cleanBusinessName(raw) {
        if (!raw) return "Equipo";
        let nombre = String(raw).split(/[\-|•–|:]/)[0].trim();
        if (nombre.length < 3) nombre = String(raw).trim();
        return nombre;
    }
    function verificarIdentidad(p, r) {
        if (p.identidad_verificada === false || p.identidad_verificada === 0) return [false, "Marcado manualmente como identidad no verificada."];
        const web = s(p.web || p.Web), webLower = web.toLowerCase();
        const wa = s(p.whatsapp || p.WhatsApp), tel = s(p.telefono || p["Teléfono"]), email = s(p.email || p.Email);
        const redes = s(p.redes_sociales || p["Redes sociales"]), nombre = s(p.nombre || p["Nombre del negocio"]);
        if (web && r.identidad.marcadores_url_invalida.some((m) => webLower.includes(m))) {
            return [false, `El enlace registrado (${dominioDe(web) || web.slice(0, 40)}) corresponde a un visor de documentos o sitio ajeno al negocio, y no cuenta con canales verificados.`];
        }
        if (!nombre || ["sin nombre", "desconocido", "test"].includes(nombre.toLowerCase())) return [false, "Nombre comercial ausente o inválido."];
        if (!web && !wa && !tel && !email && !redes) return [false, "No cuenta con sitio web oficial ni ningún canal público verificable (WhatsApp, teléfono, correo o redes)."];
        return [true, "Identidad respaldada por fuente pública."];
    }
    function necesitaInvestigar(p, r) {
        const web = s(p.web || p.Web).toLowerCase(), nombre = s(p.nombre || p["Nombre del negocio"]).toLowerCase();
        const wa = s(p.whatsapp || p.WhatsApp), tel = s(p.telefono || p["Teléfono"]), email = s(p.email || p.Email), redes = s(p.redes_sociales || p["Redes sociales"]);
        if (r.identidad.marcadores_corporativos.some((m) => web.includes(m) || nombre.includes(m)) && !wa) {
            return [true, "Propiedad perteneciente a grupo corporativo o segmento de lujo con atención centralizada y sin WhatsApp público."];
        }
        if (web && !wa && !tel && !email && !redes) return [true, "Sitio web activo, pero sin WhatsApp, teléfono directo ni correo publicados (solo formulario cerrado o sin datos visibles)."];
        return [false, ""];
    }
    function seleccionarServicio(p, r, honorExplicit = true) {
        if (!verificarIdentidad(p, r)[0]) return ["no_contactar", "identidad_no_verificada"];
        const explicit = p.servicio_sugerido;
        if (honorExplicit && ["no_contactar", "investigar_mas"].includes(explicit)) return [explicit, "eleccion_humana"];
        const necesidad = s(p.necesidad_expresada);
        if (necesidad) {
            const porNecesidad = servicioPorNecesidad(necesidad, r);
            if (porNecesidad) return [porNecesidad, "necesidad_confirmada"];
        }
        const forzado = !!(honorExplicit && p._force_explicit && serviciosValidos(r).has(explicit) && !(explicit in ESPECIALES));
        if (necesitaInvestigar(p, r)[0] && !forzado) return ["investigar_mas", "reglas"];
        if (forzado) return [explicit, "eleccion_humana"];
        return [servicioPorReglas(sectorDeProspecto(p, r).sector, p), "reglas_sector"];
    }
    function observacionVerificada(p, r, evidencias) {
        const [ok, motivo] = verificarIdentidad(p, r);
        if (!ok) return `Identidad no verificada: ${motivo}`;
        const domain = dominioDe(s(p.web || p.Web));
        const wa = s(p.whatsapp || p.WhatsApp), waEstado = s(p.whatsapp_estado), fuenteWa = s(p.fuente_whatsapp);
        const tel = s(p.telefono || p["Teléfono"]), email = s(p.email || p.Email), redes = s(p.redes_sociales || p["Redes sociales"]);
        const parts = [domain ? `Sitio web oficial activo (${domain})` : "Sin sitio web propio registrado"];
        if (wa && ["WHATSAPP_COMPROBADO", "confirmado"].includes(waEstado)) parts.push(`WhatsApp público comprobado (+${wa})${fuenteWa ? ` vía ${fuenteWa}` : " en su sitio oficial"}`);
        else if (["WHATSAPP_PENDIENTE_VERIFICACION", "declarado"].includes(waEstado)) parts.push(`mención de WhatsApp pendiente de verificar (${wa || "sin enlace wa.me directo"})`);
        else parts.push("sin enlace directo de WhatsApp en su web");
        const otros = [];
        if (tel) otros.push(`teléfono (${tel.split(",")[0].trim()})`);
        if (email) otros.push(`correo (${email.split(",")[0].trim()})`);
        if (redes) otros.push("perfiles en redes sociales");
        if (otros.length) parts.push("publica " + otros.join(", "));
        else if (!wa) parts.push("únicamente dispone de formulario web general");
        const verificadas = (evidencias || []).filter((ev) => ev.estado_comprobacion === "VERIFICADA_VISIBLE");
        if (verificadas.length && verificadas[0].elemento_observado) parts.push(`evidencia visual comprobada: ${verificadas[0].elemento_observado}`);
        const obs = parts.join("; ");
        return obs[0].toUpperCase() + obs.slice(1) + ".";
    }
    function hipotesis(p, servicio, sector, fuente, r) {
        if (servicio === "no_contactar") return "Sin fuente pública legítima confirmada; no debe iniciarse contacto comercial.";
        if (servicio === "investigar_mas") return necesitaInvestigar(p, r)[1] || "Estructura operativa sin contacto directo; conviene identificar primero al encargado.";
        const serv = r.servicios[servicio];
        const necesidad = s(p.necesidad_expresada);
        if (fuente === "necesidad_confirmada" && serv) return `Necesidad confirmada por el negocio: «${necesidad}». Solución a conversar: ${serv.nombre}.`;
        if (necesidad) return `Necesidad confirmada por el negocio: «${necesidad}». No se reconoció automáticamente la solución; revísala antes de proponer.`;
        const textoH = (sector.hipotesis || {})[servicio] || (serv || {}).hipotesis;
        return textoH ? `Hipótesis: ${textoH}` : "Hipótesis exploratoria sujeta a validación con el negocio.";
    }
    function claveHecho(sn) {
        if (sn.web && sn.wa_comprobado) return "web_whatsapp";
        if (sn.web && sn.wa_pendiente) return "whatsapp_pendiente";
        if (sn.web && sn.telefono) return "web_telefono";
        if (sn.web) return "web";
        if (sn.wa_comprobado) return "solo_whatsapp";
        return "sin_web";
    }
    function fuenteAlta(p) {
        let f = s(p.fuente);
        if (!f) { const d = s(p.fuente_descubrimiento); f = d.startsWith("movil_") ? d.slice(6) : ""; }
        return f;
    }
    function indiceEstilo(p, total) {
        const raw = p.id ?? p.pc_id;
        let base;
        if (typeof raw === "number" && isFinite(raw)) base = Math.trunc(raw);
        else if (typeof raw === "string" && /^\s*-?\d+\s*$/.test(raw)) base = parseInt(raw, 10);
        else { base = 0; for (const ch of String(p.nombre || "")) base += ch.codePointAt(0); }
        const m = Math.max(total, 1);
        return ((base % m) + m) % m;
    }
    function componerMensajes(p, sector, servicioKey, fuente, r) {
        const mod = r.modalidades[r.modalidad_predeterminada];
        const objMax = r.mensajes.objetivo_max;
        const serv = r.servicios[servicioKey];
        const nombre = cleanBusinessName(p.nombre || p["Nombre del negocio"] || "Equipo");
        const loc = localidad(p, r);
        const plantillaSaludo = mod.saludos[indiceEstilo(p, mod.saludos.length)];
        const saludo = rellenar(plantillaSaludo, { nombre, en_localidad: loc ? ` en ${loc}` : "" });
        const saludoCorto = rellenar(plantillaSaludo, { nombre, en_localidad: "" });
        const unir = (partes) => partes.filter(Boolean).join(" ").trim();
        let preg, frio;
        if (fuente === "necesidad_confirmada") {
            preg = mod.pregunta_con_necesidad;
            const cuerpo = rellenar(mod.con_necesidad, { servicio: serv.nombre });
            const cands = [unir([saludo, cuerpo, preg]), unir([saludoCorto, cuerpo, preg])];
            frio = cands.find((c) => [...c].length <= objMax) || cands[cands.length - 1];
        } else {
            const sn = senales(p);
            preg = pregunta(sector, servicioKey, estadoContacto(servicioKey, sn), r);
            const fa = fuenteAlta(p);
            const hecho = ((mod.hechos_fuente || {})[fa] && fa ? mod.hechos_fuente[fa] : "") || mod.hechos[claveHecho(sn)] || "";
            const cands = [unir([saludo, mod.presentacion, hecho, preg]), unir([saludoCorto, mod.presentacion, hecho, preg]),
                unir([saludo, mod.presentacion, preg]), unir([saludoCorto, mod.presentacion, preg])];
            frio = cands.find((c) => [...c].length <= objMax) || cands[cands.length - 1];
        }
        return {
            pregunta: preg,
            mensaje_personalizado: frio,
            mensaje_calido: rellenar(mod.calido, { nombre, pregunta: preg }).trim(),
            mensaje_seguimiento: rellenar(mod.seguimiento, { nombre, tema: serv.tema_seguimiento }).trim()
        };
    }

    function generarMensajes(p, r, contexto, indice, evidencias) {
        const nombre = cleanBusinessName(p.nombre || p["Nombre del negocio"] || "Equipo");
        const [ok, motivo] = verificarIdentidad(p, r);
        const identidad = analizarIdentidad(p, contexto, r, indice);
        const info = sectorDeProspecto(p, r);
        const sector = info.conflicto && !identidad.confirmada_por_humano ? r.sector_general : info.sector;
        const [servicioKey, fuente] = seleccionarServicio(p, r, true);
        const servicioNombre = ((r.servicios[servicioKey] || ESPECIALES[servicioKey]) || {}).nombre || "";
        const observacion = observacionVerificada(p, r, evidencias);
        const hip = hipotesis(p, servicioKey, sector, fuente, r);
        let checks = p.checks || {};
        if (typeof checks === "string") { try { checks = JSON.parse(checks); } catch { checks = {}; } }
        const verificadas = (evidencias || []).filter((ev) => ev.estado_comprobacion === "VERIFICADA_VISIBLE");
        const conProblema = verificadas.length > 0 || (checks && (checks.responsive === false || checks.whatsapp === false));
        const base = {
            identidad_verificada: true,
            modalidad: conProblema ? "A_PROBLEMA_VERIFICADO" : "B_OPORTUNIDAD_EXPLORATORIA",
            modalidad_comunicacion: r.modalidad_predeterminada,
            servicio_sugerido: servicioKey, servicio_nombre: servicioNombre, fuente_servicio: fuente,
            sector_id: sector.id, sector_nombre: sector.nombre,
            observacion_verificada: observacion, hipotesis_comercial: hip, evidencia_origen: observacion,
            consumo_tokens: 0, motor: "reglas_deterministas",
            revision: {
                identidad: identidad.hallazgos, identidad_requiere_revision: identidad.requiere_revision,
                identidad_confirmada: identidad.confirmada_por_humano, firma_identidad: identidad.firma, mensajes: {}
            }
        };
        const bloquear = (msg, tipoObs, identOk = true, preg = "") => Object.assign(base, {
            identidad_verificada: identOk, bloqueado_envio: true, tipo_observacion: tipoObs, pregunta_comercial: preg,
            mensaje_personalizado: msg, mensaje_calido: msg, mensaje_seguimiento: msg
        });
        if (!ok || servicioKey === "no_contactar") {
            base.servicio_sugerido = "no_contactar";
            base.servicio_nombre = ESPECIALES.no_contactar.nombre;
            return bloquear(`[BLOQUEADO — NO CONTACTAR TODAVÍA]\nMotivo: ${motivo}\nAcción recomendada: Verificar primero que ${nombre} opere activamente y confirmar un canal oficial antes de redactar un mensaje.`,
                "IDENTIDAD_NO_VERIFICADA", ok);
        }
        if (servicioKey === "investigar_mas") {
            return bloquear(`[RECOMENDACIÓN: INVESTIGAR MÁS ANTES DE CONTACTAR]\nObservación: ${observacion}\nNota comercial: ${hip}\nSi decides contactar a ${nombre}, selecciona manualmente una capacidad específica de CÍDIKS en el selector superior.`,
                "REQUIERE_INVESTIGACION");
        }
        if (identidad.requiere_revision) {
            const motivos = identidad.hallazgos.filter((h) => h.severidad === "revision").map((h) => h.mensaje).join("; ");
            const preg = pregunta(sector, servicioKey, estadoContacto(servicioKey, senales(p)), r);
            return bloquear(`[REVISIÓN HUMANA REQUERIDA]\nAntes de escribir a ${nombre}, confirma: ${motivos}\nEn la ficha: «Confirmar identidad» o corrige el nombre o el giro.`,
                "REQUIERE_REVISION_HUMANA", true, preg);
        }
        const mensajes = componerMensajes(p, sector, servicioKey, fuente, r);
        const revisiones = {};
        for (const [campo, tipo] of [["mensaje_personalizado", "inicial"], ["mensaje_calido", "inicial"], ["mensaje_seguimiento", "seguimiento"]]) {
            revisiones[campo] = revisarMensaje(mensajes[campo], p, contexto, tipo, r);
        }
        base.revision.mensajes = revisiones;
        return Object.assign(base, {
            bloqueado_envio: Object.values(revisiones).some((v) => v.bloqueado),
            tipo_observacion: verificadas.length ? "OBSERVACION_COMPROBADA" : "HIPOTESIS_COMERCIAL",
            pregunta_comercial: mensajes.pregunta,
            mensaje_personalizado: mensajes.mensaje_personalizado,
            mensaje_calido: mensajes.mensaje_calido,
            mensaje_seguimiento: mensajes.mensaje_seguimiento
        });
    }

    return {
        normalizar, textoComparable, contieneFrase, tokens, fnv1a,
        normalizarTelefono, clavesContacto, paisDelProspecto,
        detectarSector, sectorDeProspecto, sectorPorId, servicioPorNecesidad, localidad,
        dominioDe, compararNombreDominio, firmaIdentidad, indiceClaves, analizarIdentidad, revisarMensaje,
        generarMensajes
    };
}));
