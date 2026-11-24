/*
 * Sabueso Móvil — CÍDIKS Sales Engine para iPhone (funciona sin internet)
 *
 * - Los datos viven SOLO en el celular (IndexedDB). Este sitio solo entrega el código.
 * - Cada acción (confirmar contacto, respuesta, propuesta, venta, cobro, nota, prospecto nuevo)
 *   se guarda como un "evento". La PC los importa de forma idempotente (movil_sync.py).
 * - Abrir WhatsApp o copiar un mensaje NUNCA marca a nadie como contactado:
 *   la confirmación siempre es humana y explícita, igual que en Sabueso PC.
 */
(function () {
    "use strict";

    const APP_VERSION = "1.0.0";
    const FORMATO_PC = "sabueso-movil";
    const FORMATO_AVANCES = "sabueso-movil-avances";
    const FORMATO_RESPALDO = "sabueso-movil-respaldo";
    const MAX_ARCHIVO = 15 * 1024 * 1024;

    const ESTADOS = {
        investigado: "Investigado",
        auditado: "Auditado",
        contactado: "Contactado",
        interesado: "Interesado",
        no_interesa: "No le interesa",
        propuesta: "Propuesta",
        ganado: "Ganado",
        descartado: "Descartado"
    };
    const CERRADOS = new Set(["ganado", "descartado", "no_interesa"]);
    const PRIORIDADES = { critical: "Crítica", high: "Alta", medium: "Media", low: "Baja" };
    const RANGO_PRIORIDAD = { critical: 0, high: 1, medium: 2, low: 3 };
    const CANALES = { whatsapp: "WhatsApp", llamada: "Llamada", email: "Correo", redes: "Redes sociales", persona: "En persona" };
    const FUENTES = {
        maps: "Google Maps", facebook: "Facebook", instagram: "Instagram", persona: "Lo vi en persona",
        recomendacion: "Me lo recomendaron", web: "Su página web", otro: "Otro"
    };
    const CAMPOS_TEXTO = [
        "nombre", "sector", "municipio", "web", "redes_sociales", "telefono", "whatsapp", "whatsapp_estado", "email",
        "prioridad", "estado_comercial", "problemas_detectados", "observacion_verificada", "hipotesis_comercial",
        "pregunta_comercial", "servicio_sugerido", "mensaje_personalizado", "mensaje_calido", "mensaje_seguimiento",
        "notas", "fecha_contacto_confirmada", "canal", "respuesta", "necesidad_expresada", "siguiente_accion",
        "fecha_seguimiento", "movil_uid"
    ];
    const CAMPOS_NUM = ["puntuacion", "propuesta_monto", "venta_monto", "ingreso_cobrado"];
    const CAMPOS_FLAG = ["propuesta_enviada", "venta_acordada", "mensaje_aprobado", "identidad_verificada"];
    const CAMPOS_CRM = [
        "estado_comercial", "respuesta", "necesidad_expresada", "siguiente_accion", "fecha_seguimiento",
        "propuesta_enviada", "propuesta_monto", "venta_acordada", "venta_monto", "ingreso_cobrado"
    ];

    // ======================================================================
    // Utilidades
    // ======================================================================
    const $ = (sel) => document.querySelector(sel);

    function h(tag, props, ...children) {
        const el = document.createElement(tag);
        if (props) {
            for (const [k, v] of Object.entries(props)) {
                if (v === null || v === undefined || v === false) continue;
                if (k === "class") el.className = v;
                else if (k === "value") el.value = v;
                else if (k === "checked" || k === "disabled" || k === "selected" || k === "required") el[k] = !!v;
                else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
                else el.setAttribute(k, v === true ? "" : String(v));
            }
        }
        for (const c of children.flat(Infinity)) {
            if (c === null || c === undefined || c === false || c === "") continue;
            el.append(c instanceof Node ? c : document.createTextNode(String(c)));
        }
        return el;
    }

    function uuid() {
        if (crypto.randomUUID) return crypto.randomUUID();
        const b = crypto.getRandomValues(new Uint8Array(16));
        b[6] = (b[6] & 0x0f) | 0x40;
        b[8] = (b[8] & 0x3f) | 0x80;
        const x = [...b].map((n) => n.toString(16).padStart(2, "0")).join("");
        return `${x.slice(0, 8)}-${x.slice(8, 12)}-${x.slice(12, 16)}-${x.slice(16, 20)}-${x.slice(20)}`;
    }

    function ahoraISO() {
        const d = new Date();
        const p = (n) => String(n).padStart(2, "0");
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
    }
    const hoyISO = () => ahoraISO().slice(0, 10);

    function fechaBonita(iso, conHora = true) {
        if (!iso) return "";
        const d = new Date(String(iso).length === 10 ? `${iso}T12:00:00` : iso);
        if (isNaN(d)) return String(iso);
        const opts = { day: "numeric", month: "short", year: "numeric" };
        if (conHora && String(iso).length > 10) Object.assign(opts, { hour: "numeric", minute: "2-digit" });
        return d.toLocaleString("es-MX", opts);
    }

    const pesos = (n) => Number(n || 0).toLocaleString("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });

    function sinAcentos(s) {
        return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
    }

    function texto(v, max = 5000) {
        if (v === null || v === undefined) return "";
        if (typeof v === "number" && !isFinite(v)) return "";
        if (typeof v === "number" && Number.isInteger(v) === false && Math.abs(v - Math.round(v)) < 1e-9) v = Math.round(v);
        let s = String(v);
        if (s === "nan" || s === "NaN" || s === "None" || s === "null") return "";
        s = s.trim();
        return s.length > max ? s.slice(0, max) : s;
    }

    function numero(v) {
        const n = parseFloat(String(v ?? "").replace(/[$,\s]/g, ""));
        return isFinite(n) && n >= 0 ? Math.round(n * 100) / 100 : 0;
    }

    function bandera(v, porDefecto = 0) {
        if (v === null || v === undefined || v === "") return porDefecto;
        if (typeof v === "boolean") return v ? 1 : 0;
        const s = sinAcentos(v);
        return ["1", "1.0", "true", "si", "yes"].includes(s) ? 1 : 0;
    }

    function urlSegura(url) {
        const s = texto(url, 500);
        if (!s) return "";
        const conEsquema = /^https?:\/\//i.test(s) ? s : (/^[\w.-]+\.[a-z]{2,}(\/|$)/i.test(s) ? `https://${s}` : "");
        try {
            const u = new URL(conEsquema);
            return (u.protocol === "https:" || u.protocol === "http:") ? u.href : "";
        } catch {
            return "";
        }
    }

    function primerasUrls(textoRedes) {
        return (String(textoRedes || "").match(/https?:\/\/[^\s,;]+/gi) || []).map(urlSegura).filter(Boolean).slice(0, 4);
    }

    function digitosWa(numero) {
        const d = String(numero || "").replace(/\D/g, "");
        if (d.length === 10) return `52${d}`;
        if (d.length >= 11 && d.length <= 15) return d;
        return "";
    }

    function digitosTel(numero) {
        const d = String(numero || "").replace(/\D/g, "");
        if (d.length === 10) return `+52${d}`;
        if (d.length >= 11 && d.length <= 15) return `+${d}`;
        return "";
    }

    function normalizarPrioridad(v) {
        const s = sinAcentos(v);
        if (s.includes("crit")) return "critical";
        if (s.includes("alt") || s.includes("high")) return "high";
        if (s.includes("baj") || s.includes("low")) return "low";
        return "medium";
    }

    function normalizarEstado(v) {
        const s = sinAcentos(v).replace(/\s+/g, "_");
        if (ESTADOS[s]) return s;
        if (s.includes("no_interesa")) return "no_interesa";
        if (s.includes("contactado")) return "contactado";
        if (s.includes("interesado")) return "interesado";
        if (s.includes("propuesta")) return "propuesta";
        if (s.includes("ganado") || s.includes("cerrado") || s.includes("venta")) return "ganado";
        if (s.includes("descartado")) return "descartado";
        if (s.includes("auditado")) return "auditado";
        return "investigado";
    }

    function waComprobado(p) {
        return ["WHATSAPP_COMPROBADO", "confirmado"].includes(p.whatsapp_estado) && !!p.whatsapp;
    }
    function waPendiente(p) {
        return ["WHATSAPP_PENDIENTE_VERIFICACION", "declarado"].includes(p.whatsapp_estado);
    }

    function estaBloqueado(p, mensaje) {
        if (!p) return false;
        if (Number(p.identidad_verificada) === 0) return true;
        if (p.servicio_sugerido === "no_contactar" || p.servicio_sugerido === "investigar_mas") return true;
        const m = String(mensaje ?? p.mensaje_personalizado ?? "").trim();
        return m.startsWith("[BLOQUEADO") || m.startsWith("[RECOMENDACIÓN");
    }

    let toastTimer = null;
    function toast(msg, tipo = "") {
        const t = $("#toast");
        t.textContent = msg;
        t.className = `toast ${tipo}`;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => t.classList.add("oculto"), 3800);
    }

    // ======================================================================
    // Almacenamiento local (IndexedDB, con respaldo en localStorage)
    // ======================================================================
    const DB_NOMBRE = "sabueso-movil";
    const DB_STORE = "kv";
    const CLAVE = "estado";
    let dbConexion = null;

    function abrirDB() {
        if (dbConexion) return Promise.resolve(dbConexion);
        return new Promise((resolve, reject) => {
            if (!("indexedDB" in window)) return reject(new Error("IndexedDB no disponible"));
            const req = indexedDB.open(DB_NOMBRE, 1);
            req.onupgradeneeded = () => req.result.createObjectStore(DB_STORE);
            req.onsuccess = () => { dbConexion = req.result; resolve(dbConexion); };
            req.onerror = () => reject(req.error);
        });
    }

    async function leerEstado() {
        try {
            const db = await abrirDB();
            return await new Promise((resolve, reject) => {
                const r = db.transaction(DB_STORE, "readonly").objectStore(DB_STORE).get(CLAVE);
                r.onsuccess = () => resolve(r.result || null);
                r.onerror = () => reject(r.error);
            });
        } catch {
            try { return JSON.parse(localStorage.getItem(`${DB_NOMBRE}:${CLAVE}`) || "null"); } catch { return null; }
        }
    }

    async function escribirEstado(valor) {
        try {
            const db = await abrirDB();
            await new Promise((resolve, reject) => {
                const tx = db.transaction(DB_STORE, "readwrite");
                tx.objectStore(DB_STORE).put(valor, CLAVE);
                tx.oncomplete = () => resolve();
                tx.onerror = () => reject(tx.error);
                tx.onabort = () => reject(tx.error);
            });
        } catch (err) {
            localStorage.setItem(`${DB_NOMBRE}:${CLAVE}`, JSON.stringify(valor));
        }
    }

    function estadoVacio() {
        return {
            version: 1,
            dispositivo: uuid(),
            prospectos: {},
            alias: {},
            eventos: [],
            meta: { ultima_importacion: "", origen_importacion: "", ultima_exportacion: "", ultimo_respaldo: "", municipio_reciente: "" }
        };
    }

    let estado = estadoVacio();

    async function guardar() {
        try {
            await escribirEstado(estado);
        } catch (err) {
            toast("No se pudo guardar en el celular. Haz un respaldo cuanto antes.", "error");
            throw err;
        }
    }

    // ======================================================================
    // Eventos y vistas (base de la PC + avances del celular aún no confirmados)
    // ======================================================================
    function resolverUid(uid) {
        return estado.alias[uid] || uid;
    }

    function nuevoEvento(tipo, uid, datos) {
        const ev = { id: uuid(), tipo, uid, fecha: ahoraISO(), datos, exportado_en: "", sincronizado: false };
        estado.eventos.push(ev);
        return ev;
    }

    function aplicarEvento(v, ev) {
        const d = ev.datos || {};
        if (ev.tipo === "contacto_confirmado") {
            v.estado_comercial = "contactado";
            v.fecha_contacto_confirmada = d.fecha || ev.fecha;
            v.canal = d.canal;
        } else if (ev.tipo === "actualizacion") {
            Object.assign(v, d);
        } else if (ev.tipo === "nota") {
            v.notas_movil.push({ fecha: ev.fecha, texto: d.texto });
        }
    }

    function construirVistas() {
        const porUid = {};
        for (const ev of estado.eventos) {
            const uid = resolverUid(ev.uid);
            (porUid[uid] = porUid[uid] || []).push(ev);
        }
        const vistas = {};
        for (const [uid, base] of Object.entries(estado.prospectos)) {
            const v = { ...base, uid, notas_movil: [], historial: porUid[uid] || [] };
            for (const ev of v.historial) {
                if (!ev.sincronizado) aplicarEvento(v, ev);
            }
            v.pendientes = v.historial.filter((e) => !e.sincronizado).length;
            vistas[uid] = v;
        }
        return vistas;
    }

    function ordenar(lista) {
        return lista.sort((a, b) =>
            (RANGO_PRIORIDAD[a.prioridad] ?? 2) - (RANGO_PRIORIDAD[b.prioridad] ?? 2) ||
            (b.puntuacion || 0) - (a.puntuacion || 0) ||
            String(a.nombre).localeCompare(String(b.nombre), "es")
        );
    }

    const fueContactado = (p) => !!p.fecha_contacto_confirmada || !["investigado", "auditado"].includes(p.estado_comercial);
    const porContactar = (p) => !fueContactado(p) && !estaBloqueado(p) && !!(p.whatsapp || p.telefono);
    const seguimientoVencido = (p) => !!p.fecha_seguimiento && p.fecha_seguimiento <= hoyISO() && !CERRADOS.has(p.estado_comercial);
    const eventosPendientes = () => estado.eventos.filter((e) => !e.sincronizado);

    // ======================================================================
    // Copiloto CÍDIKS (versión de bolsillo para prospectos agregados en el celular)
    // Mantener alineado con copilot.py: Modalidad B (oportunidad exploratoria), sin halagos
    // ni afirmaciones que no se hayan comprobado.
    // ======================================================================
    const RE_HOSPEDAJE = /hotel|hosped|posada|hostal|hostel|caba[nñ]a|bungalow|glamping|suite|villa|resort|casa de hu[eé]sped/i;

    function capacidad(servicio, hospedaje) {
        const textos = {
            catalogos: ["Catálogos digitales para WhatsApp", hospedaje
                ? "catálogos digitales y fichas ligeras de habitaciones y tarifas para responder consultas en WhatsApp"
                : "catálogos digitales de productos y servicios para responder consultas en WhatsApp"],
            web: ["Presencia web con contacto directo", hospedaje
                ? "páginas web rápidas conectadas a WhatsApp para facilitar consultas y reservaciones directas"
                : "páginas web rápidas conectadas a WhatsApp para que los clientes los encuentren y escriban directo"],
            flyers: ["Flyers y promociones de temporada", "diseño de promociones, paquetes de temporada y piezas visuales para estados de WhatsApp y redes"],
            redes_sociales: ["Contenido digital y redes sociales", "organización visual de perfiles en Instagram y Facebook orientados a convertir visitas en consultas directas"],
            diseno: ["Diseño gráfico comercial", hospedaje
                ? "diseño de menús, guías para huéspedes, mapas locales y materiales de presentación del hospedaje"
                : "diseño de menús, catálogos impresos y digitales, y materiales de presentación del negocio"]
        };
        const [nombre, descripcion] = textos[servicio] || textos.catalogos;
        return { nombre, descripcion };
    }

    function elegirServicio(p) {
        const n = sinAcentos(`${p.nombre} ${p.sector}`);
        const tieneWa = !!p.whatsapp;
        if (!p.web) {
            if (!tieneWa && p.redes_sociales) return "redes_sociales";
            return "web";
        }
        if (/tour|surf|experiencia|viaje|aventura|mezcal|ecoturismo/.test(n)) return "flyers";
        if (/restaurante|cafe|palapa|bistro|bar|mirador|cocina|comida|fonda|taquer/.test(n)) return "diseno";
        if (!tieneWa) return p.redes_sociales ? "redes_sociales" : "web";
        return "catalogos";
    }

    function preguntaAdaptada(servicio, p, hospedaje) {
        const wa = waComprobado(p);
        if (hospedaje) {
            if (servicio === "catalogos") return wa
                ? "¿Actualmente comparten sus tipos de habitación y tarifas por WhatsApp mediante algún catálogo digital o los detallan en cada mensaje?"
                : "¿Actualmente manejan algún número de WhatsApp con catálogo de habitaciones para enviar informes a quienes llaman o escriben?";
            if (servicio === "web") return wa
                ? "¿Hoy los viajeros los encuentran principalmente por Google Maps y redes, o les gustaría tener una página propia conectada a su WhatsApp?"
                : "¿Tienen previsto incorporar atención por WhatsApp o prefieren centralizar las reservaciones por teléfono y correo?";
        }
        const generales = {
            catalogos: "¿Actualmente comparten sus productos o servicios por WhatsApp con algún catálogo digital o los detallan en cada mensaje?",
            web: "¿Hoy sus clientes los encuentran principalmente por Google Maps y redes, o les gustaría tener una página propia conectada a WhatsApp?",
            flyers: "¿Suelen preparar flyers o promociones de temporada para compartir por WhatsApp y redes?",
            redes_sociales: "¿Actualmente las consultas de sus clientes les llegan más por redes sociales o directo por WhatsApp?",
            diseno: "¿Cuentan actualmente con menú, catálogo o materiales de presentación actualizados para esta temporada?"
        };
        return generales[servicio] || generales.catalogos;
    }

    function generarMensajes(p) {
        const nombre = p.nombre || "su negocio";
        const loc = p.municipio ? ` en ${p.municipio}` : "";
        if (!Number(p.identidad_verificada)) {
            const bloq = `[BLOQUEADO — NO CONTACTAR TODAVÍA]\nMotivo: no confirmaste que ${nombre} exista y que sus datos de contacto sean públicos.\nAcción recomendada: verifica primero el negocio y su canal oficial antes de escribir.`;
            return { servicio_sugerido: "no_contactar", mensaje_personalizado: bloq, mensaje_calido: bloq, mensaje_seguimiento: bloq };
        }
        const hospedaje = RE_HOSPEDAJE.test(`${p.nombre} ${p.sector}`);
        const servicio = elegirServicio(p);
        const cap = capacidad(servicio, hospedaje);
        const pregunta = preguntaAdaptada(servicio, p, hospedaje);
        const aperturas = {
            maps: `Vi en Google Maps la ficha de ${nombre}${loc}.`,
            facebook: `Vi en Facebook la página de ${nombre}${loc}.`,
            instagram: `Vi en Instagram el perfil de ${nombre}${loc}.`,
            persona: `Pasé por ${nombre}${loc} y tomé sus datos de contacto.`,
            recomendacion: `Me compartieron los datos de contacto de ${nombre}${loc}.`,
            web: `Revisé la página de ${nombre}${loc}.`,
            otro: `Ubicamos los datos de contacto de ${nombre}${loc} a través de sus canales públicos.`
        };
        const apertura = aperturas[p.fuente] || aperturas.otro;
        const grupo = hospedaje ? "hospedajes de la región" : "negocios locales de Oaxaca";
        let hash = 0;
        for (const ch of nombre) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
        const estilos = [
            `Hola, buen día al equipo de ${nombre}. Les saludo desde CÍDIKS en Oaxaca.\n\n${apertura} En CÍDIKS colaboramos con ${grupo} en ${cap.descripcion}.\n\n${pregunta}`,
            `Hola, equipo de ${nombre}. Les escribo de CÍDIKS aquí en Oaxaca.\n\n${apertura} Apoyamos a ${grupo} con ${cap.descripcion}.\n\n${pregunta}`,
            `Buen día al equipo de ${nombre}, les saludo de CÍDIKS en Oaxaca.\n\n${apertura} Trabajamos con ${grupo} desarrollando ${cap.descripcion}.\n\n${pregunta}`
        ];
        return {
            servicio_sugerido: servicio,
            mensaje_personalizado: estilos[hash % 3],
            mensaje_calido: `Hola, equipo de ${nombre}, buen día desde CÍDIKS en Oaxaca.\n\n${apertura} Desarrollamos ${cap.descripcion} para ${grupo}.\n\n${pregunta}`,
            mensaje_seguimiento: `Hola de nuevo al equipo de ${nombre}, espero que vaya muy bien la semana${loc}.\n\nLes escribí hace unos días respecto a ${cap.nombre.toLowerCase()}. Si en este momento tienen cubierto el tema no hay ningún inconveniente; quedo a la orden si más adelante desean revisar algún ejemplo.`
        };
    }

    // ======================================================================
    // Importar desde la PC (JSON recomendado, o el CSV de "Exportar CSV")
    // ======================================================================
    function limpiarProspectoPC(raw) {
        const p = {};
        for (const k of CAMPOS_TEXTO) p[k] = texto(raw[k], k.startsWith("mensaje") || k === "notas" ? 8000 : 2000);
        for (const k of CAMPOS_NUM) p[k] = numero(raw[k]);
        for (const k of CAMPOS_FLAG) p[k] = bandera(raw[k], k === "identidad_verificada" ? 1 : 0);
        p.prioridad = normalizarPrioridad(p.prioridad);
        p.estado_comercial = normalizarEstado(p.estado_comercial);
        if (p.fecha_seguimiento && !/^\d{4}-\d{2}-\d{2}/.test(p.fecha_seguimiento)) p.fecha_seguimiento = "";
        p.fecha_seguimiento = p.fecha_seguimiento.slice(0, 10);
        p.nombre = p.nombre || "Sin nombre";
        p.origen = "pc";
        return p;
    }

    function parseCSV(txt) {
        txt = txt.replace(/^﻿/, "");
        const primera = txt.split(/\r?\n/, 1)[0] || "";
        const delim = primera.split(";").length > primera.split(",").length ? ";" : ",";
        const filas = [];
        let fila = [], campo = "", enComillas = false;
        for (let i = 0; i < txt.length; i++) {
            const c = txt[i];
            if (enComillas) {
                if (c === '"') {
                    if (txt[i + 1] === '"') { campo += '"'; i++; } else enComillas = false;
                } else campo += c;
                continue;
            }
            if (c === '"') enComillas = true;
            else if (c === delim) { fila.push(campo); campo = ""; }
            else if (c === "\n") { fila.push(campo); filas.push(fila); fila = []; campo = ""; }
            else if (c !== "\r") campo += c;
        }
        if (campo !== "" || fila.length) { fila.push(campo); filas.push(fila); }
        return filas.filter((f) => f.some((x) => x.trim() !== ""));
    }

    const MAPA_CSV = {
        "id": "id", "nombre del negocio": "nombre", "sector": "sector", "ubicacion": "municipio", "sitio web": "web",
        "telefono": "telefono", "whatsapp": "whatsapp", "estado whatsapp": "whatsapp_estado", "email": "email",
        "redes sociales": "redes_sociales", "puntuacion": "puntuacion", "prioridad": "prioridad",
        "estado comercial": "estado_comercial", "problemas detectados": "problemas_detectados",
        "mensaje aprobado": "mensaje_aprobado", "fecha de contacto": "fecha_contacto_confirmada",
        "canal de contacto": "canal", "respuesta del cliente": "respuesta", "necesidad confirmada": "necesidad_expresada",
        "propuesta enviada": "propuesta_enviada", "monto propuesta": "propuesta_monto", "venta acordada": "venta_acordada",
        "monto venta acordada": "venta_monto", "ingreso cobrado": "ingreso_cobrado", "mensaje frio": "mensaje_personalizado",
        "mensaje calido": "mensaje_calido", "mensaje seguimiento": "mensaje_seguimiento"
    };

    function prospectosDesdeCSV(txt) {
        const filas = parseCSV(txt);
        if (filas.length < 2) throw new Error("El CSV está vacío.");
        const columnas = filas[0].map((c) => MAPA_CSV[sinAcentos(c)] || null);
        if (!columnas.includes("id") || !columnas.includes("nombre")) {
            throw new Error("Este CSV no parece exportado desde Sabueso PC (faltan las columnas ID y Nombre del negocio).");
        }
        return filas.slice(1).map((f) => {
            const o = {};
            columnas.forEach((k, i) => { if (k) o[k] = f[i]; });
            return o;
        });
    }

    function integrarDesdePC(listaCruda, aplicados, origen) {
        const nuevos = {};
        let ignorados = 0;
        for (const raw of listaCruda) {
            const id = parseInt(String(raw.id ?? "").split(".")[0], 10);
            if (!Number.isInteger(id) || id <= 0) { ignorados++; continue; }
            const p = limpiarProspectoPC(raw);
            p.pc_id = id;
            const uid = `pc-${id}`;
            nuevos[uid] = p;
            if (/^m-[A-Za-z0-9-]{8,64}$/.test(p.movil_uid)) estado.alias[p.movil_uid] = uid;
        }

        // Conservar: prospectos creados en el celular que la PC aún no conoce, y prospectos
        // con avances pendientes aunque ya no vengan en el archivo (para no esconder trabajo).
        const conPendientes = new Set(eventosPendientes().map((e) => resolverUid(e.uid)));
        for (const [uid, p] of Object.entries(estado.prospectos)) {
            if (nuevos[uid]) continue;
            if (uid.startsWith("m-") && !estado.alias[uid]) nuevos[uid] = p;
            else if (conPendientes.has(uid) && !uid.startsWith("m-")) nuevos[uid] = { ...p, fuera_de_pc: true };
        }
        estado.prospectos = nuevos;

        let confirmados = 0;
        if (aplicados && aplicados.size) {
            for (const ev of estado.eventos) {
                if (!ev.sincronizado && aplicados.has(ev.id)) { ev.sincronizado = true; confirmados++; }
            }
        }
        // Mantener el historial acotado: se descartan los eventos ya confirmados más antiguos.
        const sincronizados = estado.eventos.filter((e) => e.sincronizado);
        if (sincronizados.length > 3000) {
            const sobran = new Set(sincronizados.slice(0, sincronizados.length - 3000).map((e) => e.id));
            estado.eventos = estado.eventos.filter((e) => !sobran.has(e.id));
        }

        estado.meta.ultima_importacion = ahoraISO();
        estado.meta.origen_importacion = origen;
        return { total: Object.keys(nuevos).length, ignorados, confirmados };
    }

    async function importarArchivo(file) {
        if (!file) return;
        if (file.size > MAX_ARCHIVO) throw new Error("El archivo es demasiado grande (máximo 15 MB).");
        const contenido = await file.text();
        const nombre = (file.name || "").toLowerCase();

        if (nombre.endsWith(".csv") || (!contenido.trim().startsWith("{") && contenido.includes(","))) {
            const lista = prospectosDesdeCSV(contenido);
            const r = integrarDesdePC(lista, null, "csv");
            await guardar();
            return `Listo: ${r.total} prospectos desde el CSV de la PC.` +
                (r.ignorados ? ` ${r.ignorados} filas sin ID se ignoraron.` : "") +
                " Tip: el archivo «Para el celular» de la PC trae más datos y confirma tus avances.";
        }

        let data;
        try { data = JSON.parse(contenido); } catch { throw new Error("El archivo no es un JSON válido."); }

        if (data && data.formato === FORMATO_RESPALDO) {
            if (!data.estado || typeof data.estado !== "object" || !data.estado.prospectos) throw new Error("El respaldo está incompleto.");
            if (!confirm("¿Restaurar este respaldo? Reemplaza TODO lo que hay ahora en Sabueso Móvil.")) return "Restauración cancelada.";
            const base = estadoVacio();
            estado = {
                ...base,
                ...data.estado,
                meta: { ...base.meta, ...(data.estado.meta || {}) },
                alias: data.estado.alias || {},
                eventos: Array.isArray(data.estado.eventos) ? data.estado.eventos : []
            };
            await guardar();
            return `Respaldo restaurado (${Object.keys(estado.prospectos).length} prospectos).`;
        }

        if (!data || data.formato !== FORMATO_PC || !Array.isArray(data.prospectos)) {
            if (data && data.formato === FORMATO_AVANCES) throw new Error("Ese es un archivo de avances: se importa en la PC, no aquí.");
            throw new Error("Este archivo no viene de Sabueso PC. Usa el botón «Celular → Descargar archivo para el celular».");
        }
        if (data.version !== 1) throw new Error("Versión de archivo no compatible. Actualiza Sabueso PC o Sabueso Móvil.");
        if (data.prospectos.length > 20000) throw new Error("El archivo trae demasiados prospectos.");

        const aplicados = new Set(Array.isArray(data.eventos_aplicados) ? data.eventos_aplicados.map(String) : []);
        const r = integrarDesdePC(data.prospectos, aplicados, "json");
        await guardar();
        return `Listo: ${r.total} prospectos al día.` + (r.confirmados ? ` La PC confirmó ${r.confirmados} avance(s) tuyos.` : "");
    }

    // ======================================================================
    // Exportar avances / respaldo (compartir con la hoja de iOS o descargar)
    // ======================================================================
    function nombreArchivo(prefijo) {
        return `${prefijo}_${ahoraISO().slice(0, 16).replace(/[-:]/g, "").replace("T", "_")}.json`;
    }

    async function compartirOBajar(nombre, objeto) {
        const blob = new Blob([JSON.stringify(objeto, null, 1)], { type: "application/json" });
        const file = new File([blob], nombre, { type: "application/json" });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
            try {
                await navigator.share({ files: [file], title: nombre });
                return true;
            } catch (err) {
                if (err && err.name === "AbortError") return false;
            }
        }
        const url = URL.createObjectURL(blob);
        const a = h("a", { href: url, download: nombre });
        document.body.append(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
        return true;
    }

    async function exportarAvances() {
        const pendientes = eventosPendientes();
        if (!pendientes.length) { toast("No hay avances nuevos para enviar a la PC."); return; }
        const paquete = {
            formato: FORMATO_AVANCES,
            version: 1,
            generado_en: ahoraISO(),
            dispositivo: estado.dispositivo,
            eventos: pendientes.map(({ id, tipo, uid, fecha, datos }) => ({ id, tipo, uid, fecha, datos }))
        };
        const ok = await compartirOBajar(nombreArchivo("sabueso_avances"), paquete);
        if (!ok) return;
        const cuando = ahoraISO();
        pendientes.forEach((e) => { e.exportado_en = e.exportado_en || cuando; });
        estado.meta.ultima_exportacion = cuando;
        await guardar();
        toast(`${pendientes.length} avance(s) listos para la PC. Impórtalos en Sabueso PC → Celular.`, "ok");
        render();
    }

    async function exportarRespaldo() {
        const ok = await compartirOBajar(nombreArchivo("sabueso_movil_respaldo"), { formato: FORMATO_RESPALDO, version: 1, generado_en: ahoraISO(), estado });
        if (!ok) return;
        estado.meta.ultimo_respaldo = ahoraISO();
        await guardar();
        toast("Respaldo creado. Guárdalo en Archivos o iCloud.", "ok");
        render();
    }

    // ======================================================================
    // Navegación
    // ======================================================================
    let tabActual = "hoy";
    let filtroLista = "todos";
    let textoBusqueda = "";
    let limiteLista = 60;
    let fichaUid = null;
    let tabMensaje = "mensaje_personalizado";
    let esperandoConfirmacion = null;
    const borradores = {};

    function cambiarTab(tab) {
        tabActual = tab;
        document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("activo", b.dataset.tab === tab));
        limiteLista = 60;
        render();
        window.scrollTo(0, 0);
    }

    function render() {
        const vistas = construirVistas();
        const cont = $("#vista");
        cont.replaceChildren();
        if (tabActual === "hoy") cont.append(...pantallaHoy(vistas));
        else if (tabActual === "prospectos") cont.append(...pantallaProspectos(vistas));
        else if (tabActual === "agregar") cont.append(...pantallaAgregar());
        else cont.append(...pantallaSync(vistas));

        const n = eventosPendientes().filter((e) => !e.exportado_en).length;
        const tabPc = document.querySelector('.tab[data-tab="sync"]');
        tabPc.querySelector(".punto")?.remove();
        if (n) tabPc.append(h("span", { class: "punto" }, n > 99 ? "99+" : n));

        if (fichaUid) renderFicha(vistas[fichaUid] ? fichaUid : null, vistas);
    }

    // ======================================================================
    // Pantalla: Hoy
    // ======================================================================
    function esAppInstalada() {
        return window.navigator.standalone === true || window.matchMedia("(display-mode: standalone)").matches;
    }

    function tarjetaProspecto(p, extra) {
        const badges = [
            h("span", { class: `badge badge-${p.prioridad}` }, PRIORIDADES[p.prioridad] || "Media"),
            h("span", { class: "badge badge-estado" }, ESTADOS[p.estado_comercial] || p.estado_comercial)
        ];
        if (waComprobado(p)) badges.push(h("span", { class: "badge badge-wa" }, "WhatsApp ✓"));
        else if (waPendiente(p)) badges.push(h("span", { class: "badge badge-pend" }, "WhatsApp por verificar"));
        if (estaBloqueado(p)) badges.push(h("span", { class: "badge badge-bloq" }, "No contactar aún"));
        if (p.fecha_seguimiento && !CERRADOS.has(p.estado_comercial)) {
            badges.push(h("span", { class: `badge ${seguimientoVencido(p) ? "badge-high" : ""}` }, `Seguimiento ${fechaBonita(p.fecha_seguimiento, false)}`));
        }
        if (p.pendientes) badges.push(h("span", { class: "badge badge-pend" }, `${p.pendientes} sin pasar a la PC`));
        if (p.origen === "movil" && !p.pc_id) badges.push(h("span", { class: "badge" }, "Nuevo del celular"));
        return h("article", { class: "card card-tap", role: "button", tabindex: "0", onclick: () => abrirFicha(p.uid) },
            h("div", { class: "p-fila" },
                h("div", null,
                    h("div", { class: "p-nombre" }, p.nombre),
                    h("div", { class: "p-meta" }, [p.sector, p.municipio].filter(Boolean).join(" · ") || "Sin giro ni municipio")
                ),
                h("span", { class: "chico", "aria-hidden": "true" }, "›")
            ),
            extra ? h("div", { class: "chico" }, extra) : null,
            h("div", { class: "badges" }, badges)
        );
    }

    function pantallaHoy(vistas) {
        const lista = Object.values(vistas);
        const out = [h("h2", null, "Hoy"), h("p", { class: "sub" }, fechaBonita(hoyISO(), false))];

        if (!esAppInstalada()) {
            out.push(h("div", { class: "aviso aviso-alerta" },
                h("strong", null, "Instálala en tu iPhone"),
                "En Safari toca Compartir (□↑) → «Agregar a pantalla de inicio». Así abre sin internet y iOS no borra tus datos."
            ));
        }

        if (!lista.length) {
            out.push(h("div", { class: "vacio" },
                h("p", null, "Aún no hay prospectos en tu celular."),
                h("p", { class: "chico" }, "Trae los de tu PC con un archivo, o agrega negocios que encuentres en Maps o en la calle."),
                h("div", { class: "fila-btns" },
                    h("button", { class: "btn btn-primario", type: "button", onclick: () => cambiarTab("sync") }, "Traer de la PC"),
                    h("button", { class: "btn", type: "button", onclick: () => cambiarTab("agregar") }, "Agregar negocio")
                )
            ));
            return out;
        }

        const pendientes = eventosPendientes();
        const sinExportar = pendientes.filter((e) => !e.exportado_en).length;
        if (sinExportar) {
            out.push(h("div", { class: "aviso aviso-info" },
                h("strong", null, `${sinExportar} avance(s) solo están en tu celular`),
                "Cuando puedas, mándalos a la PC para no perderlos.",
                h("button", { class: "btn btn-primario btn-bloque", type: "button", onclick: exportarAvances }, "Enviar avances a la PC")
            ));
        }
        const diasRespaldo = estado.meta.ultimo_respaldo ? (Date.now() - new Date(estado.meta.ultimo_respaldo)) / 864e5 : Infinity;
        if (pendientes.length >= 5 && diasRespaldo > 3) {
            out.push(h("div", { class: "aviso aviso-alerta" },
                h("strong", null, "Haz un respaldo"),
                "Tienes varios avances sin confirmar por la PC. Un respaldo en iCloud te protege si se borra Safari o cambias de celular.",
                h("button", { class: "btn btn-bloque", type: "button", onclick: exportarRespaldo }, "Crear respaldo")
            ));
        }

        const seguimientos = ordenar(lista.filter(seguimientoVencido));
        out.push(h("h3", null, `Seguimientos para hoy (${seguimientos.length})`));
        if (seguimientos.length) seguimientos.slice(0, 15).forEach((p) => out.push(tarjetaProspecto(p, p.siguiente_accion ? `Siguiente paso: ${p.siguiente_accion}` : "")));
        else out.push(h("p", { class: "parrafo" }, "Nada vencido. Pon fecha de seguimiento en la ficha de cada prospecto y aparecerá aquí."));

        const abiertos = ordenar(lista.filter((p) => ["interesado", "propuesta"].includes(p.estado_comercial) && !seguimientoVencido(p)));
        if (abiertos.length) {
            out.push(h("h3", null, `Interesados y propuestas abiertas (${abiertos.length})`));
            abiertos.slice(0, 10).forEach((p) => out.push(tarjetaProspecto(p)));
        }

        const nuevos = ordenar(lista.filter(porContactar));
        out.push(h("h3", null, `Por contactar (${nuevos.length})`));
        if (nuevos.length) {
            nuevos.slice(0, 10).forEach((p) => out.push(tarjetaProspecto(p)));
            if (nuevos.length > 10) out.push(h("button", { class: "btn btn-texto", type: "button", onclick: () => { filtroLista = "por_contactar"; cambiarTab("prospectos"); } }, `Ver los ${nuevos.length} →`));
        } else out.push(h("p", { class: "parrafo" }, "No hay prospectos listos para contactar."));

        out.push(h("h3", null, "Tus números"));
        const contactados = lista.filter(fueContactado).length;
        const interesados = lista.filter((p) => ["interesado", "propuesta", "ganado"].includes(p.estado_comercial)).length;
        const propuestas = lista.filter((p) => Number(p.propuesta_enviada)).length;
        const vendido = lista.filter((p) => Number(p.venta_acordada)).reduce((s, p) => s + numero(p.venta_monto), 0);
        const cobrado = lista.reduce((s, p) => s + numero(p.ingreso_cobrado), 0);
        out.push(h("div", { class: "metricas" },
            metrica(lista.length, "Prospectos"),
            metrica(contactados, "Contactos confirmados"),
            metrica(interesados, "Interesados"),
            metrica(propuestas, "Propuestas enviadas"),
            metrica(pesos(vendido), "Venta acordada"),
            metrica(pesos(cobrado), "Ingreso cobrado")
        ));
        return out;
    }

    function metrica(valor, etiqueta) {
        return h("div", { class: "metrica" }, h("div", { class: "metrica-valor" }, valor), h("div", { class: "metrica-etiqueta" }, etiqueta));
    }

    // ======================================================================
    // Pantalla: Prospectos
    // ======================================================================
    const FILTROS = {
        todos: ["Todos", () => true],
        por_contactar: ["Por contactar", porContactar],
        seguimiento: ["Seguimiento", seguimientoVencido],
        contactado: ["Contactados", (p) => p.estado_comercial === "contactado"],
        interesado: ["Interesados", (p) => p.estado_comercial === "interesado"],
        propuesta: ["Propuesta", (p) => p.estado_comercial === "propuesta"],
        ganado: ["Ganados", (p) => p.estado_comercial === "ganado"],
        cerrados: ["Cerrados", (p) => ["descartado", "no_interesa"].includes(p.estado_comercial)],
        bloqueados: ["No contactar", (p) => estaBloqueado(p)]
    };

    function pantallaProspectos(vistas) {
        const todos = Object.values(vistas);
        const lista = h("div", { id: "lista-prospectos" });

        // Solo se vuelve a dibujar la lista (no el buscador) para no cerrar el teclado del iPhone.
        const pintarLista = () => {
            const q = sinAcentos(textoBusqueda);
            const filtrados = ordenar(todos.filter((p) => {
                if (!FILTROS[filtroLista][1](p)) return false;
                if (!q) return true;
                return sinAcentos(`${p.nombre} ${p.sector} ${p.municipio} ${p.telefono} ${p.whatsapp}`).includes(q);
            }));
            const hijos = [];
            if (!filtrados.length) hijos.push(h("p", { class: "vacio" }, "Ningún prospecto coincide."));
            filtrados.slice(0, limiteLista).forEach((p) => hijos.push(tarjetaProspecto(p)));
            if (filtrados.length > limiteLista) {
                hijos.push(h("button", { class: "btn btn-bloque", type: "button", onclick: () => { limiteLista += 60; pintarLista(); } },
                    `Mostrar más (${filtrados.length - limiteLista} restantes)`));
            }
            lista.replaceChildren(...hijos);
        };

        const buscador = h("input", {
            class: "buscador", type: "search", placeholder: "Buscar por nombre, giro, municipio o teléfono",
            value: textoBusqueda, "aria-label": "Buscar prospectos", autocomplete: "off"
        });
        buscador.addEventListener("input", () => {
            textoBusqueda = buscador.value;
            limiteLista = 60;
            pintarLista();
        });

        const chips = h("div", { class: "chips", role: "tablist" },
            Object.entries(FILTROS).map(([k, [etq, fn]]) => h("button", {
                class: `chip ${filtroLista === k ? "activo" : ""}`, type: "button",
                onclick: () => { filtroLista = k; limiteLista = 60; render(); }
            }, `${etq} ${todos.filter(fn).length}`))
        );

        const out = [h("h2", null, "Prospectos"), buscador, chips];
        if (!todos.length) {
            out.push(h("div", { class: "vacio" }, "Todavía no hay prospectos.",
                h("div", null, h("button", { class: "btn btn-primario", type: "button", onclick: () => cambiarTab("sync") }, "Traer de la PC"))));
            return out;
        }
        pintarLista();
        out.push(lista);
        return out;
    }

    // ======================================================================
    // Ficha comercial
    // ======================================================================
    function abrirFicha(uid) {
        fichaUid = uid;
        tabMensaje = "mensaje_personalizado";
        document.body.classList.add("sin-scroll");
        render();
        $("#ficha").scrollTop = 0;
    }

    function cerrarFicha() {
        fichaUid = null;
        esperandoConfirmacion = null;
        $("#ficha").classList.add("oculto");
        $("#ficha").replaceChildren();
        document.body.classList.remove("sin-scroll");
        render();
    }

    function dato(k, v) {
        if (v === null || v === undefined || v === "") return null;
        return h("div", { class: "dato" }, h("span", { class: "dato-k" }, k), h("span", { class: "dato-v" }, v));
    }

    function renderFicha(uid, vistas) {
        const panel = $("#ficha");
        if (!uid) { cerrarFicha(); return; }
        const p = vistas[uid];
        const mensajeActual = p[tabMensaje] || "";
        const claveBorrador = `${uid}|${tabMensaje}`;
        const bloqueado = estaBloqueado(p, p.mensaje_personalizado);
        const scroll = panel.scrollTop;

        const area = h("textarea", {
            class: "mensaje", id: "msg-editor", "aria-label": "Mensaje para enviar",
            value: borradores[claveBorrador] ?? mensajeActual
        });
        const waDig = digitosWa(p.whatsapp || p.telefono);
        const tel = digitosTel(p.telefono || p.whatsapp);
        const email = (p.email || "").split(/[,;\s]/).find((x) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(x)) || "";
        const web = urlSegura(p.web);
        const puedeWa = !bloqueado && !!waDig;

        // Enlace real (tocado por la persona) para que iOS abra la app de WhatsApp con el mensaje.
        const enlaceWa = () => `https://wa.me/${waDig}?text=${encodeURIComponent(area.value)}`;
        const enlaceWaApp = () => `whatsapp://send?phone=${waDig}&text=${encodeURIComponent(area.value)}`;
        const btnWa = h("a", {
            class: `btn btn-wa ${puedeWa ? "" : "deshabilitado"}`,
            href: puedeWa ? enlaceWa() : "#", target: "_blank", rel: "noopener noreferrer"
        }, "WhatsApp");
        const btnWaApp = h("a", { class: `btn btn-texto ${puedeWa ? "" : "oculto"}`, href: puedeWa ? enlaceWaApp() : "#" }, "¿No abrió? Abrir directo en la app");
        const marcarEnvio = (e) => {
            if (!puedeWa) { e.preventDefault(); return; }
            esperandoConfirmacion = uid;
            setTimeout(() => { if (fichaUid === uid) render(); }, 1500);
        };
        btnWa.addEventListener("click", marcarEnvio);
        btnWaApp.addEventListener("click", marcarEnvio);
        const btnCopiar = h("button", { class: "btn", type: "button", disabled: bloqueado }, "Copiar");
        btnCopiar.addEventListener("click", async () => {
            try { await navigator.clipboard.writeText(area.value); }
            catch { area.select(); document.execCommand("copy"); }
            toast("Mensaje copiado. Cuando lo envíes, confirma el contacto aquí.");
        });

        const tabs = h("div", { class: "tabs-msg", role: "tablist" },
            [["mensaje_personalizado", "Frío"], ["mensaje_calido", "Redes"], ["mensaje_seguimiento", "Seguimiento"]].map(([k, etq]) =>
                h("button", { class: `tab-msg ${tabMensaje === k ? "activo" : ""}`, type: "button", onclick: () => { tabMensaje = k; render(); } }, etq))
        );

        const btnGuardarMsg = h("button", { class: `btn btn-chico ${area.value === mensajeActual ? "oculto" : ""}`, type: "button" }, "Guardar cambios del mensaje");
        area.addEventListener("input", () => {
            borradores[claveBorrador] = area.value;
            btnGuardarMsg.classList.toggle("oculto", area.value === mensajeActual);
            if (puedeWa) { btnWa.href = enlaceWa(); btnWaApp.href = enlaceWaApp(); }
        });
        btnGuardarMsg.addEventListener("click", async () => {
            nuevoEvento("actualizacion", uid, { [tabMensaje]: texto(area.value, 5000) });
            delete borradores[claveBorrador];
            await guardar();
            toast("Mensaje guardado.", "ok");
            render();
        });

        const contactoInfo = fueContactado(p) && p.fecha_contacto_confirmada
            ? h("div", { class: "aviso aviso-ok" }, h("strong", null, "Contacto confirmado"),
                `${fechaBonita(p.fecha_contacto_confirmada)} · ${CANALES[p.canal] || p.canal || "canal sin registrar"}`)
            : null;

        const preguntaEnvio = esperandoConfirmacion === uid && !p.fecha_contacto_confirmada
            ? h("div", { class: "aviso aviso-info" },
                h("strong", null, "¿Sí enviaste el mensaje?"),
                "Abrir WhatsApp no cuenta como contacto. Confírmalo solo si de verdad lo mandaste.",
                h("div", { class: "fila-btns" },
                    h("button", { class: "btn btn-ok", type: "button", onclick: () => hojaConfirmarContacto(p) }, "Sí, confirmar"),
                    h("button", { class: "btn", type: "button", onclick: () => { esperandoConfirmacion = null; render(); } }, "Todavía no")
                ))
            : null;

        const redes = primerasUrls(p.redes_sociales);
        const cuerpo = h("div", { class: "ficha-cuerpo" },
            h("h2", { id: "ficha-titulo" }, p.nombre),
            h("p", { class: "sub" }, [p.sector, p.municipio].filter(Boolean).join(" · ")),
            h("div", { class: "badges" },
                h("span", { class: `badge badge-${p.prioridad}` }, `Prioridad ${PRIORIDADES[p.prioridad] || "Media"}`),
                h("span", { class: "badge badge-estado" }, ESTADOS[p.estado_comercial] || p.estado_comercial),
                p.puntuacion ? h("span", { class: "badge" }, `${p.puntuacion}/100`) : null,
                waComprobado(p) ? h("span", { class: "badge badge-wa" }, "WhatsApp comprobado") : null,
                waPendiente(p) ? h("span", { class: "badge badge-pend" }, "WhatsApp por verificar") : null,
                p.fuera_de_pc ? h("span", { class: "badge badge-pend" }, "Ya no viene en el archivo de la PC") : null
            ),
            bloqueado ? h("div", { class: "aviso aviso-peligro" }, h("strong", null, "No contactar todavía"),
                "Sabueso marcó este prospecto como bloqueado (identidad sin verificar o requiere investigar más). No se puede enviar mensaje desde aquí.") : null,
            preguntaEnvio,
            contactoInfo,

            h("h3", null, "Mensaje"),
            tabs,
            h("div", { class: "campo" }, area),
            btnGuardarMsg,
            h("div", { class: "fila-btns" }, btnWa, btnCopiar),
            btnWaApp,
            h("div", { class: "fila-btns fila-btns-3" },
                h("a", { class: `btn ${tel ? "" : "deshabilitado"}`, href: tel ? `tel:${tel}` : "#" }, "Llamar"),
                h("a", { class: `btn ${email && !bloqueado ? "" : "deshabilitado"}`, href: email && !bloqueado ? `mailto:${email}?subject=${encodeURIComponent("Atención digital para su negocio")}&body=${encodeURIComponent(mensajeActual)}` : "#" }, "Correo"),
                h("a", { class: `btn ${web ? "" : "deshabilitado"}`, href: web || "#", target: "_blank", rel: "noopener noreferrer" }, "Sitio")
            ),
            !p.fecha_contacto_confirmada
                ? h("button", { class: "btn btn-ok btn-bloque", type: "button", onclick: () => hojaConfirmarContacto(p) }, "Confirmar contacto")
                : h("button", { class: "btn btn-bloque", type: "button", onclick: () => hojaConfirmarContacto(p) }, "Registrar otro contacto"),

            h("h3", null, "Datos"),
            h("div", { class: "card" },
                dato("WhatsApp", p.whatsapp),
                dato("Teléfono", p.telefono),
                dato("Correo", email),
                dato("Sitio web", web ? h("a", { href: web, target: "_blank", rel: "noopener noreferrer" }, web.replace(/^https?:\/\//, "").slice(0, 40)) : ""),
                dato("Redes", redes.length ? h("span", null, redes.map((u, i) => [i ? " · " : "", h("a", { href: u, target: "_blank", rel: "noopener noreferrer" }, new URL(u).hostname.replace("www.", ""))])) : texto(p.redes_sociales, 120)),
                dato("Origen", p.origen === "movil" ? `Agregado en el celular (${FUENTES[p.fuente] || "otro"})` : (p.pc_id ? `Sabueso PC #${p.pc_id}` : ""))
            ),

            (p.observacion_verificada || p.problemas_detectados || p.pregunta_comercial) ? h("div", null,
                h("h3", null, "Lo que encontró Sabueso"),
                h("div", { class: "card" },
                    p.observacion_verificada ? h("p", { class: "chico" }, h("strong", null, "Observación: "), p.observacion_verificada) : null,
                    p.problemas_detectados ? h("p", { class: "chico" }, h("strong", null, "Problemas detectados: "), p.problemas_detectados) : null,
                    p.pregunta_comercial ? h("p", { class: "chico" }, h("strong", null, "Pregunta sugerida: "), p.pregunta_comercial) : null
                )) : null,

            h("h3", null, "Seguimiento comercial"),
            formularioCRM(p),

            h("h3", null, "Notas"),
            p.notas ? h("div", { class: "nota-pc" }, p.notas) : null,
            p.notas_movil.length ? h("div", { class: "nota-pc" }, p.notas_movil.map((n) => `[${fechaBonita(n.fecha)}] ${n.texto}`).join("\n")) : null,
            formularioNota(uid),

            p.historial.length ? h("div", null,
                h("h3", null, "Historial en este celular"),
                h("div", { class: "card" }, [...p.historial].reverse().map((ev) => itemHistorial(ev)))
            ) : null
        );

        panel.replaceChildren(
            h("div", { class: "ficha-barra" },
                h("button", { class: "btn btn-texto", type: "button", onclick: cerrarFicha }, "‹ Volver"),
                h("span", { class: "chico" }, p.pendientes ? `${p.pendientes} avance(s) sin confirmar por la PC` : "")
            ),
            cuerpo
        );
        panel.classList.remove("oculto");
        panel.scrollTop = scroll;
    }

    function itemHistorial(ev) {
        const d = ev.datos || {};
        let desc = "";
        if (ev.tipo === "contacto_confirmado") desc = `Contacto confirmado por ${CANALES[d.canal] || d.canal}`;
        else if (ev.tipo === "nota") desc = `Nota: ${texto(d.texto, 60)}`;
        else if (ev.tipo === "nuevo_prospecto") desc = "Alta del prospecto en el celular";
        else desc = `Actualización: ${Object.keys(d).map((k) => k.replace(/_/g, " ")).join(", ")}`;
        const estadoEv = ev.sincronizado ? "✓ en la PC" : (ev.exportado_en ? "Enviado, falta confirmar" : "Solo en el celular");
        const puedeDeshacer = !ev.sincronizado && !ev.exportado_en && ev.tipo !== "nuevo_prospecto";
        return h("div", { class: "historial-item" },
            h("div", null, h("div", null, desc), h("div", { class: "muy-chico" }, `${fechaBonita(ev.fecha)} · ${estadoEv}`)),
            puedeDeshacer ? h("button", { class: "btn btn-texto", type: "button", onclick: () => deshacerEvento(ev.id) }, "Deshacer") : null
        );
    }

    async function deshacerEvento(id) {
        if (!confirm("¿Deshacer este avance? Solo se borra del celular (aún no se había enviado a la PC).")) return;
        estado.eventos = estado.eventos.filter((e) => e.id !== id);
        await guardar();
        toast("Avance deshecho.");
        render();
    }

    function formularioCRM(p) {
        const sel = h("select", { id: "crm-estado" },
            Object.entries(ESTADOS).map(([k, etq]) => h("option", {
                value: k, selected: p.estado_comercial === k,
                disabled: k === "contactado" && p.estado_comercial !== "contactado"
            }, k === "contactado" ? `${etq} (usa «Confirmar contacto»)` : etq))
        );
        sel.value = p.estado_comercial;
        const f = {
            respuesta: h("textarea", { id: "crm-respuesta", value: p.respuesta || "", placeholder: "¿Qué contestó?" }),
            necesidad_expresada: h("input", { id: "crm-necesidad", type: "text", value: p.necesidad_expresada || "", placeholder: "Lo que el cliente dijo que necesita" }),
            siguiente_accion: h("input", { id: "crm-siguiente", type: "text", value: p.siguiente_accion || "", placeholder: "Ej. Mandar ejemplo de catálogo" }),
            fecha_seguimiento: h("input", { id: "crm-fecha", type: "date", value: p.fecha_seguimiento || "" }),
            propuesta_enviada: h("input", { id: "crm-prop", type: "checkbox", checked: !!Number(p.propuesta_enviada) }),
            propuesta_monto: h("input", { id: "crm-prop-monto", type: "number", inputmode: "decimal", min: "0", step: "1", value: p.propuesta_monto || "" }),
            venta_acordada: h("input", { id: "crm-venta", type: "checkbox", checked: !!Number(p.venta_acordada) }),
            venta_monto: h("input", { id: "crm-venta-monto", type: "number", inputmode: "decimal", min: "0", step: "1", value: p.venta_monto || "" }),
            ingreso_cobrado: h("input", { id: "crm-cobrado", type: "number", inputmode: "decimal", min: "0", step: "1", value: p.ingreso_cobrado || "" })
        };
        const guardarCRM = async () => {
            const nuevos = {
                estado_comercial: sel.value,
                respuesta: texto(f.respuesta.value, 2000),
                necesidad_expresada: texto(f.necesidad_expresada.value, 2000),
                siguiente_accion: texto(f.siguiente_accion.value, 2000),
                fecha_seguimiento: f.fecha_seguimiento.value || "",
                propuesta_enviada: f.propuesta_enviada.checked ? 1 : 0,
                propuesta_monto: numero(f.propuesta_monto.value),
                venta_acordada: f.venta_acordada.checked ? 1 : 0,
                venta_monto: numero(f.venta_monto.value),
                ingreso_cobrado: numero(f.ingreso_cobrado.value)
            };
            const cambios = {};
            for (const k of CAMPOS_CRM) {
                const antes = ["propuesta_enviada", "venta_acordada"].includes(k) ? (Number(p[k]) ? 1 : 0)
                    : ["propuesta_monto", "venta_monto", "ingreso_cobrado"].includes(k) ? numero(p[k]) : (p[k] || "");
                if (nuevos[k] !== antes) cambios[k] = nuevos[k];
            }
            if (cambios.estado_comercial === "contactado") delete cambios.estado_comercial;
            if (!Object.keys(cambios).length) { toast("No hay cambios que guardar."); return; }
            nuevoEvento("actualizacion", p.uid, cambios);
            await guardar();
            toast("Seguimiento guardado en el celular.", "ok");
            render();
        };
        return h("div", { class: "card" },
            h("div", { class: "campo" }, h("label", { for: "crm-estado" }, "Estado comercial"), sel),
            h("div", { class: "campo" }, h("label", { for: "crm-respuesta" }, "Respuesta del cliente"), f.respuesta),
            h("div", { class: "campo" }, h("label", { for: "crm-necesidad" }, "Necesidad confirmada"), f.necesidad_expresada),
            h("div", { class: "campo" }, h("label", { for: "crm-siguiente" }, "Siguiente paso"), f.siguiente_accion),
            h("div", { class: "campo" }, h("label", { for: "crm-fecha" }, "Fecha de seguimiento"), f.fecha_seguimiento),
            h("label", { class: "check" }, f.propuesta_enviada, "Propuesta enviada"),
            h("div", { class: "campo" }, h("label", { for: "crm-prop-monto" }, "Monto de la propuesta (MXN)"), f.propuesta_monto),
            h("label", { class: "check" }, f.venta_acordada, "Venta acordada"),
            h("div", { class: "dos-col" },
                h("div", { class: "campo" }, h("label", { for: "crm-venta-monto" }, "Monto acordado"), f.venta_monto),
                h("div", { class: "campo" }, h("label", { for: "crm-cobrado" }, "Ingreso cobrado"), f.ingreso_cobrado)
            ),
            h("p", { class: "muy-chico" }, "Una venta acordada no cuenta como cobrada: registra el ingreso solo cuando te paguen."),
            h("button", { class: "btn btn-primario btn-bloque", type: "button", onclick: guardarCRM }, "Guardar seguimiento")
        );
    }

    function formularioNota(uid) {
        const t = h("textarea", { id: "nota-nueva", placeholder: "Ej. Me pidió escribir después de las 5" });
        return h("div", null,
            h("div", { class: "campo" }, h("label", { for: "nota-nueva" }, "Agregar nota"), t),
            h("button", {
                class: "btn btn-bloque", type: "button", onclick: async () => {
                    const v = texto(t.value, 2000);
                    if (!v) { toast("Escribe la nota primero."); return; }
                    nuevoEvento("nota", uid, { texto: v });
                    await guardar();
                    toast("Nota guardada.", "ok");
                    render();
                }
            }, "Guardar nota")
        );
    }

    function cerrarHoja() {
        const hoja = $("#hoja");
        hoja.classList.add("oculto");
        hoja.replaceChildren();
    }

    function hojaConfirmarContacto(p) {
        const bloqueado = estaBloqueado(p);
        const canal = h("select", { id: "cc-canal" }, Object.entries(CANALES).map(([k, v]) => h("option", { value: k, selected: k === "whatsapp" }, v)));
        const fecha = h("input", { id: "cc-fecha", type: "datetime-local", value: ahoraISO().slice(0, 16) });
        const notas = h("textarea", { id: "cc-notas", placeholder: bloqueado ? "Obligatoria: explica por qué hubo contacto con un prospecto bloqueado" : "Opcional: con quién hablaste, qué dijeron" });
        const confirma = h("input", { type: "checkbox", id: "cc-ok" });
        const hoja = $("#hoja");
        hoja.replaceChildren(h("div", { class: "hoja", role: "dialog", "aria-labelledby": "cc-titulo" },
            h("h2", { id: "cc-titulo" }, "Confirmar contacto"),
            h("p", { class: "parrafo" }, p.nombre),
            bloqueado ? h("div", { class: "aviso aviso-peligro" }, "Prospecto bloqueado: solo registra un contacto que de verdad ocurrió, con una nota que lo explique.") : null,
            h("div", { class: "campo" }, h("label", { for: "cc-canal" }, "¿Por dónde?"), canal),
            h("div", { class: "campo" }, h("label", { for: "cc-fecha" }, "¿Cuándo?"), fecha),
            h("div", { class: "campo" }, h("label", { for: "cc-notas" }, "Notas"), notas),
            h("label", { class: "check" }, confirma, "Confirmo que sí envié el mensaje o hablé con el negocio."),
            h("div", { class: "fila-btns" },
                h("button", { class: "btn", type: "button", onclick: cerrarHoja }, "Cancelar"),
                h("button", {
                    class: "btn btn-ok", type: "button", onclick: async () => {
                        if (!confirma.checked) { toast("Marca la casilla para confirmar."); return; }
                        const nota = texto(notas.value, 2000);
                        if (bloqueado && !nota) { toast("Este prospecto está bloqueado: la nota es obligatoria.", "error"); return; }
                        const cuando = fecha.value ? `${fecha.value}:00` : ahoraISO();
                        nuevoEvento("contacto_confirmado", p.uid, { canal: canal.value, notas: nota, fecha: cuando });
                        esperandoConfirmacion = null;
                        await guardar();
                        cerrarHoja();
                        toast("Contacto confirmado en el celular.", "ok");
                        render();
                    }
                }, "Confirmar")
            )
        ));
        hoja.classList.remove("oculto");
        hoja.onclick = (e) => { if (e.target === hoja) cerrarHoja(); };
    }

    // ======================================================================
    // Pantalla: Buscar / Agregar
    // ======================================================================
    function pantallaAgregar() {
        const giro = h("input", { id: "bq-giro", type: "text", placeholder: "Ej. hotel, restaurante, tours", autocomplete: "off" });
        const muni = h("input", { id: "bq-muni", type: "text", value: estado.meta.municipio_reciente || "", placeholder: "Ej. Puerto Escondido", autocomplete: "off" });
        const abrirBusqueda = (tipo) => {
            const q = `${texto(giro.value, 80)} ${texto(muni.value, 80)} Oaxaca`.trim();
            if (!texto(giro.value)) { toast("Escribe qué tipo de negocio buscas."); return; }
            estado.meta.municipio_reciente = texto(muni.value, 80);
            guardar();
            const urls = {
                maps: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`,
                google: `https://www.google.com/search?q=${encodeURIComponent(q + " whatsapp")}`,
                facebook: `https://www.facebook.com/search/pages/?q=${encodeURIComponent(q)}`
            };
            window.open(urls[tipo], "_blank", "noopener");
        };

        const f = {
            nombre: h("input", { id: "ag-nombre", type: "text", autocomplete: "off", placeholder: "Nombre comercial" }),
            sector: h("input", { id: "ag-sector", type: "text", autocomplete: "off", placeholder: "Ej. Hotel, Restaurante" }),
            municipio: h("input", { id: "ag-muni", type: "text", autocomplete: "off", value: estado.meta.municipio_reciente || "" }),
            whatsapp: h("input", { id: "ag-wa", type: "tel", inputmode: "tel", placeholder: "10 dígitos" }),
            wa_ok: h("input", { id: "ag-wa-ok", type: "checkbox" }),
            telefono: h("input", { id: "ag-tel", type: "tel", inputmode: "tel", placeholder: "Si es distinto al WhatsApp" }),
            email: h("input", { id: "ag-email", type: "email", autocomplete: "off" }),
            web: h("input", { id: "ag-web", type: "url", inputmode: "url", placeholder: "Si tiene" }),
            redes: h("input", { id: "ag-redes", type: "url", inputmode: "url", placeholder: "Link de Facebook o Instagram" }),
            fuente: h("select", { id: "ag-fuente" }, Object.entries(FUENTES).map(([k, v]) => h("option", { value: k }, v))),
            notas: h("textarea", { id: "ag-notas", placeholder: "Dónde lo viste, horario, quién atiende…" }),
            identidad: h("input", { id: "ag-identidad", type: "checkbox" })
        };

        const guardarNuevo = async () => {
            const nombre = texto(f.nombre.value, 200);
            if (!nombre) { toast("El nombre es obligatorio."); f.nombre.focus(); return; }
            const wa = texto(f.whatsapp.value, 40);
            const tel = texto(f.telefono.value, 40);
            if (wa && !digitosWa(wa)) { toast("El WhatsApp debe tener 10 dígitos (o lada internacional)."); return; }
            if (tel && !digitosTel(tel)) { toast("El teléfono debe tener 10 dígitos."); return; }
            const web = urlSegura(f.web.value);
            const redes = urlSegura(f.redes.value);
            const base = {
                nombre, sector: texto(f.sector.value, 120), municipio: texto(f.municipio.value, 120),
                whatsapp: wa, whatsapp_estado: wa && f.wa_ok.checked ? "confirmado" : "no_verificado",
                telefono: tel || wa, email: texto(f.email.value, 200), web, redes_sociales: redes,
                fuente: f.fuente.value, identidad_verificada: f.identidad.checked ? 1 : 0
            };
            const msgs = generarMensajes(base);
            const uid = `m-${uuid()}`;
            const datos = { ...base, ...msgs, notas: texto(f.notas.value, 2000) };
            estado.prospectos[uid] = {
                ...datos, origen: "movil", prioridad: "medium", estado_comercial: "investigado", puntuacion: 0,
                propuesta_enviada: 0, propuesta_monto: 0, venta_acordada: 0, venta_monto: 0, ingreso_cobrado: 0,
                fecha_contacto_confirmada: "", canal: "", respuesta: "", necesidad_expresada: "", siguiente_accion: "",
                fecha_seguimiento: "", observacion_verificada: "", problemas_detectados: "", pregunta_comercial: ""
            };
            nuevoEvento("nuevo_prospecto", uid, datos);
            estado.meta.municipio_reciente = base.municipio;
            await guardar();
            toast(base.identidad_verificada ? "Negocio agregado con mensaje listo." : "Negocio agregado, pero bloqueado hasta verificarlo.", "ok");
            abrirFicha(uid);
        };

        return [
            h("h2", null, "Buscar negocios"),
            h("p", { class: "parrafo" }, "Busca en Google Maps o Facebook y agrega aquí los que te sirvan. Esto sí necesita datos móviles."),
            h("div", { class: "card" },
                h("div", { class: "dos-col" },
                    h("div", { class: "campo" }, h("label", { for: "bq-giro" }, "¿Qué buscas?"), giro),
                    h("div", { class: "campo" }, h("label", { for: "bq-muni" }, "¿Dónde?"), muni)
                ),
                h("div", { class: "fila-btns fila-btns-3" },
                    h("button", { class: "btn btn-primario", type: "button", onclick: () => abrirBusqueda("maps") }, "Maps"),
                    h("button", { class: "btn", type: "button", onclick: () => abrirBusqueda("google") }, "Google"),
                    h("button", { class: "btn", type: "button", onclick: () => abrirBusqueda("facebook") }, "Facebook")
                ),
                h("p", { class: "muy-chico" }, "La búsqueda automática con auditoría web (como en la PC) necesita un servidor. Por ahora, desde el celular buscas tú y Sabueso te arma el mensaje.")
            ),

            h("h3", null, "Agregar negocio"),
            h("div", { class: "card" },
                h("div", { class: "campo" }, h("label", { for: "ag-nombre" }, "Nombre del negocio *"), f.nombre),
                h("div", { class: "dos-col" },
                    h("div", { class: "campo" }, h("label", { for: "ag-sector" }, "Giro"), f.sector),
                    h("div", { class: "campo" }, h("label", { for: "ag-muni" }, "Municipio"), f.municipio)
                ),
                h("div", { class: "campo" }, h("label", { for: "ag-wa" }, "WhatsApp"), f.whatsapp),
                h("label", { class: "check" }, f.wa_ok, "Comprobé que ese número sí tiene WhatsApp (lo vi en su ficha, su perfil o su botón)."),
                h("div", { class: "campo" }, h("label", { for: "ag-tel" }, "Teléfono"), f.telefono),
                h("div", { class: "dos-col" },
                    h("div", { class: "campo" }, h("label", { for: "ag-email" }, "Correo"), f.email),
                    h("div", { class: "campo" }, h("label", { for: "ag-fuente" }, "¿Dónde lo encontraste?"), f.fuente)
                ),
                h("div", { class: "campo" }, h("label", { for: "ag-web" }, "Sitio web"), f.web),
                h("div", { class: "campo" }, h("label", { for: "ag-redes" }, "Facebook / Instagram"), f.redes),
                h("div", { class: "campo" }, h("label", { for: "ag-notas" }, "Notas"), f.notas),
                h("label", { class: "check" }, f.identidad, "Verifiqué que el negocio existe, está activo y que estos datos de contacto son públicos."),
                h("p", { class: "muy-chico" }, "Sin esta casilla el prospecto queda como «No contactar todavía», igual que en la PC."),
                h("button", { class: "btn btn-primario btn-bloque", type: "button", onclick: guardarNuevo }, "Agregar y preparar mensaje")
            )
        ];
    }

    // ======================================================================
    // Pantalla: PC (sincronización y respaldo)
    // ======================================================================
    function pantallaSync(vistas) {
        const pendientes = eventosPendientes();
        const sinExportar = pendientes.filter((e) => !e.exportado_en).length;
        const enviadosSinConfirmar = pendientes.length - sinExportar;

        const input = h("input", { type: "file", accept: ".json,.csv,application/json,text/csv,text/comma-separated-values", class: "oculto", id: "archivo-pc" });
        input.addEventListener("change", async () => {
            const file = input.files && input.files[0];
            input.value = "";
            try {
                const msg = await importarArchivo(file);
                if (msg) toast(msg, "ok");
            } catch (err) {
                toast(err.message || "No se pudo leer el archivo.", "error");
            }
            render();
        });

        return [
            h("h2", null, "Sincronizar con la PC"),
            h("p", { class: "parrafo" }, "Todo se pasa con archivos: no necesitas que la PC tenga internet y tus datos no pasan por ningún servidor."),

            h("h3", null, "1. Traer prospectos de la PC"),
            h("div", { class: "card" },
                h("p", { class: "chico" }, estado.meta.ultima_importacion
                    ? `Última carga: ${fechaBonita(estado.meta.ultima_importacion)} (${estado.meta.origen_importacion === "csv" ? "CSV" : "archivo para celular"}) · ${Object.keys(vistas).length} prospectos`
                    : "Todavía no has cargado prospectos de la PC."),
                input,
                h("button", { class: "btn btn-primario btn-bloque", type: "button", onclick: () => input.click() }, "Elegir archivo de la PC"),
                h("p", { class: "muy-chico" }, "Acepta el archivo «sabueso_para_celular_….json» (recomendado) o el CSV de «Exportar CSV». También sirve para restaurar un respaldo. Tus avances sin enviar no se pierden al cargar uno nuevo.")
            ),

            h("h3", null, "2. Enviar tus avances a la PC"),
            h("div", { class: "card" },
                h("p", { class: "chico" }, `${sinExportar} avance(s) nuevos · ${enviadosSinConfirmar} enviados que la PC aún no confirma`),
                h("button", { class: "btn btn-primario btn-bloque", type: "button", disabled: !pendientes.length, onclick: exportarAvances }, "Enviar avances (compartir archivo)"),
                h("p", { class: "muy-chico" }, "Se abre el menú Compartir: mándatelo por WhatsApp, correo o guárdalo en Archivos. En Sabueso PC: botón «Celular» → «Importar avances del celular». Importarlo dos veces no duplica nada.")
            ),

            h("h3", null, "Respaldo"),
            h("div", { class: "card" },
                h("p", { class: "chico" }, estado.meta.ultimo_respaldo ? `Último respaldo: ${fechaBonita(estado.meta.ultimo_respaldo)}` : "Aún no has hecho respaldo."),
                h("button", { class: "btn btn-bloque", type: "button", onclick: exportarRespaldo }, "Crear respaldo completo"),
                h("p", { class: "muy-chico" }, "Guárdalo en iCloud Drive. Si cambias de celular o se borran los datos de Safari, lo restauras con «Elegir archivo de la PC».")
            ),

            h("h3", null, "¿La PC no tiene internet?"),
            h("ol", { class: "pasos" },
                h("li", null, h("strong", null, "Comparte internet desde tu iPhone: "), "Ajustes → Compartir Internet. Conecta la PC a esa red."),
                h("li", null, "En Sabueso PC toca «Celular» → «Descargar archivo para el celular» y mándatelo por WhatsApp Web o correo."),
                h("li", null, "En el iPhone abre el archivo desde aquí con «Elegir archivo de la PC»."),
                h("li", null, "Sabueso PC trabaja sin internet; solo la búsqueda y la auditoría web la necesitan.")
            ),

            h("div", { class: "separador" }),
            h("button", {
                class: "btn btn-peligro btn-bloque", type: "button", onclick: async () => {
                    if (pendientes.length && !confirm(`Tienes ${pendientes.length} avance(s) que la PC no ha confirmado. Si borras, se pierden. ¿Continuar?`)) return;
                    if (!confirm("¿Borrar TODOS los datos de Sabueso Móvil en este celular?")) return;
                    estado = estadoVacio();
                    await guardar();
                    toast("Datos borrados del celular.");
                    render();
                }
            }, "Borrar datos de este celular"),
            h("p", { class: "muy-chico" }, `Sabueso Móvil ${APP_VERSION} · Los datos se guardan solo en este iPhone.`)
        ];
    }

    // ======================================================================
    // Arranque
    // ======================================================================
    function actualizarRed() {
        const el = $("#red-estado");
        if (navigator.onLine) {
            el.textContent = "Con conexión · tus datos se quedan en el celular";
            el.classList.remove("offline");
        } else {
            el.textContent = "Sin internet · todo funciona igual";
            el.classList.add("offline");
        }
    }

    function registrarServiceWorker() {
        if (!("serviceWorker" in navigator)) return;
        // Solo se recarga cuando la persona toca «Actualizar» (nunca en la primera instalación
        // ni a media captura de datos).
        let actualizacionPedida = false;
        const ofrecerActualizacion = (worker) => {
            $("#aviso-actualizacion").classList.remove("oculto");
            $("#btn-recargar").onclick = () => {
                actualizacionPedida = true;
                worker.postMessage("activar-version-nueva");
            };
        };
        navigator.serviceWorker.register("sw.js").then((reg) => {
            if (reg.waiting && navigator.serviceWorker.controller) ofrecerActualizacion(reg.waiting);
            reg.addEventListener("updatefound", () => {
                const worker = reg.installing;
                if (!worker) return;
                worker.addEventListener("statechange", () => {
                    if (worker.state === "installed" && navigator.serviceWorker.controller) ofrecerActualizacion(worker);
                });
            });
        }).catch(() => { /* sin SW: la app sigue funcionando con conexión */ });
        navigator.serviceWorker.addEventListener("controllerchange", () => {
            if (actualizacionPedida) window.location.reload();
        });
    }

    async function iniciar() {
        document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => {
            if (fichaUid) cerrarFicha();
            cambiarTab(b.dataset.tab);
        }));
        window.addEventListener("online", actualizarRed);
        window.addEventListener("offline", actualizarRed);
        document.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "visible" && esperandoConfirmacion && fichaUid === esperandoConfirmacion) render();
        });
        actualizarRed();

        const guardado = await leerEstado();
        if (guardado && guardado.version === 1) {
            const base = estadoVacio();
            estado = { ...base, ...guardado, meta: { ...base.meta, ...(guardado.meta || {}) }, alias: guardado.alias || {} };
        } else {
            await guardar();
        }
        if (navigator.storage && navigator.storage.persist) {
            navigator.storage.persist().catch(() => { });
        }
        render();
        registrarServiceWorker();
    }

    // Exponer funciones puras para pruebas automatizadas (sin efectos en la app).
    window.__sabuesoMovil = { parseCSV, prospectosDesdeCSV, generarMensajes, estaBloqueado, digitosWa, urlSegura, normalizarEstado };

    iniciar().catch((err) => {
        $("#vista").replaceChildren(h("div", { class: "aviso aviso-peligro" }, h("strong", null, "No se pudo abrir Sabueso Móvil"), String(err && err.message || err)));
    });
})();
