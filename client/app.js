// OpenDesktop Client - Digital Employee OS & Playbook Engine

// Same-origin when served via demo proxy / public tunnel; localhost when developing locally.
(() => {
    const host = window.location.hostname;
    const proto = window.location.protocol === "https:" ? "https" : "http";
    const wsProto = window.location.protocol === "https:" ? "wss" : "ws";
    const local = host === "localhost" || host === "127.0.0.1";
    const API_BASE = local ? "http://localhost:8000/api/v1" : `${proto}://${window.location.host}/api/v1`;
    const WS_BASE = local ? "ws://localhost:8000/ws" : `${wsProto}://${window.location.host}/ws`;
    window.API_BASE = API_BASE;
    window.WS_BASE = WS_BASE;
})();
const API_BASE = window.API_BASE;
const WS_BASE = window.WS_BASE;

let activeComputerId = null;
let machines = [];
const machineViewers = new Map();
let actionStream = null;

// DOM Elements
const computerTabsBar = document.getElementById("computer-tabs-bar");
const activeComputerCount = document.getElementById("active-computer-count");
const btnAddComputer = document.getElementById("btn-add-computer");
const btnRunAgent = document.getElementById("btn-run-agent");
const agentPrompt = document.getElementById("agent-prompt");
const playbookSelect = document.getElementById("playbook-select");
const badgeActivePlaybook = document.getElementById("badge-active-playbook");
const logFeed = document.getElementById("log-feed");
const machinesGrid = document.getElementById("machines-grid");
const modalApi = document.getElementById("modal-api");
const btnApiKeys = document.getElementById("btn-api-keys");
const btnCloseModal = document.getElementById("btn-close-modal");

// Navigation Tabs
const btnTabChat = document.getElementById("btn-tab-chat");
const btnTabOperator = document.getElementById("btn-tab-operator");
const btnTabDeveloper = document.getElementById("btn-tab-developer");
const containerChat = document.getElementById("container-chat");
const containerOperator = document.getElementById("container-operator");
const containerDeveloper = document.getElementById("container-developer");

class MachineViewer {
    constructor(machine) {
        this.machine = machine;
        this.ws = null;
        this.reconnectTimeout = null;
        this.status = 'disconnected';
        
        this.element = this.createDOM();
        this.connect();
    }

    createDOM() {
        const wrapper = document.createElement("div");
        wrapper.className = "grid-computer-box";
        wrapper.id = `machine-box-${this.machine.id}`;

        const header = document.createElement("div");
        header.className = "comp-box-header";
        header.textContent = this.machine.name;

        const controls = document.createElement("div");
        controls.className = "machine-controls";
        controls.innerHTML = `
            <button class="control-btn" onclick="controlMachine('${this.machine.id}', 'start')">Start</button>
            <button class="control-btn" onclick="controlMachine('${this.machine.id}', 'stop')">Stop</button>
            <button class="control-btn" onclick="controlMachine('${this.machine.id}', 'restart')">Restart</button>
        `;

        const viewer = document.createElement("div");
        viewer.className = "machine-viewer";
        
        this.img = document.createElement("img");
        this.img.className = "machine-screen";
        
        this.statusEl = document.createElement("div");
        this.statusEl.className = "machine-status";
        
        this.statusIndicator = document.createElement("span");
        this.statusIndicator.className = "status-indicator status-disconnected";
        
        this.statusText = document.createTextNode(" Disconnected");
        
        this.statusEl.appendChild(this.statusIndicator);
        this.statusEl.appendChild(this.statusText);
        
        viewer.appendChild(this.img);
        viewer.appendChild(this.statusEl);

        wrapper.appendChild(header);
        wrapper.appendChild(controls);
        wrapper.appendChild(viewer);
        
        return wrapper;
    }

    updateStatus(status) {
        this.status = status;
        this.statusIndicator.className = `status-indicator status-${status}`;
        this.statusText.textContent = ` ${status.charAt(0).toUpperCase() + status.slice(1)}`;
        
        const viewer = this.element.querySelector('.machine-viewer');
        if (status === 'connected') {
            viewer.classList.add('connected-glow');
        } else {
            viewer.classList.remove('connected-glow');
        }
    }

    connect() {
        this.updateStatus('connecting');
        
        this.ws = new WebSocket(`${WS_BASE}/stream/${this.machine.id}`);
        
        this.ws.onopen = () => {
            this.updateStatus('connected');
            if (this.reconnectTimeout) {
                clearTimeout(this.reconnectTimeout);
                this.reconnectTimeout = null;
            }
        };
        
        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'frame' && msg.data) {
                    this.img.src = 'data:image/jpeg;base64,' + msg.data;
                }
            } catch (e) {
                console.error("Error parsing frame data", e);
            }
        };
        
        this.ws.onclose = () => {
            this.updateStatus('disconnected');
            this.scheduleReconnect();
        };
        
        this.ws.onerror = () => {
            this.ws.close();
        };
    }
    
    scheduleReconnect() {
        if (!this.reconnectTimeout) {
            this.reconnectTimeout = setTimeout(() => {
                this.reconnectTimeout = null;
                this.connect();
            }, 3000);
        }
    }

    highlight(active) {
        if (active) {
            this.element.classList.add("active-machine");
        } else {
            this.element.classList.remove("active-machine");
        }
    }
}

class ActionStream {
    constructor() {
        this.ws = null;
        this.reconnectTimeout = null;
        this.connect();
    }
    
    connect() {
        this.ws = new WebSocket(`${WS_BASE}/actions`);
        
        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'action') {
                    this.renderLogStep(msg);
                }
            } catch (e) {
                console.error("Error parsing action data", e);
            }
        };
        
        this.ws.onclose = () => {
            this.scheduleReconnect();
        };
        
        this.ws.onerror = () => {
            this.ws.close();
        };
    }
    
    scheduleReconnect() {
        if (!this.reconnectTimeout) {
            this.reconnectTimeout = setTimeout(() => {
                this.reconnectTimeout = null;
                this.connect();
            }, 3000);
        }
    }
    
    renderLogStep(s) {
        if (!logFeed) return;
        const chatLog = document.getElementById("chat-log-feed");
        [logFeed, chatLog].filter(Boolean).forEach(feed => {
            const item = document.createElement("div");
            item.className = "log-item fade-in";
            const actName = s.action_type || "action";
            item.innerHTML = `
                <div class="log-item-header">
                    <span class="log-step-num">STEP ${s.step || '-'} [${s.agent || s.machine_id || 'Agent'}]</span>
                    <span class="log-action-tag">${actName.toUpperCase()}</span>
                </div>
                <div class="log-thought">${s.thought || ''}</div>
            `;
            feed.prepend(item);
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

function initApp() {
    setupEventListeners();
    setMainTab("chat");
    initChat();
    fetchMachines();
    actionStream = new ActionStream();
    fetchEngineStatus();
}

async function fetchEngineStatus() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        const el = document.getElementById("engine-status");
        if (el) {
            const dockerOk = data.docker?.available ? "docker ok" : "docker unavailable";
            el.textContent = `${data.agent || "OpenWorker"} • ${data.sandbox_mode || "local"} • ${dockerOk}`;
        }
        updateSetupBanner(data);
    } catch (e) {
        const banner = document.getElementById("setup-banner");
        const text = document.getElementById("setup-banner-text");
        if (banner && text) {
            text.textContent = "OpenDesktop API offline — start uvicorn server.main:app on port 8000";
            banner.hidden = false;
        }
    }
}

function updateSetupBanner(health) {
    const banner = document.getElementById("setup-banner");
    const text = document.getElementById("setup-banner-text");
    const bannerBtn = document.getElementById("btn-banner-api-key");
    if (!banner || !text) return;
    if (sessionStorage.getItem("opendesktop-banner-dismissed") === "1") {
        banner.hidden = true;
        return;
    }
    if (!health.api_key_configured) {
        text.textContent = "No API key — paste your OpenRouter sk-or- key (DeepSeek V4 Flash only).";
        if (bannerBtn) bannerBtn.textContent = "Add API Key";
        banner.hidden = false;
        return;
    }
    if (!health.docker?.available) {
        text.textContent = "Docker is not available — sandbox automation requires Docker. You can still chat after setting an API key.";
        if (bannerBtn) bannerBtn.textContent = "API Key";
        banner.hidden = false;
        return;
    }
    banner.hidden = true;
}

function setupEventListeners() {
    document.querySelectorAll(".chip-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            if (agentPrompt) agentPrompt.value = btn.getAttribute("data-prompt") || "";
        });
    });

    if (btnRunAgent) btnRunAgent.addEventListener("click", () => runCampaign());
    if (btnAddComputer) btnAddComputer.addEventListener("click", () => createMachine());

    if (btnTabChat) btnTabChat.addEventListener("click", () => setMainTab("chat"));
    if (btnTabOperator) btnTabOperator.addEventListener("click", () => setMainTab("operator"));
    if (btnTabDeveloper) btnTabDeveloper.addEventListener("click", () => setMainTab("developer"));

    if (btnApiKeys) btnApiKeys.addEventListener("click", () => modalApi.classList.add("open"));
    if (btnCloseModal) btnCloseModal.addEventListener("click", () => modalApi.classList.remove("open"));

    const btnBannerKey = document.getElementById("btn-banner-api-key");
    if (btnBannerKey && modalApi) {
        btnBannerKey.addEventListener("click", () => modalApi.classList.add("open"));
    }
    const btnDismissBanner = document.getElementById("btn-dismiss-banner");
    if (btnDismissBanner) {
        btnDismissBanner.addEventListener("click", () => {
            sessionStorage.setItem("opendesktop-banner-dismissed", "1");
            const banner = document.getElementById("setup-banner");
            if (banner) banner.hidden = true;
        });
    }

    // Helper function to save API Key to backend
    async function saveKey(keyVal, statusEl) {
        if (!keyVal) return;
        try {
            const res = await fetch(`${API_BASE}/keys/set`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ api_key: keyVal })
            });
            const raw = await res.text();
            let data = null;
            try {
                data = raw ? JSON.parse(raw) : null;
            } catch {
                throw new Error(
                    res.ok
                        ? "Server returned a non-JSON page (stale tunnel URL?). Open the latest demo link and try again."
                        : `Key save failed (HTTP ${res.status}). Open the latest demo link — old tunnel URLs expire.`
                );
            }
            if (!res.ok) {
                throw new Error((data && (data.detail || data.message)) || `HTTP ${res.status}`);
            }
            if (data && data.status === "success") {
                if (statusEl) {
                    statusEl.style.display = "block";
                    setTimeout(() => { statusEl.style.display = "none"; }, 2000);
                }
                fetchEngineStatus();
                return true;
            }
            throw new Error((data && data.message) || "Unexpected response from server");
        } catch (e) {
            alert("Failed to save key: " + e.message);
        }
        return false;
    }

    const btnSaveKey = document.getElementById("btn-save-api-key");
    const inputKey = document.getElementById("input-api-key");
    const keyStatus = document.getElementById("key-save-status");
    if (btnSaveKey && inputKey) {
        btnSaveKey.addEventListener("click", async (e) => {
            e.preventDefault();
            const ok = await saveKey(inputKey.value.trim(), keyStatus);
            if (ok && modalApi) setTimeout(() => modalApi.classList.remove("open"), 1000);
        });
    }

    const btnSaveSidebarKey = document.getElementById("btn-save-sidebar-key");
    const sidebarInputKey = document.getElementById("sidebar-api-key");
    const sidebarKeyStatus = document.getElementById("sidebar-key-status");
    if (btnSaveSidebarKey && sidebarInputKey) {
        btnSaveSidebarKey.addEventListener("click", async (e) => {
            e.preventDefault();
            await saveKey(sidebarInputKey.value.trim(), sidebarKeyStatus);
        });
    }
}

function setMainTab(tab) {
    const show = (el, visible) => {
        if (!el) return;
        if (visible) {
            el.style.display = el.id === "container-chat" || el.id === "container-operator" ? "grid" : "block";
            el.classList.add("is-visible");
        } else {
            el.style.display = "none";
            el.classList.remove("is-visible");
        }
    };
    show(containerChat, tab === "chat");
    show(containerOperator, tab === "operator");
    show(containerDeveloper, tab === "developer");
    if (btnTabChat) btnTabChat.classList.toggle("active", tab === "chat");
    if (btnTabOperator) btnTabOperator.classList.toggle("active", tab === "operator");
    if (btnTabDeveloper) btnTabDeveloper.classList.toggle("active", tab === "developer");
}

async function fetchMachines() {
    try {
        const res = await fetch(`${API_BASE}/machines`);
        const data = await res.json();
        if (data.machines && data.machines.length > 0) {
            // Check if machine list changed
            const newIds = data.machines.map(m => m.id).join(",");
            const oldIds = machines.map(m => m.id).join(",");
            
            if (newIds !== oldIds || machineViewers.size === 0) {
                machinesGrid.innerHTML = '';
                machineViewers.forEach(v => {
                    if (v.ws) v.ws.close();
                });
                machineViewers.clear();
                machines = data.machines;
                
                machines.forEach(m => {
                    const viewer = new MachineViewer(m);
                    machineViewers.set(m.id, viewer);
                    machinesGrid.appendChild(viewer.element);
                });
                
                if (!activeComputerId || !machineViewers.has(activeComputerId)) {
                    activeComputerId = machines[0].id;
                }
                renderTabs();
                switchMachine(activeComputerId);
            }
        } else {
            // Auto-provision initial machine if none exist
            console.log("No machines found. Auto-provisioning Agent Machine #1...");
            await createMachine();
        }
    } catch (e) {
        console.log("Fetch machines error, retrying in 3s:", e);
        setTimeout(fetchMachines, 3000);
    }
}

async function createMachine() {
    try {
        const res = await fetch(`${API_BASE}/machines`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: `Machine #${machines.length + 1}`, template: "medium" })
        });
        const data = await res.json();
        if (data.machine) {
            machines.push(data.machine);
            const viewer = new MachineViewer(data.machine);
            machineViewers.set(data.machine.id, viewer);
            machinesGrid.appendChild(viewer.element);
            renderTabs();
            switchMachine(data.machine.id);
        }
    } catch (e) {
        console.log("Create machine error:", e);
    }
}

function renderTabs() {
    if (!computerTabsBar) return;
    const existing = computerTabsBar.querySelectorAll(".tab-btn");
    existing.forEach(e => e.remove());

    machines.forEach(c => {
        const btn = document.createElement("button");
        btn.className = `tab-btn ${c.id === activeComputerId ? 'active' : ''}`;
        btn.setAttribute("data-id", c.id);
        btn.innerHTML = `<span class="tab-dot"></span><span>${c.name}</span>`;
        btn.addEventListener("click", () => switchMachine(c.id));
        computerTabsBar.insertBefore(btn, btnAddComputer);
    });

    if (activeComputerCount) {
        activeComputerCount.textContent = machines.length;
    }
}

function switchMachine(id) {
    activeComputerId = id;
    renderTabs();
    machineViewers.forEach((viewer, vId) => {
        viewer.highlight(vId === id);
    });
}

async function runCampaign() {
    const sidebarInputKey = document.getElementById("sidebar-api-key");
    if (sidebarInputKey && sidebarInputKey.value.trim()) {
        try {
            await fetch(`${API_BASE}/keys/set`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ api_key: sidebarInputKey.value.trim() })
            });
        } catch (e) {
            console.log("Auto-save key error:", e);
        }
    }

    const prompt = agentPrompt ? agentPrompt.value.trim() : "";
    if (!prompt) {
        alert("Please enter a campaign goal instruction.");
        return;
    }

    const playbookId = playbookSelect ? playbookSelect.value : "pb_web_research";
    if (badgeActivePlaybook) {
        badgeActivePlaybook.textContent = `TEMPLATE: ${playbookId.toUpperCase()}`;
    }

    if (btnRunAgent) {
        btnRunAgent.disabled = true;
        btnRunAgent.textContent = `Executing ${playbookId}...`;
    }

    try {
        await fetch(`${API_BASE}/playbooks/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ playbook_id: playbookId, prompt })
        });
        // ActionStream WebSocket will show the live updates
    } catch (e) {
        console.log("Playbook dispatch error:", e);
    } finally {
        setTimeout(() => {
            if (btnRunAgent) {
                btnRunAgent.disabled = false;
                btnRunAgent.textContent = "Run Campaign Template";
            }
        }, 3000);
    }
}

window.controlMachine = async function(id, action) {
    try {
        await fetch(`${API_BASE}/machines/${id}/actions`, { 
            method: "POST", 
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: action }) 
        });
        console.log(`Machine ${id} action: ${action} sent.`);
    } catch (e) {
        console.log(`Failed to send ${action} to machine ${id}:`, e);
    }
};
