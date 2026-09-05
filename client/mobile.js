// OpenWorker mobile shell — roster → chat → computer sheet

(function () {
    const params = new URLSearchParams(location.search);
    const forceMobile = params.get("mobile") === "1" || params.get("mobile") === "true";
    const mq = window.matchMedia("(max-width: 768px)");

    function isMobile() {
        return forceMobile || mq.matches;
    }

    function activate() {
        const on = isMobile();
        document.body.classList.toggle("mobile-active", on);
        document.body.classList.toggle("force-mobile", forceMobile);
        const app = document.getElementById("mobile-app");
        if (app) app.setAttribute("aria-hidden", on ? "false" : "true");
        if (!on) {
            closeSheets();
            document.body.dataset.mobileView = "roster";
        }
    }

    function showRoster() {
        document.body.dataset.mobileView = "roster";
        const roster = document.getElementById("m-roster-view");
        const chat = document.getElementById("m-chat-view");
        if (roster) roster.hidden = false;
        if (chat) chat.hidden = true;
        closeSheets();
    }

    function showChat() {
        document.body.dataset.mobileView = "chat";
        const roster = document.getElementById("m-roster-view");
        const chat = document.getElementById("m-chat-view");
        if (roster) roster.hidden = true;
        if (chat) chat.hidden = false;
        const messages = document.getElementById("m-messages");
        if (messages) messages.scrollTop = messages.scrollHeight;
    }

    function openSheet(id) {
        const sheet = document.getElementById(id);
        const backdrop = document.getElementById("m-sheet-backdrop");
        if (backdrop) backdrop.hidden = false;
        if (sheet) sheet.hidden = false;
    }

    function closeSheets() {
        const backdrop = document.getElementById("m-sheet-backdrop");
        if (backdrop) backdrop.hidden = true;
        document.querySelectorAll(".m-sheet").forEach((el) => {
            el.hidden = true;
        });
    }

    async function openComputerSheet() {
        openSheet("m-computer-sheet");
        const w = window.OpenWorkerChat?.getActiveWorker?.();
        const sub = document.getElementById("m-sheet-sub");
        if (sub) {
            sub.textContent = w?.current_action
                ? w.current_action
                : "Glance — or take over when they need you.";
        }
        await window.OpenWorkerChat?.refreshActiveScreen?.();
    }

    function bind() {
        document.getElementById("m-btn-back")?.addEventListener("click", showRoster);
        document.getElementById("m-btn-computer")?.addEventListener("click", openComputerSheet);
        document.getElementById("m-sheet-close")?.addEventListener("click", closeSheets);
        document.getElementById("m-sheet-backdrop")?.addEventListener("click", closeSheets);
        document.getElementById("m-routines-close")?.addEventListener("click", closeSheets);

        const openApiModal = () => {
            if (typeof window.openApiModal === "function") {
                window.openApiModal();
                return;
            }
            const modal = document.getElementById("modal-api");
            if (!modal) return;
            modal.hidden = false;
            modal.classList.add("open");
            const input = document.getElementById("input-api-key");
            if (input) setTimeout(() => input.focus(), 50);
        };
        document.getElementById("m-btn-settings")?.addEventListener("click", openApiModal);
        // Banner lives outside the mobile shell — bind here too so it works even if app.js raced.
        document.getElementById("btn-banner-api-key")?.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            openApiModal();
        });

        document.getElementById("m-btn-add-worker")?.addEventListener("click", () => {
            const modal = document.getElementById("modal-worker");
            if (modal) modal.hidden = false;
        });

        document.getElementById("m-btn-add-group")?.addEventListener("click", () => {
            document.getElementById("btn-add-group")?.click();
        });

        document.getElementById("m-btn-send")?.addEventListener("click", () => {
            window.OpenWorkerChat?.send?.(true);
        });

        const mInput = document.getElementById("m-chat-input");
        mInput?.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                window.OpenWorkerChat?.send?.(true);
            }
        });
        mInput?.addEventListener("input", () => {
            mInput.style.height = "auto";
            mInput.style.height = Math.min(mInput.scrollHeight, 120) + "px";
        });

        document.querySelectorAll("#m-chips .m-chip").forEach((chip) => {
            chip.addEventListener("click", () => {
                const input = document.getElementById("m-chat-input");
                if (input) {
                    input.value = chip.dataset.prompt || chip.textContent;
                    input.focus();
                }
            });
        });

        document.getElementById("m-btn-routines")?.addEventListener("click", () => {
            openSheet("m-routines-sheet");
            window.OpenWorkerChat?.loadRoutines?.();
        });

        document.getElementById("m-btn-new-routine")?.addEventListener("click", () => {
            closeSheets();
            const modal = document.getElementById("modal-routine");
            if (modal) modal.hidden = false;
        });

        document.getElementById("m-btn-sheet-refresh")?.addEventListener("click", () => {
            window.OpenWorkerChat?.refreshActiveScreen?.();
        });

        document.getElementById("m-btn-sheet-takeover")?.addEventListener("click", () => {
            closeSheets();
            window.OpenWorkerChat?.setTakeoverOpen?.(true);
        });

        // After worker create on mobile, jump into chat
        const saveWorker = document.getElementById("btn-save-worker");
        saveWorker?.addEventListener("click", () => {
            setTimeout(() => {
                if (isMobile()) showChat();
            }, 400);
        });
    }

    window.MobileUI = {
        showChat,
        showRoster,
        openComputerSheet,
        closeSheets,
        onWorkers(workers, activeId) {
            // presence already rendered by chat.js
            if (!isMobile()) return;
            if (document.body.dataset.mobileView === "chat" && activeId) {
                // keep chat
            }
        },
        isMobile,
    };

    function init() {
        activate();
        bind();
        if (isMobile()) showRoster();
        mq.addEventListener?.("change", activate);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
