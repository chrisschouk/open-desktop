// OpenWorker Chat — conversational UI for OpenDesktop

let chatSessionId = null;
let chatPollInterval = null;
let chatIsWorking = false;

const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("btn-chat-send");
const chatLiveImg = document.getElementById("chat-live-screen");
const chatStatusBadge = document.getElementById("chat-status-badge");

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
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

async function initChat() {
    try {
        const res = await fetch(`${API_BASE}/sessions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ persona_id: "openworker" }),
        });
        const data = await res.json();
        chatSessionId = data.session?.id;
        if (data.greeting) {
            appendChatMessage("assistant", data.greeting, { intent: "greeting" });
        }
    } catch (e) {
        appendChatMessage("assistant", "Couldn't connect to OpenDesktop API. Is the server running on port 8000?", { error: true });
        console.error("Chat init failed:", e);
    }
}

function appendChatMessage(role, content, meta = {}) {
    if (!chatMessages) return;
    const el = document.createElement("div");
    el.className = `chat-msg ${role}${meta.status === "working" ? " working" : ""}${meta.error ? " error" : ""}`;
    if (role === "assistant" && !meta.error) {
        el.innerHTML = renderMarkdown(content);
    } else {
        el.textContent = content;
    }
    if (meta.intent) {
        const m = document.createElement("div");
        m.className = "chat-msg-meta";
        m.textContent = meta.intent;
        el.appendChild(m);
    }
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendChatMessage() {
    if (!chatInput || !chatSessionId || chatIsWorking) return;
    const text = chatInput.value.trim();
    if (!text) return;

    appendChatMessage("user", text);
    chatInput.value = "";
    setChatWorking(true);

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, session_id: chatSessionId }),
        });
        const data = await res.json();
        appendChatMessage("assistant", data.reply || "No reply", {
            intent: data.intent,
            status: data.status,
        });

        if (chatStatusBadge) {
            chatStatusBadge.textContent = data.status === "working" ? "Working…" : "Ready";
            chatStatusBadge.className = data.status === "working" ? "badge badge-amber" : "badge badge-green";
        }

        if (data.status === "working") {
            startChatPolling();
            connectChatLiveStream();
        } else {
            setChatWorking(false);
        }
    } catch (e) {
        appendChatMessage("assistant", `Error: ${e.message}`, { error: true });
        setChatWorking(false);
    }
}

function startChatPolling() {
    if (chatPollInterval) clearInterval(chatPollInterval);
    let lastCount = 0;

    chatPollInterval = setInterval(async () => {
        if (!chatSessionId) return;
        try {
            const res = await fetch(`${API_BASE}/sessions/${chatSessionId}`);
            const data = await res.json();
            const msgs = data.messages || [];
            const session = data.session || {};

            if (lastCount === 0) {
                lastCount = msgs.length;
            } else if (msgs.length > lastCount) {
                for (let i = lastCount; i < msgs.length; i++) {
                    const m = msgs[i];
                    if (m.role === "assistant" && (m.metadata?.status === "completed" || m.metadata?.status === "error")) {
                        appendChatMessage("assistant", m.content, { intent: m.metadata?.status || "completed" });
                    }
                }
                lastCount = msgs.length;
            }

            if (session.status === "idle" || session.status === "error") {
                clearInterval(chatPollInterval);
                chatPollInterval = null;
                setChatWorking(false);
                if (chatStatusBadge) {
                    if (session.status === "error") {
                        chatStatusBadge.textContent = "Error";
                        chatStatusBadge.className = "badge badge-amber";
                    } else {
                        chatStatusBadge.textContent = "Ready";
                        chatStatusBadge.className = "badge badge-green";
                    }
                }
            }
        } catch (e) {
            console.log("Chat poll error:", e);
        }
    }, 3000);
}

function connectChatLiveStream() {
    if (!chatLiveImg) return;
    fetch(`${API_BASE}/machines`)
        .then(r => r.json())
        .then(data => {
            const running = (data.machines || []).find(m => m.status === "running");
            if (!running) return;
            const ws = new WebSocket(`${WS_BASE}/stream/${running.id}`);
            ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === "frame" && msg.data) {
                        chatLiveImg.src = "data:image/jpeg;base64," + msg.data;
                    }
                } catch (e) { /* ignore */ }
            };
        })
        .catch(() => {});
}

function setupChatListeners() {
    if (chatSendBtn) chatSendBtn.addEventListener("click", sendChatMessage);
    if (chatInput) {
        chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }
    document.querySelectorAll(".chat-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            if (chatInput) {
                chatInput.value = chip.getAttribute("data-prompt") || "";
                chatInput.focus();
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    setupChatListeners();
});
