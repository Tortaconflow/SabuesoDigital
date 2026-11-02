document.addEventListener("DOMContentLoaded", () => {
    // ========================================
    // Utility Functions & XSS Defense
    // ========================================
    function escapeHtml(str) {
        if (str === null || str === undefined) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function safeUrl(url) {
        if (!url || typeof url !== "string") return "#";
        const trimmed = url.trim();
        if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            return encodeURI(trimmed);
        }
        return "#";
    }

    function truncateUrl(url) {
        if (!url) return "";
        try {
            const u = new URL(url);
            return u.hostname.replace("www.", "");
        } catch {
            return url.substring(0, 30);
        }
    }

    // ========================================
    // DOM Elements
    // ========================================
    const searchForm = document.getElementById("search-form");
    const btnSearch = document.getElementById("btn-search");
    const btnExportCsv = document.getElementById("btn-export-csv");
    const btnExportXlsx = document.getElementById("btn-export-xlsx");
    const tableBody = document.getElementById("table-body");
    const detailPanel = document.getElementById("detail-panel");
    const panelClose = document.getElementById("panel-close");
    const editForm = document.getElementById("edit-prospect-form");
    
    // API Config Elements
    const btnConfigApi = document.getElementById("btn-config-api");
    const apiModal = document.getElementById("api-modal");
    const modalClose = document.getElementById("modal-close");
    const apiConfigForm = document.getElementById("api-config-form");
    const providerName = document.getElementById("provider-name");
    const aiProviderName = document.getElementById("ai-provider-name");
    const providerSearchStatus = document.getElementById("provider-search-status");
    const providerAiStatus = document.getElementById("provider-ai-status");
    
    // Logger Elements
    const progressLogger = document.getElementById("progress-logger-container");
    const loggerText = document.getElementById("logger-text");

    // Mobile Elements
    const btnMobileMenu = document.getElementById("btn-mobile-menu");
    const sidebar = document.getElementById("sidebar");
    const btnCloseSidebar = document.getElementById("btn-close-sidebar");
    const mobileOverlay = document.getElementById("mobile-overlay");

    if (btnMobileMenu) btnMobileMenu.addEventListener("click", () => {
        if (sidebar) sidebar.classList.add("mobile-open");
        if (mobileOverlay) mobileOverlay.classList.add("show");
    });
    if (btnCloseSidebar) btnCloseSidebar.addEventListener("click", () => {
        if (sidebar) sidebar.classList.remove("mobile-open");
        if (mobileOverlay) mobileOverlay.classList.remove("show");
    });
    if (mobileOverlay) mobileOverlay.addEventListener("click", () => {
        if (sidebar) sidebar.classList.remove("mobile-open");
        if (mobileOverlay) mobileOverlay.classList.remove("show");
    });

    // Stats elements (5 Métricas Separadas Cierre WhatsApp-First)
    const statDiscovered = document.getElementById("stat-discovered");
    const statTotal = document.getElementById("stat-total");
    const statCritical = document.getElementById("stat-critical");
    const statWa = document.getElementById("stat-wa");
    const statWaPending = document.getElementById("stat-wa-pending");
    const statActionable = document.getElementById("stat-actionable");
    const statOtherChannels = document.getElementById("stat-other-channels");
    const statContacted = document.getElementById("stat-contacted");
    const statRevenue = document.getElementById("stat-revenue");
    const microDiscovered = document.getElementById("micro-discovered");
    const microTotal = document.getElementById("micro-total");
    const microCritical = document.getElementById("micro-critical");
    const microWa = document.getElementById("micro-wa");
    const microWaPending = document.getElementById("micro-wa-pending");
    const microActionable = document.getElementById("micro-actionable");
    const microOtherChannels = document.getElementById("micro-other-channels");
    const microContacted = document.getElementById("micro-contacted");
    const microRevenue = document.getElementById("micro-revenue");

    // WhatsApp-First & Presets
    const detailWaBadge = document.getElementById("detail-wa-badge");
    const detailWaFuente = document.getElementById("detail-wa-fuente");
    const editServicioSugerido = document.getElementById("edit-servicio-sugerido");
    const btnRegenMsg = document.getElementById("btn-regen-msg");
    const btnPresetOaxaca = document.getElementById("btn-preset-oaxaca");

    // Pipeline step elements
    const stepBuscar = document.getElementById("step-buscar");
    const stepAuditar = document.getElementById("step-auditar");
    const stepCalificar = document.getElementById("step-calificar");
    const stepContactar = document.getElementById("step-contactar");
    const connector1 = document.getElementById("connector-1");
    const connector2 = document.getElementById("connector-2");
    const connector3 = document.getElementById("connector-3");

    // Detail Panel fields
    const editId = document.getElementById("edit-id");
    const editName = document.getElementById("edit-name");
    const editWeb = document.getElementById("edit-web");
    const editEmail = document.getElementById("edit-email");
    const editPhone = document.getElementById("edit-phone");
    const editWhatsapp = document.getElementById("edit-whatsapp");
    const editSocials = document.getElementById("edit-socials");
    const editScore = document.getElementById("edit-score");
    const editPriority = document.getElementById("edit-priority");
    const editStatus = document.getElementById("edit-status");
    const editIssues = document.getElementById("edit-issues");
    const editHipotesis = document.getElementById("edit-hipotesis");
    const editPregunta = document.getElementById("edit-pregunta");
    const editMessage = document.getElementById("edit-message");
    const editMsgApproved = document.getElementById("edit-msg-approved");
    const editRespuesta = document.getElementById("edit-respuesta");
    const editNecesidad = document.getElementById("edit-necesidad");
    const editPropuestaEnviada = document.getElementById("edit-propuesta-enviada");
    const editVentaAcordada = document.getElementById("edit-venta-acordada");
    const editVentaMonto = document.getElementById("edit-venta-monto");
    const editIngresoCobrado = document.getElementById("edit-ingreso-cobrado");
    const btnSaveEdit = document.getElementById("btn-save-edit");

    // Quarantine Modal Elements
    const btnQuarantineOpen = document.getElementById("btn-quarantine-open");
    const quarantineModal = document.getElementById("quarantine-modal");
    const quarantineModalClose = document.getElementById("quarantine-modal-close");
    const quarantineListContainer = document.getElementById("quarantine-list-container");
    const badgeQuarantineCount = document.getElementById("badge-quarantine-count");
    
    // Playwright Evidence in Detail Panel
    const evidenceBadge = document.getElementById("evidence-badge");
    const verifyTextInput = document.getElementById("verify-text-input");
    const btnRunVisualAudit = document.getElementById("btn-run-visual-audit");
    const screenshotContainer = document.getElementById("screenshot-container");
    const screenshotImg = document.getElementById("screenshot-img");
    const screenshotLink = document.getElementById("screenshot-link");

    // Outreach Links
    const linkWa = document.getElementById("link-wa");
    const linkMail = document.getElementById("link-mail");
    const btnCopyMsg = document.getElementById("btn-copy-msg");
    const btnConfirmContactModal = document.getElementById("btn-confirm-contact-modal");
    const outreachBlockedWarning = document.getElementById("outreach-blocked-warning");

    // Contact Confirm Modal
    const contactModal = document.getElementById("contact-confirm-modal");
    const contactModalClose = document.getElementById("contact-modal-close");
    const contactConfirmForm = document.getElementById("contact-confirm-form");
    const contactDate = document.getElementById("contact-date");
    const contactChannel = document.getElementById("contact-channel");
    const contactNotes = document.getElementById("contact-notes");

    // Import Modal Elements
    const btnImportOpen = document.getElementById("btn-import-open");
    const importModal = document.getElementById("import-modal");
    const importModalClose = document.getElementById("import-modal-close");
    const importFilePath = document.getElementById("import-file-path");
    const btnImportPreviewAction = document.getElementById("btn-import-preview-action");
    const importPreviewResults = document.getElementById("import-preview-results");
    const importSummaryText = document.getElementById("import-summary-text");
    const importPreviewTableWrap = document.getElementById("import-preview-table-wrap");
    const btnImportExecuteAction = document.getElementById("btn-import-execute-action");

    // Duplicates Modal Elements
    const btnDuplicatesOpen = document.getElementById("btn-duplicates-open");
    const duplicatesModal = document.getElementById("duplicates-modal");
    const duplicatesModalClose = document.getElementById("duplicates-modal-close");
    const duplicatesListContainer = document.getElementById("duplicates-list-container");

    // Toast Container
    const toastContainer = document.getElementById("toast-container");

    // History Elements
    const historySection = document.getElementById("history-section");
    const historyHeader = document.getElementById("history-header");
    const historyChips = document.getElementById("history-chips");
    const historyClearBtn = document.getElementById("history-clear-btn");

    // Debug Panel Elements
    const debugPanel = document.getElementById("debug-panel");
    const debugHeader = document.getElementById("debug-header");
    const debugBody = document.getElementById("debug-body");
    const debugQuery = document.getElementById("debug-query");
    const debugEngine = document.getElementById("debug-engine");
    const debugRaw = document.getElementById("debug-raw");
    const debugFiltered = document.getElementById("debug-filtered");
    const debugErrorRow = document.getElementById("debug-error-row");
    const debugError = document.getElementById("debug-error");

    // Auto-audit elements
    const autoAuditToggle = document.getElementById("auto-audit-toggle");
    const autoAuditBar = document.getElementById("auto-audit-bar");
    const auditBarText = document.getElementById("audit-bar-text");
    const auditBarFill = document.getElementById("audit-bar-fill");

    // ========================================
    // Local State
    // ========================================
    let prospects = [];
    let favorites = JSON.parse(localStorage.getItem("sabueso_favorites") || "[]");
    let activeFilter = "wa_main";
    let sortCol = "score";
    let sortDir = "desc";
    let selectedProspectId = null;
    let currentCategory = "";
    let currentLocation = "";
    let activeTab = "frio";
    let searchTimerInterval = null;

    if (btnPresetOaxaca) {
        btnPresetOaxaca.addEventListener("click", () => {
            const cat = document.getElementById("category");
            const loc = document.getElementById("location");
            const lim = document.getElementById("limit");
            if (cat) cat.value = "Turismo y hospedaje";
            if (loc) loc.value = "Costa de Oaxaca";
            if (lim) lim.value = "10";
            showToast("info", "Preset cargado", "Turismo y hospedaje · Costa de Oaxaca (Meta: 10 prospectos).");
        });
    }

    // Splash Screen
    const splash = document.getElementById("splash-screen");
    if (splash) {
        setTimeout(() => splash.remove(), 1800);
    }

    // Top Progress Bar
    const iosBar = document.getElementById("ios-progress-bar");
    function startIosProgress() {
        if (!iosBar) return null;
        iosBar.style.width = "0%";
        iosBar.classList.add("active");
        let w = 0;
        const iv = setInterval(() => {
            w += Math.random() * 8;
            if (w > 85) { clearInterval(iv); w = 85; }
            iosBar.style.width = w + "%";
        }, 300);
        return iv;
    }
    function finishIosProgress() {
        if (!iosBar) return;
        iosBar.style.width = "100%";
        setTimeout(() => {
            iosBar.classList.remove("active");
            iosBar.style.width = "0%";
        }, 400);
    }

    // Quick Filters
    const quickFilters = document.getElementById("quick-filters");
    if (quickFilters) {
        quickFilters.addEventListener("click", (e) => {
            const chip = e.target.closest(".filter-chip");
            if (!chip) return;
            quickFilters.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            activeFilter = chip.dataset.filter;
            renderTable();
        });
    }

    // Sortable Columns
    document.querySelectorAll(".sort-col").forEach(th => {
        th.addEventListener("click", () => {
            const col = th.dataset.col;
            if (sortCol === col) {
                sortDir = sortDir === "asc" ? "desc" : "asc";
            } else {
                sortCol = col;
                sortDir = col === "score" ? "desc" : "asc";
            }
            document.querySelectorAll(".sort-col").forEach(t => t.classList.remove("sort-asc", "sort-desc"));
            th.classList.add(sortDir === "asc" ? "sort-asc" : "sort-desc");
            renderTable();
        });
    });

    // Toast Notification System
    function showToast(type, title, message, duration = 4000) {
        const iconMap = {
            success: "fa-solid fa-circle-check",
            error: "fa-solid fa-circle-xmark",
            info: "fa-solid fa-circle-info",
            warning: "fa-solid fa-triangle-exclamation"
        };

        const toast = document.createElement("div");
        toast.className = "toast";
        toast.innerHTML = `
            <span class="toast-icon ${escapeHtml(type)}"><i class="${iconMap[type] || iconMap.info}"></i></span>
            <div class="toast-body">
                <div class="toast-title">${escapeHtml(title)}</div>
                ${message ? `<div class="toast-message">${escapeHtml(message)}</div>` : ""}
            </div>
        `;

        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.classList.add("toast-exit");
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    // ========================================
    // Data Loading & Persistence
    // ========================================
    async function loadProspects() {
        try {
            const res = await fetch("/api/prospects");
            if (!res.ok) throw new Error("Error cargando prospectos locales");
            prospects = await res.json();
            renderTable();
            updatePipelineSteps();
            updateMetrics();
            if (btnExportCsv) btnExportCsv.disabled = prospects.length === 0;
            if (btnExportXlsx) btnExportXlsx.disabled = prospects.length === 0;
        } catch (err) {
            console.error("Fallo al cargar prospectos:", err);
            showToast("error", "Error", "No se pudieron cargar los prospectos de la base local.");
        }
    }

    async function updateMetrics() {
        try {
            const res = await fetch("/api/metrics");
            if (!res.ok) return;
            const m = await res.json();
            
            const descubiertos = m.negocios_descubiertos ?? m.prospectos_investigados ?? m.total ?? 0;
            const waComprobados = m.con_whatsapp_comprobado ?? 0;
            const waPendientes = m.con_whatsapp_pendiente ?? 0;
            const revisables = m.oportunidades_revisables ?? 0;
            const contactados = m.contactos_confirmados ?? m.contactados ?? 0;
            const otrosCanales = m.otros_canales ?? 0;
            const cobrados = Number(m.ingresos_cobrados || 0);
            const cuarentena = m.en_cuarentena ?? 0;

            if (statDiscovered) statDiscovered.textContent = descubiertos;
            if (statTotal) statTotal.textContent = descubiertos;
            if (statCritical) statCritical.textContent = m.criticos ?? 0;
            if (statWa) statWa.textContent = waComprobados;
            if (statWaPending) statWaPending.textContent = waPendientes;
            if (statActionable) statActionable.textContent = revisables;
            if (statOtherChannels) statOtherChannels.textContent = otrosCanales;
            if (statContacted) statContacted.textContent = contactados;
            if (statRevenue) {
                statRevenue.textContent = `$${cobrados.toLocaleString('es-MX')} MXN`;
            }
            if (badgeQuarantineCount) {
                badgeQuarantineCount.textContent = cuarentena;
            }

            if (microDiscovered) {
                microDiscovered.textContent = `${descubiertos} prospectos investigados activos.`;
            }
            if (microWa) {
                microWa.textContent = `${waComprobados} enlaces o widgets directos comprobados.`;
            }
            if (microWaPending) {
                microWaPending.textContent = `${waPendientes} teléfono(s) en subpágina por verificar.`;
            }
            if (microActionable) {
                microActionable.textContent = `${revisables} prospectos verificados no bloqueados listos para revisión.`;
            }
            if (microOtherChannels) {
                microOtherChannels.textContent = `${otrosCanales} prospectos por teléfono, correo o redes.`;
            }
            if (microContacted) {
                microContacted.textContent = `${contactados} confirmados manualmente por usuario ($0 cobrado).`;
            }
            if (microRevenue) {
                microRevenue.textContent = `Cobrado efectivamente: $${cobrados.toLocaleString('es-MX')} MXN.`;
            }
        } catch (err) {
            console.error("Error al actualizar métricas:", err);
        }
    }

    function isWhatsAppProspect(p) {
        const st = p.whatsapp_estado || "";
        if (st === "WHATSAPP_COMPROBADO" || st === "confirmado") return true;
        if (st === "WHATSAPP_PENDIENTE_VERIFICACION" || st === "declarado") return true;
        if (p.whatsapp && String(p.whatsapp).trim() !== "" && st !== "SIN_WHATSAPP_COMPROBABLE") return true;
        return false;
    }

    // ========================================
    // Render Table (Safe XSS-free)
    // ========================================
    function renderTable() {
        if (!tableBody) return;

        // Actualizar contadores de bandejas
        const waCount = prospects.filter(p => isWhatsAppProspect(p)).length;
        const otherCount = prospects.filter(p => !isWhatsAppProspect(p)).length;
        const countWaTrayEl = document.getElementById("count-wa-tray");
        const countOtherTrayEl = document.getElementById("count-other-tray");
        if (countWaTrayEl) countWaTrayEl.textContent = waCount;
        if (countOtherTrayEl) countOtherTrayEl.textContent = otherCount;

        if (prospects.length === 0) {
            renderEmptyState();
            return;
        }

        let filtered = [...prospects];

        // Apply filters: Bandejas WhatsApp-First
        if (activeFilter === "wa_main") {
            filtered = filtered.filter(p => isWhatsAppProspect(p));
            // Ordenar: primero los comprobados, luego pendientes
            filtered.sort((a, b) => {
                const aComp = (a.whatsapp_estado === "WHATSAPP_COMPROBADO" || a.whatsapp_estado === "confirmado") ? 1 : 0;
                const bComp = (b.whatsapp_estado === "WHATSAPP_COMPROBADO" || b.whatsapp_estado === "confirmado") ? 1 : 0;
                return bComp - aComp;
            });
        } else if (activeFilter === "other_channels") {
            filtered = filtered.filter(p => !isWhatsAppProspect(p));
        } else if (activeFilter === "top10" || activeFilter === "top5") {
            filtered = filtered.sort((a, b) => (b.puntuacion || 0) - (a.puntuacion || 0)).slice(0, 10);
        } else if (activeFilter === "critical") {
            filtered = filtered.filter(p => p.prioridad === "critical" || (p.puntuacion && p.puntuacion >= 85));
        } else if (activeFilter === "contacted") {
            filtered = filtered.filter(p => p.estado_comercial === "contactado" || p.fecha_contacto_confirmada);
        } else if (activeFilter === "favorites") {
            filtered = filtered.filter(p => favorites.includes(String(p.id)) || favorites.includes(p.web || p.nombre));
        }

        // Apply sorting
        if (sortCol) {
            filtered.sort((a, b) => {
                let va, vb;
                if (sortCol === "score") {
                    va = parseFloat(a.puntuacion) || 0;
                    vb = parseFloat(b.puntuacion) || 0;
                } else if (sortCol === "nombre") {
                    va = (a.nombre || a["Nombre del negocio"] || "").toLowerCase();
                    vb = (b.nombre || b["Nombre del negocio"] || "").toLowerCase();
                } else if (sortCol === "prioridad") {
                    const weights = { "critical": 4, "high": 3, "medium": 2, "low": 1 };
                    va = weights[a.prioridad] || 0;
                    vb = weights[b.prioridad] || 0;
                }
                if (va < vb) return sortDir === "asc" ? -1 : 1;
                if (va > vb) return sortDir === "asc" ? 1 : -1;
                return 0;
            });
        }

        tableBody.innerHTML = "";

        if (filtered.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 40px; color: var(--text-muted);">
                <i class="fa-solid fa-filter" style="font-size: 24px; margin-bottom: 8px; display: block;"></i>
                Ningún prospecto en esta bandeja. Selecciona otra bandeja o realiza una búsqueda.
            </td></tr>`;
            return;
        }

        filtered.forEach((p, idx) => {
            const tr = document.createElement("tr");
            tr.dataset.id = p.id;
            tr.classList.add("stagger-in");
            tr.style.animationDelay = `${idx * 0.03}s`;
            if (selectedProspectId === p.id) tr.classList.add("selected");

            const scoreNum = parseInt(p.puntuacion) || 0;
            const priorityKey = p.prioridad || "medium";
            const priorityBadgeClass = getPriorityBadgeClass(priorityKey);
            const scoreClass = getScoreColorClass(scoreNum);

            // Safe URL
            const webUrl = p.web || p["Web"] || "";
            const webHtml = webUrl 
                ? `<a href="${safeUrl(webUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(truncateUrl(webUrl))}</a>` 
                : `<span class="text-muted">Sin Sitio Web</span>`;

            // Canal / WhatsApp badge
            let canalBadge = "";
            const st = p.whatsapp_estado || "";
            if (st === "WHATSAPP_COMPROBADO" || st === "confirmado" || (p.whatsapp && st !== "SIN_WHATSAPP_COMPROBABLE")) {
                canalBadge = `<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.4);"><i class="fa-brands fa-whatsapp"></i> ${escapeHtml(p.whatsapp || "Comprobado")}</span>`;
            } else if (st === "WHATSAPP_PENDIENTE_VERIFICACION" || st === "declarado") {
                canalBadge = `<span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4);"><i class="fa-solid fa-clock"></i> Pendiente WA</span>`;
            } else {
                const tipo = p.tipo_canal_principal || (p.telefono ? "telefono" : (p.email ? "email" : "otros"));
                canalBadge = `<span class="badge badge-low"><i class="fa-solid fa-${tipo === 'telefono' ? 'phone' : (tipo === 'email' ? 'envelope' : 'share-nodes')}"></i> ${escapeHtml(tipo)}</span>`;
            }

            // Propuesta CÍDIKS
            const servMap = {
                "catalogos": "Catálogos WA",
                "web": "Presencia Web",
                "flyers": "Flyers",
                "redes_sociales": "Redes Sociales",
                "diseno": "Diseño Gráfico",
                "investigar_mas": "🔍 Investigar más",
                "no_contactar": "⛔ No contactar"
            };
            const servLabel = servMap[p.servicio_sugerido] || "Catálogos WA";
            const servHtml = `<span style="font-size: 11px; color: var(--text-muted); font-weight: 500;">${escapeHtml(servLabel)}</span>`;

            // SVG Score Gauge
            const gaugeRadius = 14;
            const gaugeCirc = 2 * Math.PI * gaugeRadius;
            const gaugePct = Math.min(100, scoreNum) / 100;
            const strokeOffset = gaugeCirc * (1 - gaugePct);
            const gaugeColor = scoreNum >= 85 ? "#ef4444" : scoreNum >= 65 ? "#f59e0b" : scoreNum >= 45 ? "#3b82f6" : "#6b7280";
            
            const scoreGauge = scoreNum > 0 ? `
                <div class="score-gauge-wrap">
                    <svg class="score-gauge" viewBox="0 0 36 36">
                        <circle class="bg" cx="18" cy="18" r="${gaugeRadius}"/>
                        <circle class="fill" cx="18" cy="18" r="${gaugeRadius}"
                            stroke="${gaugeColor}"
                            stroke-dasharray="${gaugeCirc}"
                            stroke-dashoffset="${strokeOffset}"/>
                    </svg>
                    <span class="score-badge ${scoreClass}">${scoreNum}</span>
                </div>` : `<span class="score-badge">—</span>`;

            const currentStatus = p.estado_comercial || p["Estado comercial"] || "investigado";
            const statusMap = {
                "investigado": "Investigado",
                "auditado": "Auditado",
                "contactado": "Contactado",
                "interesado": "Interesado",
                "no_interesa": "No Interesa",
                "propuesta": "Propuesta",
                "ganado": "Venta Ganada"
            };

            const favKey = String(p.id);
            const isFav = favorites.includes(favKey) || favorites.includes(webUrl);

            tr.innerHTML = `
                <td><strong>${escapeHtml(p.nombre || p["Nombre del negocio"])}</strong></td>
                <td>${webHtml}</td>
                <td>${canalBadge}</td>
                <td>${servHtml}</td>
                <td>${scoreGauge}</td>
                <td>
                    <select class="status-select status-change-trigger" data-id="${p.id}">
                        ${Object.keys(statusMap).map(k => `
                            <option value="${k}" ${k === currentStatus ? "selected" : ""}>${statusMap[k]}</option>
                        `).join("")}
                    </select>
                </td>
                <td>
                    <button class="status-select btn-audit-trigger" data-id="${p.id}" style="font-weight: 600;">
                        Ver Ficha
                    </button>
                </td>
                <td>
                    <button class="btn-favorite btn-fav-trigger ${isFav ? 'is-fav' : ''}" data-id="${p.id}">
                        <i class="fa-${isFav ? 'solid' : 'regular'} fa-star"></i>
                    </button>
                </td>
            `;

            // Row click listener
            tr.addEventListener("click", (e) => {
                if (e.target.closest("a") || e.target.closest("select") || e.target.closest("button")) return;
                selectProspect(p.id);
            });

            // Status select listener
            const selectEl = tr.querySelector(".status-change-trigger");
            if (selectEl) {
                selectEl.addEventListener("change", (e) => {
                    e.stopPropagation();
                    changeProspectStatus(p.id, selectEl.value);
                });
            }

            // Audit button listener
            const auditBtn = tr.querySelector(".btn-audit-trigger");
            if (auditBtn) {
                auditBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    auditProspect(p.id, auditBtn);
                });
            }

            // Fav button listener
            const favBtn = tr.querySelector(".btn-fav-trigger");
            if (favBtn) {
                favBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    toggleFavorite(favBtn, p.id);
                });
            }

            tableBody.appendChild(tr);
        });
    }

    function renderEmptyState() {
        tableBody.innerHTML = `
            <tr class="placeholder-row">
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-icon-wrap"><i class="fa-solid fa-dog"></i></div>
                        <h3>Comienza tu prospección en Oaxaca</h3>
                        <p>Busca negocios locales en el panel lateral o importa un archivo Excel previo.</p>
                    </div>
                </td>
            </tr>
        `;
    }

    function getScoreColorClass(score) {
        if (!score) return "text-muted";
        if (score >= 85) return "badge-critical score-badge";
        if (score >= 65) return "badge-high score-badge";
        if (score >= 45) return "badge-medium score-badge";
        return "badge-low score-badge";
    }

    function getPriorityBadgeClass(priority) {
        if (!priority) return "badge-medium";
        const p = priority.toLowerCase();
        if (p.includes("crit") || p === "critical") return "badge-critical";
        if (p.includes("alt") || p === "high") return "badge-high";
        if (p.includes("baj") || p === "low") return "badge-low";
        return "badge-medium";
    }

    function toggleFavorite(btn, id) {
        const strId = String(id);
        const idx = favorites.indexOf(strId);
        if (idx === -1) {
            favorites.push(strId);
            btn.classList.add("is-fav");
            btn.innerHTML = `<i class="fa-solid fa-star"></i>`;
        } else {
            favorites.splice(idx, 1);
            btn.classList.remove("is-fav");
            btn.innerHTML = `<i class="fa-regular fa-star"></i>`;
        }
        localStorage.setItem("sabueso_favorites", JSON.stringify(favorites));
    }

    // ========================================
    // Audit Single Prospect
    // ========================================
    async function auditProspect(id, btn) {
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
        }
        if (progressLogger) progressLogger.classList.remove("hidden");
        if (loggerText) loggerText.textContent = "Auditando sitio y redactando con Copiloto CÍDIKS...";

        try {
            const res = await fetch("/api/audit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id, category: currentCategory, location: currentLocation })
            });

            if (!res.ok) throw new Error("Fallo en la auditoría");
            const updated = await res.json();
            
            // Update in local state
            const pIdx = prospects.findIndex(p => p.id === id);
            if (pIdx !== -1) prospects[pIdx] = updated;

            renderTable();
            updateMetrics();
            updatePipelineSteps();

            if (selectedProspectId === id) selectProspect(id);
            showToast("success", "Auditoría completada", `${updated.nombre} calificado con ${updated.puntuacion || 0}/100.`);
        } catch (err) {
            showToast("error", "Error en auditoría", err.message);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = "Re-auditar";
            }
            if (progressLogger) progressLogger.classList.add("hidden");
        }
    }

    // ========================================
    // Status Change
    // ========================================
    async function changeProspectStatus(id, newStatus) {
        const p = prospects.find(x => x.id === id);
        if (newStatus === "contactado" && p && isProspectBlocked(p, p.mensaje_personalizado)) {
            showToast("warning", "Acción bloqueada", "No es posible marcar como contactado un prospecto bloqueado (NO CONTACTAR o INVESTIGAR MÁS) desde el flujo de prospección.");
            renderTable();
            return;
        }

        try {
            const res = await fetch("/api/prospects/update", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id, estado_comercial: newStatus })
            });
            if (!res.ok) throw new Error("No se pudo actualizar el estado");
            
            const pIdx = prospects.findIndex(p => p.id === id);
            if (pIdx !== -1) prospects[pIdx].estado_comercial = newStatus;

            renderTable();
            updateMetrics();
            updatePipelineSteps();
            showToast("success", "Estado actualizado", `Nuevo estado: ${newStatus}`);
        } catch (err) {
            showToast("error", "Error", err.message);
        }
    }

    // ========================================
    // Select Prospect & Open Panel
    // ========================================
    async function selectProspect(id) {
        selectedProspectId = id;
        document.querySelectorAll("#prospects-table tbody tr").forEach(tr => tr.classList.remove("selected"));
        const row = document.querySelector(`#prospects-table tbody tr[data-id="${id}"]`);
        if (row) row.classList.add("selected");

        try {
            const res = await fetch(`/api/prospects/${id}`);
            if (!res.ok) throw new Error("No se pudo cargar el prospecto");
            const p = await res.json();

            editId.value = p.id;
            editName.value = p.nombre || "";
            editWeb.value = p.web || "";
            editPhone.value = p.telefono || "";
            editWhatsapp.value = p.whatsapp || "";
            editEmail.value = p.email || "";
            editSocials.value = p.redes_sociales || "";
            editScore.value = p.puntuacion || 0;
            editPriority.value = p.prioridad || "medium";
            editStatus.value = p.estado_comercial || "investigado";
            editIssues.value = p.observacion_verificada || p.problemas_detectados || "";
            if (editHipotesis) editHipotesis.value = p.hipotesis_comercial || "";
            if (editPregunta) editPregunta.value = p.pregunta_comercial || "";
            if (editMsgApproved) editMsgApproved.checked = Boolean(p.mensaje_aprobado);
            if (editRespuesta) editRespuesta.value = p.respuesta || "";
            if (editNecesidad) editNecesidad.value = p.necesidad_expresada || "";
            if (editPropuestaEnviada) editPropuestaEnviada.checked = Boolean(p.propuesta_enviada);
            if (editVentaAcordada) editVentaAcordada.checked = Boolean(p.venta_acordada);
            if (editVentaMonto) editVentaMonto.value = p.venta_monto || 0;
            if (editIngresoCobrado) editIngresoCobrado.value = p.ingreso_cobrado || 0;

            // WhatsApp Provenance & Capability CÍDIKS
            if (detailWaBadge) {
                const st = p.whatsapp_estado || "";
                if (st === "WHATSAPP_COMPROBADO" || st === "confirmado" || (p.whatsapp && st !== "SIN_WHATSAPP_COMPROBABLE")) {
                    detailWaBadge.textContent = "WHATSAPP_COMPROBADO";
                    detailWaBadge.className = "badge badge-high";
                } else if (st === "WHATSAPP_PENDIENTE_VERIFICACION" || st === "declarado") {
                    detailWaBadge.textContent = "WHATSAPP_PENDIENTE_VERIFICACION";
                    detailWaBadge.className = "badge badge-medium";
                } else {
                    detailWaBadge.textContent = "SIN_WHATSAPP_COMPROBABLE";
                    detailWaBadge.className = "badge badge-low";
                }
            }
            if (detailWaFuente) {
                detailWaFuente.textContent = p.fuente_whatsapp || (p.contacto_url_origen ? 'URL: ' + truncateUrl(p.contacto_url_origen) : 'No rastreado');
            }
            if (editServicioSugerido) {
                editServicioSugerido.value = p.servicio_sugerido || "catalogos";
            }

            // Message tab
            selectMsgTab(activeTab, p);

            // Evidence
            renderEvidenceInPanel(p);

            // Outreach links
            updateOutreachLinks(p);

            detailPanel.classList.remove("hidden");
            if (panelClose) panelClose.focus();
        } catch (err) {
            showToast("error", "Error", err.message);
        }
    }

    function renderEvidenceInPanel(p) {
        if (!screenshotContainer || !evidenceBadge) return;
        const evidencias = p.evidencias || [];
        const latestEv = evidencias.length > 0 ? evidencias[0] : null;

        if (latestEv && latestEv.captura_path) {
            screenshotContainer.style.display = "block";
            screenshotImg.src = latestEv.captura_path;
            screenshotLink.href = latestEv.captura_path;
            evidenceBadge.textContent = latestEv.estado_comprobacion || "PENDIENTE_REVISION";
            evidenceBadge.className = `badge ${latestEv.estado_comprobacion === 'VERIFICADA_VISIBLE' ? 'badge-high' : 'badge-low'}`;
        } else {
            screenshotContainer.style.display = "none";
            evidenceBadge.textContent = "SIN_EVIDENCIA_VISUAL";
            evidenceBadge.className = "badge";
        }
    }

    // Run Visual Playwright Audit
    if (btnRunVisualAudit) {
        btnRunVisualAudit.addEventListener("click", async () => {
            if (!selectedProspectId) return;
            const textToVerify = verifyTextInput ? verifyTextInput.value.trim() : "";
            
            btnRunVisualAudit.disabled = true;
            btnRunVisualAudit.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Comprobando...';
            showToast("info", "Auditoría visual", "Abriendo navegador headless con Playwright...");

            try {
                const res = await fetch("/api/audit/visual", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id: selectedProspectId, text_to_verify: textToVerify })
                });

                if (!res.ok) throw new Error("Fallo en la comprobación visual");
                const evData = await res.json();

                if (evData.captura_path) {
                    screenshotContainer.style.display = "block";
                    screenshotImg.src = evData.captura_path;
                    screenshotLink.href = evData.captura_path;
                }
                if (evidenceBadge) {
                    evidenceBadge.textContent = evData.estado_comprobacion;
                    evidenceBadge.className = `badge ${evData.estado_comprobacion === 'VERIFICADA_VISIBLE' ? 'badge-high' : 'badge-low'}`;
                }

                showToast(
                    evData.estado_comprobacion === "VERIFICADA_VISIBLE" ? "success" : "warning",
                    `Resultado: ${evData.estado_comprobacion}`,
                    evData.hipotesis_necesidad || "Captura realizada correctamente."
                );

                // Reload prospect detail
                selectProspect(selectedProspectId);
            } catch (err) {
                showToast("error", "Error visual", err.message);
            } finally {
                btnRunVisualAudit.disabled = false;
                btnRunVisualAudit.innerHTML = '<i class="fa-solid fa-eye"></i> Comprobar';
            }
        });
    }

    // Message Tab Toggle
    window.selectMsgTab = (type, customProspect) => {
        activeTab = type;
        const p = customProspect || prospects.find(x => x.id === selectedProspectId);
        if (!p) return;

        document.querySelectorAll(".msg-tab").forEach(tab => tab.classList.remove("active"));
        const tabEl = document.getElementById(`tab-${type}`);
        if (tabEl) tabEl.classList.add("active");

        if (type === "frio") {
            editMessage.value = p.mensaje_personalizado || p["Mensaje personalizado"] || "";
        } else if (type === "calido") {
            editMessage.value = p.mensaje_calido || p["Mensaje calido"] || "";
        } else if (type === "seg") {
            editMessage.value = p.mensaje_seguimiento || p["Mensaje seguimiento"] || "";
        }

        updateOutreachLinks(p);
    };

    function isProspectBlocked(p, msgText) {
        if (!p) return false;
        if (p.identidad_verificada === 0 || p.identidad_verificada === false) return true;
        if (p.servicio_sugerido === "no_contactar" || p.servicio_sugerido === "investigar_mas") return true;
        const m = (msgText || "").trim();
        if (m.startsWith("[BLOQUEADO") || m.startsWith("[RECOMENDACIÓN")) return true;
        return false;
    }

    function updateOutreachLinks(p) {
        const msg = editMessage ? editMessage.value : "";
        const blocked = isProspectBlocked(p, msg);
        const phone = p.whatsapp || p.telefono || "";
        const cleanPhone = phone.replace(/\D/g, "");

        if (outreachBlockedWarning) {
            outreachBlockedWarning.style.display = blocked ? "block" : "none";
        }
        if (btnCopyMsg) {
            btnCopyMsg.disabled = blocked;
            btnCopyMsg.style.opacity = blocked ? "0.4" : "1";
        }

        if (linkWa) {
            if (cleanPhone && !blocked) {
                const waDigits = cleanPhone.length === 10 ? "52" + cleanPhone : cleanPhone;
                linkWa.href = `https://wa.me/${waDigits}?text=${encodeURIComponent(msg)}`;
                linkWa.style.pointerEvents = "auto";
                linkWa.style.opacity = "1";
            } else {
                linkWa.href = "#";
                linkWa.style.pointerEvents = "none";
                linkWa.style.opacity = "0.4";
            }
        }

        if (linkMail) {
            const email = (p.email || "").split(",")[0].trim();
            if (email && email.includes("@") && !blocked) {
                linkMail.href = `mailto:${encodeURIComponent(email)}?subject=Atención%20digital%20para%20su%20negocio&body=${encodeURIComponent(msg)}`;
                linkMail.style.pointerEvents = "auto";
                linkMail.style.opacity = "1";
            } else {
                linkMail.href = "#";
                linkMail.style.pointerEvents = "none";
                linkMail.style.opacity = "0.4";
            }
        }

        if (btnConfirmContactModal) {
            btnConfirmContactModal.disabled = blocked;
            btnConfirmContactModal.style.opacity = blocked ? "0.4" : "1";
            btnConfirmContactModal.title = blocked 
                ? "No es posible registrar nuevo contacto: prospecto bloqueado o pendiente de investigación." 
                : "Registrar contacto humano realizado";
        }
    }

    // Copy message to clipboard (Rule: NEVER auto-mark as sent!)
    if (btnCopyMsg) {
        btnCopyMsg.addEventListener("click", () => {
            const msg = editMessage ? editMessage.value : "";
            const p = prospects.find(x => x.id === selectedProspectId);
            if (isProspectBlocked(p, msg)) {
                showToast("error", "Envío bloqueado", "Verifica primero la identidad comercial o elige un enfoque válido antes de copiar.");
                return;
            }
            if (!msg) {
                showToast("warning", "Sin mensaje", "No hay mensaje para copiar.");
                return;
            }
            navigator.clipboard.writeText(msg).then(() => {
                btnCopyMsg.innerHTML = '<i class="fa-solid fa-check"></i> ¡Copiado!';
                showToast("info", "Mensaje copiado", "Pégalo en WhatsApp o Correo. Recuerda confirmar el contacto tras enviarlo.");
                setTimeout(() => {
                    btnCopyMsg.innerHTML = '<i class="fa-solid fa-copy"></i> Copiar Mensaje';
                }, 2000);
            });
        });
    }

    // Human Contact Confirmation Modal
    if (btnConfirmContactModal) {
        btnConfirmContactModal.addEventListener("click", () => {
            if (!selectedProspectId) return;
            const p = prospects.find(x => x.id === selectedProspectId);
            const msg = editMessage ? editMessage.value : "";
            if (isProspectBlocked(p, msg)) {
                showToast("error", "Acción bloqueada", "No es posible iniciar contacto con un prospecto bloqueado o pendiente de investigación.");
                return;
            }
            if (contactDate) {
                const now = new Date();
                const tzOffset = now.getTimezoneOffset() * 60000;
                contactDate.value = new Date(now - tzOffset).toISOString().slice(0, 16);
            }
            contactModal.classList.remove("hidden");
        });
    }
    if (contactModalClose) {
        contactModalClose.addEventListener("click", () => contactModal.classList.add("hidden"));
    }
    if (contactConfirmForm) {
        contactConfirmForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            if (!selectedProspectId) return;

            const canal = contactChannel ? contactChannel.value : "manual";
            const notas = contactNotes ? contactNotes.value.trim() : "";
            const fecha_contacto = contactDate ? contactDate.value : "";

            try {
                const res = await fetch("/api/prospects/contact-confirm", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id: selectedProspectId, canal, notas, fecha_contacto })
                });

                if (!res.ok) throw new Error("No se pudo registrar el contacto");
                contactModal.classList.add("hidden");
                contactNotes.value = "";
                
                showToast("success", "Contacto registrado", "El contacto humano ha sido confirmado en el CRM.");
                loadProspects();
                selectProspect(selectedProspectId);
            } catch (err) {
                showToast("error", "Error", err.message);
            }
        });
    }

    // Save Edit Form
    async function saveCurrentDetailForm(silent = false) {
        if (!selectedProspectId) return;

        const updatedData = {
            id: selectedProspectId,
            nombre: editName.value.trim(),
            web: editWeb.value.trim(),
            telefono: editPhone.value.trim(),
            whatsapp: editWhatsapp.value.trim(),
            email: editEmail.value.trim(),
            redes_sociales: editSocials.value.trim(),
            puntuacion: parseInt(editScore.value) || 0,
            prioridad: editPriority.value,
            estado_comercial: editStatus.value,
            problemas_detectados: editIssues.value.trim(),
            observacion_verificada: editIssues.value.trim(),
            hipotesis_comercial: editHipotesis ? editHipotesis.value.trim() : "",
            pregunta_comercial: editPregunta ? editPregunta.value.trim() : "",
            servicio_sugerido: editServicioSugerido ? editServicioSugerido.value : "catalogos",
            mensaje_aprobado: editMsgApproved && editMsgApproved.checked ? 1 : 0,
            respuesta: editRespuesta ? editRespuesta.value.trim() : "",
            necesidad_expresada: editNecesidad ? editNecesidad.value.trim() : "",
            propuesta_enviada: editPropuestaEnviada && editPropuestaEnviada.checked ? 1 : 0,
            venta_acordada: editVentaAcordada && editVentaAcordada.checked ? 1 : 0,
            venta_monto: editVentaMonto ? parseFloat(editVentaMonto.value) || 0.0 : 0.0,
            ingreso_cobrado: editIngresoCobrado ? parseFloat(editIngresoCobrado.value) || 0.0 : 0.0
        };

        if (activeTab === "frio") updatedData.mensaje_personalizado = editMessage.value.trim();
        else if (activeTab === "calido") updatedData.mensaje_calido = editMessage.value.trim();
        else if (activeTab === "seg") updatedData.mensaje_seguimiento = editMessage.value.trim();

        try {
            const res = await fetch("/api/prospects/update", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updatedData)
            });

            if (!res.ok) throw new Error("Error al guardar cambios");
            if (!silent) {
                showToast("success", "Guardado", "Ficha comercial actualizada correctamente.");
            }
            await loadProspects();
        } catch (err) {
            if (!silent) {
                showToast("error", "Error", err.message);
            }
        }
    }

    if (btnSaveEdit) {
        btnSaveEdit.addEventListener("click", () => saveCurrentDetailForm(false));
    }

    if (btnRegenMsg) {
        btnRegenMsg.addEventListener("click", async () => {
            if (!selectedProspectId) return;
            const servicio = editServicioSugerido ? editServicioSugerido.value : "catalogos";
            btnRegenMsg.disabled = true;
            btnRegenMsg.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';

            try {
                const res = await fetch("/api/copilot/regenerate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id: selectedProspectId, servicio_sugerido: servicio })
                });
                if (!res.ok) throw new Error("No se pudo regenerar el borrador");
                const data = await res.json();
                const p = data.prospect;

                // Update in local state
                const idx = prospects.findIndex(x => x.id === selectedProspectId);
                if (idx !== -1) prospects[idx] = p;

                if (editIssues) editIssues.value = p.observacion_verificada || p.problemas_detectados || "";
                if (editHipotesis) editHipotesis.value = p.hipotesis_comercial || "";
                if (editPregunta) editPregunta.value = p.pregunta_comercial || "";
                if (editServicioSugerido) editServicioSugerido.value = p.servicio_sugerido || servicio;

                selectMsgTab(activeTab, p);
                renderTable();
                showToast("success", "Borrador actualizado", `Orientado hacia: ${servicio}`);
            } catch (err) {
                showToast("error", "Error", err.message);
            } finally {
                btnRegenMsg.disabled = false;
                btnRegenMsg.innerHTML = '<i class="fa-solid fa-rotate"></i> Regenerar';
            }
        });
    }

    function closeDetailPanel() {
        if (!detailPanel || detailPanel.classList.contains("hidden")) return;
        detailPanel.classList.add("hidden");
        document.querySelectorAll("#prospects-table tbody tr").forEach(tr => tr.classList.remove("selected"));
        selectedProspectId = null;
    }

    // Close Panel via Button or Escape Key
    if (panelClose) {
        panelClose.addEventListener("click", () => closeDetailPanel());
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            if (detailPanel && !detailPanel.classList.contains("hidden")) {
                closeDetailPanel();
            }
            [contactModal, importModal, duplicatesModal, apiModal, quarantineModal].forEach(m => {
                if (m && !m.classList.contains("hidden")) m.classList.add("hidden");
            });
        }
    });

    // ========================================
    // Quarantine Modal & Restoration Handlers
    // ========================================
    async function loadQuarantineModal() {
        if (!quarantineListContainer) return;
        quarantineListContainer.innerHTML = '<div style="text-align:center; padding:20px;"><i class="fa-solid fa-circle-notch fa-spin"></i> Consultando registros en cuarentena...</div>';
        try {
            const [resQ, resA] = await Promise.all([
                fetch("/api/quarantine"),
                fetch("/api/audit-log")
            ]);
            const dataQ = await resQ.json();
            const dataA = await resA.json();
            const regs = dataQ.registros || [];
            const logs = (dataA.cambios || []).filter(c => c.operacion === "SANEAMIENTO_CONTACTO" && !c.revertido);

            let html = "";
            if (regs.length === 0) {
                html += '<div style="text-align:center; padding:14px; color: var(--success);"><i class="fa-solid fa-circle-check"></i> No hay registros en cuarentena actualmente.</div>';
            } else {
                html += `<div style="margin-bottom: 10px; display:flex; justify-content:space-between; align-items:center;">
                    <strong>${regs.length} registro(s) en cuarentena lógica</strong>
                </div>`;
                regs.forEach(r => {
                    html += `
                        <div style="background: rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); padding:10px 12px; border-radius:6px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
                            <div>
                                <div style="font-weight:600;">#${r.id} — ${escapeHtml(r.nombre)} <span class="badge badge-low">${escapeHtml(r.estado_comercial)}</span></div>
                                <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">Motivo: ${escapeHtml(r.motivo_cuarentena || "Artefacto de prueba")}</div>
                            </div>
                            <button type="button" class="btn btn-secondary btn-restore-quarantine" data-id="${r.id}" style="padding:6px 10px; font-size:11px;">
                                <i class="fa-solid fa-rotate-left"></i> Restaurar
                            </button>
                        </div>
                    `;
                });
            }

            if (logs.length > 0) {
                html += `<hr class="panel-divider"><div style="margin: 8px 0;"><strong>Bitácora de Contactos Saneados (${logs.length})</strong></div>`;
                logs.forEach(l => {
                    html += `
                        <div style="background: rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); padding:10px 12px; border-radius:6px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
                            <div>
                                <div style="font-weight:600;">Auditoría #${l.id} (Negocio ID ${l.negocio_id})</div>
                                <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">Anterior: <code>${escapeHtml(l.valores_anteriores_json)}</code></div>
                            </div>
                            <button type="button" class="btn btn-secondary btn-restore-audit" data-audit-id="${l.id}" style="padding:6px 10px; font-size:11px;">
                                <i class="fa-solid fa-rotate-left"></i> Revertir Cambio
                            </button>
                        </div>
                    `;
                });
            }

            quarantineListContainer.innerHTML = html;

            quarantineListContainer.querySelectorAll(".btn-restore-quarantine").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const id = parseInt(btn.dataset.id);
                    const res = await fetch("/api/quarantine/restore", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ ids: [id] })
                    });
                    if (res.ok) {
                        showToast("success", "Restaurado", `Negocio #${id} restaurado de cuarentena.`);
                        await loadProspects();
                        await loadQuarantineModal();
                    }
                });
            });

            quarantineListContainer.querySelectorAll(".btn-restore-audit").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const auditId = parseInt(btn.dataset.auditId);
                    const res = await fetch("/api/audit-log/restore", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ audit_id: auditId })
                    });
                    if (res.ok) {
                        showToast("success", "Revertido", `Cambio de auditoría #${auditId} revertido.`);
                        await loadProspects();
                        await loadQuarantineModal();
                    }
                });
            });
        } catch (err) {
            quarantineListContainer.innerHTML = `<div style="color:var(--danger);">${escapeHtml(err.message)}</div>`;
        }
    }

    if (btnQuarantineOpen) {
        btnQuarantineOpen.addEventListener("click", () => {
            if (quarantineModal) quarantineModal.classList.remove("hidden");
            loadQuarantineModal();
        });
    }
    if (quarantineModalClose) {
        quarantineModalClose.addEventListener("click", () => quarantineModal.classList.add("hidden"));
    }

    // ========================================
    // Pipeline Flow Management
    // ========================================
    function updatePipelineSteps() {
        if (!stepBuscar) return;
        const total = prospects.length;
        const auditedCount = prospects.filter(p => p.puntuacion && p.puntuacion > 0).length;
        const proposalCount = prospects.filter(p => p.estado_comercial === "propuesta" || p.propuesta_enviada == 1).length;
        const contactedCount = prospects.filter(p => p.estado_comercial === "contactado" || p.fecha_contacto_confirmada).length;

        document.getElementById("step-count-buscar").textContent = total > 0 ? total : "—";
        document.getElementById("step-count-auditar").textContent = auditedCount > 0 ? auditedCount : "—";
        document.getElementById("step-count-calificar").textContent = proposalCount > 0 ? proposalCount : "—";
        document.getElementById("step-count-contactar").textContent = contactedCount > 0 ? contactedCount : "—";

        [stepBuscar, stepAuditar, stepCalificar, stepContactar].forEach(s => s.classList.remove("active", "completed"));
        [connector1, connector2, connector3].forEach(c => c.classList.remove("active"));

        if (total === 0) {
            stepBuscar.classList.add("active");
        } else if (auditedCount === 0) {
            stepBuscar.classList.add("completed");
            connector1.classList.add("active");
            stepAuditar.classList.add("active");
        } else if (contactedCount === 0) {
            stepBuscar.classList.add("completed");
            connector1.classList.add("active");
            stepAuditar.classList.add("completed");
            connector2.classList.add("active");
            stepCalificar.classList.add("active");
        } else {
            stepBuscar.classList.add("completed");
            connector1.classList.add("active");
            stepAuditar.classList.add("completed");
            connector2.classList.add("active");
            stepCalificar.classList.add("completed");
            connector3.classList.add("active");
            stepContactar.classList.add("active");
        }
    }

    // ========================================
    // Search Form Submission
    // ========================================
    if (searchForm) {
        searchForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const category = document.getElementById("category").value.trim();
            const location = document.getElementById("location").value.trim();
            const limit = document.getElementById("limit").value;
            const depth = document.getElementById("depth").value;
            const shouldAutoAudit = autoAuditToggle ? autoAuditToggle.checked : false;

            if (!category || !location) {
                showToast("warning", "Requerido", "Ingresa categoría y ubicación.");
                return;
            }

            currentCategory = category;
            currentLocation = location;

            btnSearch.disabled = true;
            btnSearch.querySelector(".btn-text").innerHTML = `<i class="fa-solid fa-magnifying-glass"></i> Investigando...`;
            btnSearch.querySelector(".loading-spinner").classList.remove("hidden");

            const iosProgress = startIosProgress();

            try {
                const res = await fetch("/api/search", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ category, location, limit, depth })
                });

                if (iosProgress) clearInterval(iosProgress);
                finishIosProgress();

                if (!res.ok) throw new Error("Fallo en la búsqueda.");
                const data = await res.json();
                
                showToast("success", `${(data.prospects || []).length} encontrados`, "Prospectos guardados en base local SQLite.");
                await loadProspects();

                if (shouldAutoAudit && data.prospects && data.prospects.length > 0) {
                    for (const p of data.prospects) {
                        await auditProspect(p.id, null);
                    }
                }
            } catch (err) {
                showToast("error", "Error", err.message);
            } finally {
                btnSearch.disabled = false;
                btnSearch.querySelector(".btn-text").innerHTML = `<i class="fa-solid fa-magnifying-glass"></i> Investigar Prospectos`;
                btnSearch.querySelector(".loading-spinner").classList.add("hidden");
            }
        });
    }

    // ========================================
    // Import Modal & Handlers
    // ========================================
    if (btnImportOpen) {
        btnImportOpen.addEventListener("click", () => importModal.classList.remove("hidden"));
    }
    if (importModalClose) {
        importModalClose.addEventListener("click", () => importModal.classList.add("hidden"));
    }
    if (btnImportPreviewAction) {
        btnImportPreviewAction.addEventListener("click", async () => {
            const filepath = importFilePath.value.trim();
            if (!filepath) return;

            btnImportPreviewAction.disabled = true;
            btnImportPreviewAction.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Leyendo...';

            try {
                const res = await fetch("/api/import/preview", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ filepath })
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.error || "No se pudo leer el archivo");
                }

                const prev = await res.json();
                importPreviewResults.style.display = "block";
                importSummaryText.textContent = `Archivo: ${prev.archivo} | Total filas: ${prev.total_filas} | Posibles duplicados: ${prev.posibles_duplicados}`;

                // Render small preview table
                let tbl = `<table style="width:100%; font-size:11px; border-collapse:collapse;"><thead><tr>`;
                prev.columnas_originales.forEach(c => tbl += `<th style="border:1px solid #444; padding:4px;">${escapeHtml(c)}</th>`);
                tbl += `</tr></thead><tbody>`;
                prev.filas_muestra.forEach(r => {
                    tbl += `<tr>`;
                    prev.columnas_originales.forEach(c => tbl += `<td style="border:1px solid #333; padding:4px;">${escapeHtml(r[c])}</td>`);
                    tbl += `</tr>`;
                });
                tbl += `</tbody></table>`;
                importPreviewTableWrap.innerHTML = tbl;
            } catch (err) {
                showToast("error", "Error de lectura", err.message);
            } finally {
                btnImportPreviewAction.disabled = false;
                btnImportPreviewAction.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Ver Vista Previa de Columnas';
            }
        });
    }

    if (btnImportExecuteAction) {
        btnImportExecuteAction.addEventListener("click", async () => {
            const filepath = importFilePath.value.trim();
            if (!filepath) return;

            btnImportExecuteAction.disabled = true;
            btnImportExecuteAction.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Importando...';

            try {
                const res = await fetch("/api/import/execute", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ filepath })
                });

                if (!res.ok) throw new Error("Fallo en la importación");
                const result = await res.json();
                
                showToast("success", "Importación completada", `${result.importados} registros importados. Lote: ${result.batch_id}`);
                importModal.classList.add("hidden");
                importPreviewResults.style.display = "none";
                loadProspects();
            } catch (err) {
                showToast("error", "Error al importar", err.message);
            } finally {
                btnImportExecuteAction.disabled = false;
                btnImportExecuteAction.innerHTML = '<i class="fa-solid fa-file-arrow-up"></i> Confirmar e Importar a Base Local';
            }
        });
    }

    // ========================================
    // Duplicates Modal & Handlers
    // ========================================
    if (btnDuplicatesOpen) {
        btnDuplicatesOpen.addEventListener("click", async () => {
            duplicatesModal.classList.remove("hidden");
            duplicatesListContainer.innerHTML = '<div style="text-align:center; padding:20px;"><i class="fa-solid fa-circle-notch fa-spin"></i> Analizando duplicados...</div>';

            try {
                const res = await fetch("/api/duplicates");
                if (!res.ok) throw new Error("Error obteniendo duplicados");
                const dups = await res.json();

                if (dups.length === 0) {
                    duplicatesListContainer.innerHTML = '<div style="text-align:center; padding:20px; color: var(--success);"><i class="fa-solid fa-circle-check"></i> No se detectaron duplicados en la base de datos.</div>';
                    return;
                }

                let html = "";
                dups.forEach(d => {
                    html += `
                        <div style="background: rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); padding:10px; border-radius:6px; margin-bottom:8px;">
                            <div style="display:flex; justify-content:space-between; font-weight:600;">
                                <span>${escapeHtml(d.negocio_a.nombre)} &harr; ${escapeHtml(d.negocio_b.nombre)}</span>
                                <span class="badge badge-high">${Math.round(d.similitud * 100)}% similitud</span>
                            </div>
                            <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                                ${d.motivos.map(m => `<div>&bull; ${escapeHtml(m)}</div>`).join("")}
                            </div>
                        </div>
                    `;
                });
                duplicatesListContainer.innerHTML = html;
            } catch (err) {
                duplicatesListContainer.innerHTML = `<div style="color:var(--danger);">${escapeHtml(err.message)}</div>`;
            }
        });
    }
    if (duplicatesModalClose) {
        duplicatesModalClose.addEventListener("click", () => duplicatesModal.classList.add("hidden"));
    }

    // ========================================
    // Export Handlers
    // ========================================
    if (btnExportCsv) {
        btnExportCsv.addEventListener("click", () => {
            window.location.href = "/api/export?format=csv";
            showToast("info", "Exportando CSV", "Descargando archivo CSV...");
        });
    }
    if (btnExportXlsx) {
        btnExportXlsx.addEventListener("click", () => {
            window.location.href = "/api/export?format=xlsx";
            showToast("info", "Exportando Excel", "Descargando archivo XLSX...");
        });
    }

    // ========================================
    // API Status Check
    // ========================================
    async function updateApiStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();
            if (providerName) providerName.textContent = data.search_engine || "DuckDuckGo Local";
            if (aiProviderName) aiProviderName.textContent = data.gemini_configured ? "Gemini Conectado" : "Reglas determinísticas (Offline)";
            if (providerSearchStatus) providerSearchStatus.innerHTML = '<i class="fa-solid fa-circle-check" style="color: var(--success)"></i>';
            if (providerAiStatus) {
                providerAiStatus.innerHTML = data.gemini_configured 
                    ? '<i class="fa-solid fa-circle-check" style="color: var(--success)"></i>'
                    : '<i class="fa-solid fa-circle-check" style="color: var(--info)"></i>';
            }
        } catch {
            if (providerName) providerName.textContent = "Modo Local Autónomo";
            if (aiProviderName) aiProviderName.textContent = "Reglas determinísticas";
        }
    }

    // API Config Modal
    if (btnConfigApi) {
        btnConfigApi.addEventListener("click", () => apiModal.classList.remove("hidden"));
    }
    if (modalClose) {
        modalClose.addEventListener("click", () => apiModal.classList.add("hidden"));
    }
    if (apiConfigForm) {
        apiConfigForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const gemini = document.getElementById("modal-gemini-key").value.trim();
            const serp = document.getElementById("modal-serpapi-key").value.trim();
            const maps = document.getElementById("modal-maps-key").value.trim();

            const payload = {};
            if (gemini) payload.gemini_api_key = gemini;
            if (serp) payload.serpapi_key = serp;
            if (maps) payload.maps_api_key = maps;

            try {
                const res = await fetch("/api/config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    apiModal.classList.add("hidden");
                    updateApiStatus();
                    showToast("success", "Configuración guardada", "Las claves locales se actualizaron.");
                }
            } catch (err) {
                showToast("error", "Error", err.message);
            }
        });
    }

    // Initial Boots
    loadProspects();
    updateApiStatus();
});
