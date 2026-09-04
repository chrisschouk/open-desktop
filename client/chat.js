// OpenWorker Chat — Worker roster, presence, computer levels, heterogeneous transcript
// API_BASE / WS_BASE provided by app.js

let chatSessionId = null;
let chatPollInterval = null;
let chatIsWorking = false;
let activeWorkerId = null;
let workersCache = [];
let previewOpen = false;
let takeoverOpen = false;
let chatActionWs = null;
let rosterPoll = null;

const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("btn-chat-send");
const chatLiveImg = document.getElementById("chat-live-screen");
const chatStatusBadge = document.getElementById("chat-status-badge");
const rosterList = document.getElementById("roster-list");
const computerPreview = document.getElementById("computer-preview");
const computerStatusChip = document.getElementById("computer-status-chip");
const takeoverOverlay = document.getElementById("takeover-overlay");
const takeoverImg = document.getElementById("takeover-screen-img");

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function apiBase() {
    return window.API_BASE || "http://localhost:8000/api/v1";
}

function wsBase() {
    return window.WS_BASE || "ws://localhost:8000/ws";
}

function renderMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    html = html.replace(/\n/g, "<br>");
    return html;
}

function setChatWorking(working) {
    chatIsWorking = working;
    if (chatSendBtn) {
        chatSendBtn.disabled = working;
        chatSendBtn.textContent = working ? "Working…" : "Send";
    }
    if (chatInput) chatInput.disabled = working;
}

function avatarInitial(name) {
    return (name || "W").trim().charAt(0).toUpperCase();
}

function renderAvatarEl(el, worker) {
    if (!el) return;
    const presence = worker.presence || "idle";
    const avatar = worker.avatar || "default";
    el.dataset.presence = presence;
    el.dataset.avatar = avatar;
    el.title = worker.current_action
        ? `${worker.name}: ${worker.current_action}`
        : `${worker.name} · ${presence}`;
    const face = el.querySelector(".avatar-face");
    if (face) face.textContent = avatarInitial(worker.name);
}

function renderRoster() {
    if (!rosterList) return;
    rosterList.innerHTML = "";
    workersCache.forEach((w) => {
        const li = document.createElement("li");
        li.className = "roster-item" + (w.id === activeWorkerId ? " active" : "");
        li.dataset.workerId = w.id;

        const av = document.createElement("div");
        av.className = "worker-avatar roster-avatar";
        av.innerHTML = '<span class="avatar-face"></span><span class="presence-ring"></span>';
        renderAvatarEl(av, w);

        const meta = document.createElement("div");
        meta.className = "roster-meta";
        meta.innerHTML = `
            <span class="roster-name">${escapeHtml(w.name)}</span>
            <span class="roster-presence">${escapeHtml(w.presence || "idle")}</span>
            ${w.current_action ? `<span class="roster-action">${escapeHtml(w.current_action)}</span>` : ""}
        `;

        li.appendChild(av);
        li.appendChild(meta);
        li.addEventListener("click", () => selectWorker(w.id));
        li.addEventListener("mouseenter", () => {
            if (w.current_action) av.title = w.current_action;
        });
        rosterList.appendChild(li);
    });
}

async function loadWorkers() {
    try {
        const res = await fetch(`${apiBase()}/workers`);
        const data = await res.json();
        workersCache = data.workers || [];
        if (!activeWorkerId && workersCache.length) {
            activeWorkerId = workersCache[0].id;
        }
        renderRoster();
        const active = workersCache.find((w) => w.id === activeWorkerId);
        if (active) updateWorkerHeader(active);
        return workersCache;
    } catch (e) {
        console.error("loadWorkers failed", e);
        return [];
    }
}

function updateWorkerHeader(worker) {
    const nameEl = document.getElementById("active-worker-name");
    const roleEl = document.getElementById("active-worker-role");
    const av = document.getElementById("active-worker-avatar");
    if (nameEl) nameEl.textContent = worker.name;
    if (roleEl) roleEl.textContent = worker.role || "";
    renderAvatarEl(av, worker);
    const computerActive = ["working", "waiting"].includes(worker.presence) || !!worker.preferred_machine_id;
    if (computerStatusChip) {
        computerStatusChip.dataset.active = computerActive ? "true" : "false";
    }
}

async function selectWorker(workerId) {
    if (activeWorkerId === workerId && chatSessionId) {
        await loadWorkers();
        return;
    }
    activeWorkerId = workerId;
    chatSessionId = null;
    if (chatMessages) chatMessages.innerHTML = "";
    renderRoster();
    await openChatForWorker(workerId);
    await loadRoutines(workerId);
}

async function openChatForWorker(workerId) {
    try {
        // Reuse latest chat if present
        const detail = await fetch(`${apiBase()}/workers/${workerId}`).then((r) => r.json());
        const worker = detail.worker;
        if (worker) updateWorkerHeader(worker);

        const chats = detail.chats || [];
        if (chats.length) {
            chatSessionId = chats[0].id;
            const sess = await fetch(`${apiBase()}/sessions/${chatSessionId}`).then((r) => r.json());
            if (chatMessages) chatMessages.innerHTML = "";
            (sess.messages || []).forEach((m) => {
                appendChatMessage(m.role, m.content, {
                    ...(m.metadata || {}),
                    kind: m.kind || (m.metadata && m.metadata.kind) || "text",
                });
            });
            const st = sess.session?.status;
            if (st === "working") {
                setChatWorking(true);
                startChatPoll();
            }
        } else {
            const res = await fetch(`${apiBase()}/workers/${workerId}/chats`, { method: "POST" });
            const data = await res.json();
            chatSessionId = data.session?.id;
            if (chatMessages) chatMessages.innerHTML = "";
            if (data.greeting) {
                appendChatMessage("assistant", data.greeting, { intent: "greeting", kind: "text" });
            }
            // Reload to pick up seed event messages
            const sess = await fetch(`${apiBase()}/sessions/${chatSessionId}`).then((r) => r.json());
            if (chatMessages) chatMessages.innerHTML = "";
            (sess.messages || []).forEach((m) => {
                appendChatMessage(m.role, m.content, {
                    ...(m.metadata || {}),
                    kind: m.kind || "text",
                });
            });
        }
        await loadRoutines(workerId);
    } catch (e) {
        appendChatMessage("assistant", "Couldn't connect to OpenDesktop API. Is the server running on port 8000?", { error: true, kind: "text" });
        console.error(e);
    }
}

async function loadRoutines(workerId) {
    const list = document.getElementById("routines-list");
    if (!list) return;
    try {
        const res = await fetch(`${apiBase()}/workers/${workerId}/routines`);
        const data = await res.json();
        const routines = data.routines || [];
        list.innerHTML = "";
        if (!routines.length) {
            list.innerHTML = `<span class="routine-empty">No standing work yet — add a Routine so work can start without a prompt.</span>`;
            return;
        }
        routines.forEach((r) => {
            const el = document.createElement("div");
            el.className = "routine-chip" + (r.paused ? " paused" : "");
            el.innerHTML = `
                <span class="routine-name">${escapeHtml(r.name)}</span>
                <span class="routine-meta">every ${r.interval_seconds}s</span>
                <button class="btn btn-secondary btn-sm routine-toggle" data-id="${r.id}" data-paused="${r.paused ? "1" : "0"}">
                    ${r.paused ? "Resume" : "Pause"}
                </button>
            `;
            list.appendChild(el);
        });
        list.querySelectorAll(".routine-toggle").forEach((btn) => {
            btn.addEventListener("click", async (ev) => {
                ev.stopPropagation();
                const id = btn.dataset.id;
                const paused = btn.dataset.paused === "1";
                const path = paused ? "resume" : "pause";
                await fetch(`${apiBase()}/routines/${id}/${path}`, { method: "POST" });
                await loadRoutines(workerId);
            });
        });
    } catch (e) {
        console.error(e);
    }
}

function appendChatMessage(role, content, meta = {}) {
    if (!chatMessages) return;
    const kind = meta.kind || "text";
    const el = document.createElement("div");
    el.className = `chat-msg ${role} kind-${kind}${meta.status === "working" ? " working" : ""}${meta.error ? " error" : ""}`;

    if (kind === "event") {
        el.innerHTML = `<div class="msg-event">${renderMarkdown(content)}</div>`;
    } else if (kind === "widget") {
        el.innerHTML = renderWidget(content, meta);
    } else if (kind === "artifact_ref") {
        el.innerHTML = `<div class="msg-artifact">
            <span class="artifact-label">Artifact</span>
            <strong>${escapeHtml(meta.title || content)}</strong>
            <span class="artifact-id">${escapeHtml(meta.artifact_id || "")}</span>
        </div>`;
    } else if (kind === "computer_status") {
        el.innerHTML = `<div class="msg-computer">${renderMarkdown(content)}</div>`;
        if (computerStatusChip) computerStatusChip.dataset.active = "true";
    } else if (role === "assistant" && !meta.error) {
        el.innerHTML = renderMarkdown(content);
    } else {
        el.textContent = content;
    }

    if (meta.intent && kind === "text") {
        const m = document.createElement("div");
        m.className = "chat-msg-meta";
        m.textContent = meta.intent;
        el.appendChild(m);
    }
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderWidget(content, meta) {
    if (meta.widget === "routine" || meta.routine_id) {
        return `<div class="msg-widget routine-widget">
            <div class="widget-title">Created Routine</div>
            <div class="widget-body"><strong>${escapeHtml(content)}</strong>
            <p>${escapeHtml(meta.prompt || "")}</p>
            <span class="widget-meta">every ${meta.interval_seconds || "—"}s</span></div>
        </div>`;
    }
    return `<div class="msg-widget"><div class="widget-title">${escapeHtml(content)}</div>
        <pre class="widget-json">${escapeHtml(JSON.stringify(meta, null, 2))}</pre></div>`;
}

async function sendChatMessage() {
    if (!chatInput || !chatSessionId || chatIsWorking) return;
    const text = chatInput.value.trim();
    if (!text) return;

    chatInput.value = "";
    appendChatMessage("user", text, { kind: "text" });
    setChatWorking(true);
    if (chatStatusBadge) {
        chatStatusBadge.textContent = "Thinking…";
        chatStatusBadge.className = "badge badge-amber";
    }

    try {
        const res = await fetch(`${apiBase()}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, session_id: chatSessionId, worker_id: activeWorkerId }),
        });
        const data = await res.json();
        const reply = data.reply || data.result?.reply || "";
        const status = data.status || data.result?.status;
        if (reply) {
            appendChatMessage("assistant", reply, {
                intent: data.intent || data.result?.intent,
                status,
                kind: "text",
            });
        }
        if (chatStatusBadge) {
            chatStatusBadge.textContent = status === "working" ? "Working…" : "Ready";
            chatStatusBadge.className = status === "working" ? "badge badge-amber" : "badge badge-green";
        }
        if (status === "working") {
            startChatPoll();
            if (computerStatusChip) computerStatusChip.dataset.active = "true";
        } else {
            setChatWorking(false);
        }
        await loadWorkers();
    } catch (e) {
        appendChatMessage("assistant", "Request failed — check the API is up.", { error: true, kind: "text" });
        setChatWorking(false);
        console.error(e);
    }
}

function startChatPoll() {
    stopChatPoll();
    chatPollInterval = setInterval(async () => {
        if (!chatSessionId) return;
        try {
            const res = await fetch(`${apiBase()}/sessions/${chatSessionId}`);
            const data = await res.json();
            const session = data.session || {};
            const messages = data.messages || [];
            if (chatMessages) {
                const rendered = chatMessages.querySelectorAll(".chat-msg").length;
                if (messages.length > rendered) {
                    chatMessages.innerHTML = "";
                    messages.forEach((m) => {
                        appendChatMessage(m.role, m.content, {
                            ...(m.metadata || {}),
                            kind: m.kind || (m.metadata && m.metadata.kind) || "text",
                        });
                    });
                }
            }
            if (session.status === "idle" || session.status === "error") {
                setChatWorking(false);
                stopChatPoll();
                if (chatStatusBadge) {
                    chatStatusBadge.textContent = session.status === "error" ? "Blocked" : "Ready";
                    chatStatusBadge.className = session.status === "error" ? "badge badge-rose" : "badge badge-green";
                }
                await loadWorkers();
            }
            // Live screen if preview open
            const mid = session.machine_id || (data.worker && data.worker.preferred_machine_id);
            if (mid && (previewOpen || takeoverOpen)) {
                refreshScreen(mid);
            }
        } catch (e) {
            console.error(e);
        }
    }, 2500);
}

function stopChatPoll() {
    if (chatPollInterval) {
        clearInterval(chatPollInterval);
        chatPollInterval = null;
    }
}

async function refreshScreen(machineId) {
    try {
        const res = await fetch(`${apiBase()}/machines/${machineId}/screenshot`);
        if (!res.ok) return;
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        if (chatLiveImg && previewOpen) chatLiveImg.src = url;
        if (takeoverImg && takeoverOpen) takeoverImg.src = url;
    } catch (_) { /* ignore */ }
}

function setPreviewOpen(open) {
    previewOpen = open;
    if (!computerPreview) return;
    computerPreview.hidden = !open;
    computerPreview.dataset.open = open ? "true" : "false";
    const btn = document.getElementById("btn-toggle-preview");
    if (btn) {
        btn.setAttribute("aria-pressed", open ? "true" : "false");
        btn.classList.toggle("active", open);
    }
    const shell = document.getElementById("container-chat");
    if (shell) shell.classList.toggle("preview-open", open);
}

function setTakeoverOpen(open) {
    takeoverOpen = open;
    if (!takeoverOverlay) return;
    takeoverOverlay.hidden = !open;
    const handBtn = document.getElementById("btn-hand-back");
    if (handBtn) handBtn.hidden = !open;
    if (open) {
        const w = workersCache.find((x) => x.id === activeWorkerId);
        if (w?.preferred_machine_id) refreshScreen(w.preferred_machine_id);
        // Mark waiting presence via patch (user seated)
        if (activeWorkerId) {
            fetch(`${apiBase()}/workers/${activeWorkerId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ presence: "waiting", current_action: "User takeover" }),
            }).catch(() => {});
        }
    } else if (activeWorkerId) {
        fetch(`${apiBase()}/workers/${activeWorkerId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ presence: "idle", current_action: null }),
        }).then(() => loadWorkers()).catch(() => {});
    }
}

function connectChatActionWs() {
    try {
        chatActionWs = new WebSocket(`${wsBase()}/actions`);
        chatActionWs.onmessage = (ev) => {
            try {
                const event = JSON.parse(ev.data);
                const feed = document.getElementById("chat-log-feed");
                if (feed) {
                    const line = document.createElement("div");
                    line.className = "log-item";
                    line.textContent = event.thought || event.action_type || JSON.stringify(event);
                    feed.prepend(line);
                }
                if (event.worker_id === activeWorkerId || event.thought) {
                    loadWorkers();
                }
            } catch (_) { /* ignore */ }
        };
    } catch (_) { /* ignore */ }
}

async function initChat() {
    await loadWorkers();
    if (activeWorkerId) {
        await openChatForWorker(activeWorkerId);
    }
    connectChatActionWs();
    rosterPoll = setInterval(loadWorkers, 5000);

    if (chatSendBtn) chatSendBtn.addEventListener("click", sendChatMessage);
    if (chatInput) {
        chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }
    document.querySelectorAll(".chat-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            if (chatInput) {
                chatInput.value = chip.dataset.prompt || chip.textContent;
                chatInput.focus();
            }
        });
    });

    document.getElementById("btn-toggle-preview")?.addEventListener("click", () => setPreviewOpen(!previewOpen));
    document.getElementById("btn-close-preview")?.addEventListener("click", () => setPreviewOpen(false));
    document.getElementById("btn-takeover")?.addEventListener("click", () => setTakeoverOpen(true));
    document.getElementById("btn-hand-back")?.addEventListener("click", () => setTakeoverOpen(false));
    document.getElementById("btn-takeover-hand-back")?.addEventListener("click", () => setTakeoverOpen(false));

    // New worker modal
    const modalWorker = document.getElementById("modal-worker");
    document.getElementById("btn-add-worker")?.addEventListener("click", () => {
        if (modalWorker) modalWorker.hidden = false;
    });
    document.getElementById("btn-add-group")?.addEventListener("click", async () => {
        const ids = workersCache.map((w) => w.id).slice(0, 6);
        if (ids.length < 2) {
            alert("Create at least two Workers before opening a group chat.");
            return;
        }
        const name = prompt("Group name", "Project sync");
        if (!name) return;
        const coordinator = workersCache.find((w) => w.id === "wrk_coordinator")?.id || ids[0];
        const res = await fetch(`${apiBase()}/groups`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, worker_ids: ids.slice(0, 3), coordinator_id: coordinator }),
        });
        const data = await res.json();
        if (!res.ok) {
            alert(data.detail || "Could not create group");
            return;
        }
        // Open the group's session under the coordinator
        activeWorkerId = coordinator;
        chatSessionId = data.group?.session_id;
        await loadWorkers();
        if (chatSessionId) {
            const sess = await fetch(`${apiBase()}/sessions/${chatSessionId}`).then((r) => r.json());
            if (chatMessages) chatMessages.innerHTML = "";
            (sess.messages || []).forEach((m) => {
                appendChatMessage(m.role, m.content, {
                    ...(m.metadata || {}),
                    kind: m.kind || "text",
                });
            });
        }
        await loadRoutines(coordinator);
    });
    document.getElementById("btn-close-worker-modal")?.addEventListener("click", () => {
        if (modalWorker) modalWorker.hidden = true;
    });
    document.getElementById("btn-save-worker")?.addEventListener("click", async () => {
        const name = document.getElementById("input-worker-name")?.value?.trim();
        const role = document.getElementById("input-worker-role")?.value?.trim() || "general";
        const avatar = document.getElementById("input-worker-avatar")?.value || "default";
        if (!name) return;
        const res = await fetch(`${apiBase()}/workers`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, role, avatar }),
        });
        const data = await res.json();
        if (modalWorker) modalWorker.hidden = true;
        await loadWorkers();
        if (data.worker?.id) await selectWorker(data.worker.id);
    });

    // Routine modal
    const modalRoutine = document.getElementById("modal-routine");
    document.getElementById("btn-add-routine")?.addEventListener("click", () => {
        if (modalRoutine) modalRoutine.hidden = false;
    });
    document.getElementById("btn-close-routine-modal")?.addEventListener("click", () => {
        if (modalRoutine) modalRoutine.hidden = true;
    });
    document.getElementById("btn-save-routine")?.addEventListener("click", async () => {
        if (!activeWorkerId) return;
        const name = document.getElementById("input-routine-name")?.value?.trim();
        const prompt = document.getElementById("input-routine-prompt")?.value?.trim();
        const interval = parseInt(document.getElementById("input-routine-interval")?.value || "86400", 10);
        if (!name || !prompt) return;
        await fetch(`${apiBase()}/workers/${activeWorkerId}/routines`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, prompt, interval_seconds: interval }),
        });
        if (modalRoutine) modalRoutine.hidden = true;
        await loadRoutines(activeWorkerId);
        // Refresh transcript for event + widget
        if (chatSessionId) {
            const sess = await fetch(`${apiBase()}/sessions/${chatSessionId}`).then((r) => r.json());
            if (chatMessages) chatMessages.innerHTML = "";
            (sess.messages || []).forEach((m) => {
                appendChatMessage(m.role, m.content, {
                    ...(m.metadata || {}),
                    kind: m.kind || "text",
                });
            });
        }
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initChat);
} else {
    initChat();
}
