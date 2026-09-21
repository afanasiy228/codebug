(function () {
    "use strict";

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function ensureStyles() {
        if (document.getElementById("compilationDiagnosticsStyles")) return;
        const style = document.createElement("style");
        style.id = "compilationDiagnosticsStyles";
        style.textContent = `
            .ce-verdict-button {
                appearance: none;
                border: 0 !important;
                padding: 0 0 2px;
                background: transparent !important;
                color: #E47B55 !important;
                box-shadow: none !important;
                font: inherit;
                font-weight: inherit;
                line-height: inherit;
                text-decoration: underline;
                text-decoration-color: rgba(228, 123, 85, 0.58);
                text-decoration-thickness: 1px;
                text-underline-offset: 3px;
                cursor: pointer;
            }
            .ce-verdict-button:hover,
            .ce-verdict-button:focus-visible {
                color: #EA8B66 !important;
                text-decoration-color: currentColor;
            }
            .ce-verdict-button:focus-visible {
                outline: 2px solid rgba(228, 123, 85, 0.38);
                outline-offset: 4px;
                border-radius: 2px;
            }
            .compilation-diagnostics-dialog {
                width: min(760px, calc(100vw - 32px));
                max-height: min(680px, calc(100vh - 32px));
                padding: 0;
                border: 1px solid rgba(184, 184, 184, 0.22);
                border-radius: 16px;
                color: #F5F5F5;
                background: rgba(16, 16, 16, 0.98);
                box-shadow: 0 24px 72px rgba(0, 0, 0, 0.55);
            }
            .compilation-diagnostics-dialog::backdrop {
                background: rgba(0, 0, 0, 0.72);
                backdrop-filter: blur(3px);
            }
            .compilation-diagnostics-close {
                position: absolute;
                top: 12px;
                right: 12px;
                width: 28px;
                height: 28px;
                padding: 0;
                border: 0 !important;
                border-radius: 0;
                color: #969696 !important;
                background: transparent !important;
                box-shadow: none !important;
                font: 300 24px/1 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                cursor: pointer;
            }
            .compilation-diagnostics-close:hover,
            .compilation-diagnostics-close:focus-visible { color: #E3E3E3 !important; }
            .compilation-diagnostics-close:focus-visible {
                outline: none;
            }
            .compilation-diagnostics-body { padding: 48px 20px 20px; }
            .compilation-diagnostics-status {
                margin: 0;
                color: #B0B0B0;
                font: 14px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            .compilation-diagnostics-output {
                max-height: min(52vh, 460px);
                margin: 0;
                overflow: auto;
                white-space: pre-wrap;
                overflow-wrap: anywhere;
                color: #E7E7E7;
                font: 13px/1.55 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                user-select: text;
            }
            @media (max-width: 640px) {
                .compilation-diagnostics-body { padding: 44px 16px 16px; }
            }
        `;
        document.head.appendChild(style);
    }

    function ensureUi() {
        ensureStyles();
        let dialog = document.getElementById("compilationDiagnosticsDialog");
        if (dialog) return dialog;

        dialog = document.createElement("dialog");
        dialog.id = "compilationDiagnosticsDialog";
        dialog.className = "compilation-diagnostics-dialog";
        dialog.setAttribute("aria-label", "Подробности ошибки компиляции");
        dialog.innerHTML = `
            <button type="button" class="compilation-diagnostics-close" aria-label="Закрыть">×</button>
            <div class="compilation-diagnostics-body">
                <p class="compilation-diagnostics-status">Загрузка…</p>
                <pre class="compilation-diagnostics-output" hidden></pre>
            </div>
        `;
        dialog.querySelector(".compilation-diagnostics-close").addEventListener("click", () => dialog.close());
        dialog.addEventListener("click", (event) => {
            if (event.target === dialog) dialog.close();
        });
        document.body.appendChild(dialog);
        return dialog;
    }

    async function fetchDiagnostics(submissionId, forceRefresh) {
        const token = typeof window.getFreshAuthToken === "function"
            ? await window.getFreshAuthToken({ forceRefresh: Boolean(forceRefresh) })
            : null;
        if (!token) throw new Error("AUTH_REQUIRED");
        const base = window.getTasksApiBase
            ? window.getTasksApiBase()
            : (window.TASKS_API_BASE || "https://codebug.onrender.com");
        return fetch(`${base}/submissions/${encodeURIComponent(submissionId)}/diagnostics`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store"
        });
    }

    async function openCompilationDiagnostics(submissionId) {
        const safeId = String(submissionId || "").trim();
        if (!/^[-A-Za-z0-9_]{1,128}$/.test(safeId)) return;

        const dialog = ensureUi();
        const status = dialog.querySelector(".compilation-diagnostics-status");
        const output = dialog.querySelector(".compilation-diagnostics-output");
        status.hidden = false;
        status.textContent = "Загрузка…";
        output.hidden = true;
        output.textContent = "";
        if (!dialog.open) dialog.showModal();

        try {
            let response = await fetchDiagnostics(safeId, false);
            if (response.status === 401) response = await fetchDiagnostics(safeId, true);
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                const messages = {
                    401: "Войди в аккаунт, чтобы посмотреть ошибку компиляции.",
                    403: "Подробности доступны только автору посылки и администраторам.",
                    404: "Для этой посылки подробности не сохранились. Они доступны для новых CE.",
                    429: "Слишком много запросов. Попробуй немного позже."
                };
                throw new Error(messages[response.status] || payload.error || "Не удалось загрузить подробности.");
            }
            status.hidden = true;
            output.hidden = false;
            output.textContent = String(payload.details || "Компилятор не предоставил описание ошибки.");
        } catch (error) {
            status.hidden = false;
            status.textContent = error instanceof TypeError
                ? "Нет связи с сервером. Попробуй ещё раз."
                : String(error && error.message || "Не удалось загрузить подробности.");
        }
    }

    function compilationVerdictHtml(label, submissionId) {
        const text = String(label || "CE");
        const id = String(submissionId || "");
        if (text.toUpperCase() !== "CE" || !/^[-A-Za-z0-9_]{1,128}$/.test(id)) {
            return escapeHtml(text);
        }
        return `<button type="button" class="ce-verdict-button" data-submission-id="${escapeHtml(id)}" title="Показать ошибку компиляции">${escapeHtml(text)}</button>`;
    }

    ensureStyles();

    document.addEventListener("click", (event) => {
        const button = event.target.closest && event.target.closest(".ce-verdict-button");
        if (!button) return;
        openCompilationDiagnostics(button.dataset.submissionId);
    });

    window.compilationVerdictHtml = compilationVerdictHtml;
    window.openCompilationDiagnostics = openCompilationDiagnostics;
})();
