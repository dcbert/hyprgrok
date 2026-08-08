/* HyprGrok panel frontend */

const $ = (id) => document.getElementById(id);

const els = {
  statusPill: $("statusPill"),
  contextBody: $("contextBody"),
  prompt: $("prompt"),
  injectContext: $("injectContext"),
  includeShot: $("includeShot"),
  sendBtn: $("sendBtn"),
  sendSpinner: $("sendSpinner"),
  sessionBtn: $("sessionBtn"),
  askWindowBtn: $("askWindowBtn"),
  response: $("response"),
  clearResponse: $("clearResponse"),
  refreshContext: $("refreshContext"),
  cwdLabel: $("cwdLabel"),
  toast: $("toast"),
  missingBanner: $("missingBanner"),
  sessionsList: $("sessionsList"),
  historyList: $("historyList"),
  refreshSessions: $("refreshSessions"),
  refreshHistory: $("refreshHistory"),
  verLabel: $("verLabel"),
};

let currentCwd = null;
let busy = false;
let lastResponseBySession = {};

function toast(msg, isError = false) {
  els.toast.textContent = msg;
  els.toast.classList.toggle("error", isError);
  els.toast.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => els.toast.classList.add("hidden"), 3200);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
    },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

function setBusy(on) {
  busy = on;
  [els.sendBtn, els.sessionBtn, els.askWindowBtn].forEach((b) => {
    if (b) b.disabled = on;
  });
  els.sendSpinner.classList.toggle("hidden", !on);
  els.sendBtn.querySelector(".btn-label").textContent = on ? "Thinking…" : "Send to Grok";
  if (on) {
    els.statusPill.textContent = "busy";
    els.statusPill.className = "status-pill busy";
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderContext(ctx) {
  if (!ctx) {
    els.contextBody.innerHTML = `<div class="muted">No context</div>`;
    return;
  }
  currentCwd = ctx.project_root || ctx.cwd || null;
  els.cwdLabel.textContent = currentCwd ? `cwd: ${currentCwd}` : "";
  const rows = [
    ["kind", ctx.kind],
    ["title", ctx.window_title],
    ["class", ctx.window_class],
    ["file", ctx.file_hint],
    ["cwd", ctx.cwd],
    ["project", ctx.project_root],
    ["name", ctx.project_name],
    ["workspace", ctx.workspace],
    ["shot", ctx.screenshot_path],
  ].filter(([, v]) => v);
  els.contextBody.innerHTML = rows
    .map(
      ([k, v]) =>
        `<div><span class="k">${k}</span> <span class="v">${escapeHtml(String(v))}</span></div>`
    )
    .join("");
}

async function refreshStatus() {
  try {
    const { data } = await api("/api/status");
    if (!data.ok) return;
    if (data.version && els.verLabel) els.verLabel.textContent = data.version;
    if (data.missing_message) {
      els.missingBanner.textContent = data.missing_message;
      els.missingBanner.classList.remove("hidden");
    } else {
      els.missingBanner.classList.add("hidden");
    }
    if (busy) return;
    const run = data.sessions_summary?.running || 0;
    if (data.grok_found) {
      els.statusPill.textContent = run ? `${run} active` : "grok ready";
      els.statusPill.className = "status-pill ok";
      els.statusPill.title = data.grok_path || "grok";
    } else {
      els.statusPill.textContent = "grok missing";
      els.statusPill.className = "status-pill bad";
      els.statusPill.title = data.missing_message || "Install Grok Build";
      if (!els.response.dataset.userCleared && !els.response.dataset.hasContent) {
        els.response.classList.remove("muted");
        els.response.textContent = data.missing_message || "Grok Build not found.";
      }
    }
  } catch (_) {
    els.statusPill.textContent = "offline";
    els.statusPill.className = "status-pill bad";
  }
}

async function refreshContext() {
  const shot = els.includeShot.checked ? "?screenshot=1" : "";
  try {
    const { data } = await api(`/api/context${shot}`);
    if (data.ok) renderContext(data.context);
  } catch (_) {
    els.contextBody.innerHTML = `<div class="muted">Failed to load context</div>`;
  }
}

async function loadConfig() {
  try {
    const { data } = await api("/api/config");
    if (data.ok && data.config) {
      const theme = data.config.theme || {};
      const root = document.documentElement;
      for (const [k, cssVar] of [
        ["accent", "--accent"],
        ["text", "--text"],
        ["muted", "--muted"],
        ["border", "--border"],
        ["success", "--success"],
        ["error", "--error"],
      ]) {
        if (theme[k]) root.style.setProperty(cssVar, theme[k]);
      }
      if (data.config.auto_inject_context) els.injectContext.checked = true;
    }
  } catch (_) {
    /* ignore */
  }
}

function showResponse(text) {
  els.response.classList.remove("muted");
  els.response.textContent = text || "(empty response)";
  els.response.dataset.hasContent = "1";
  delete els.response.dataset.userCleared;
}

async function sendPrompt() {
  const prompt = els.prompt.value.trim();
  if (!prompt) {
    toast("Type a prompt first", true);
    els.prompt.focus();
    return;
  }
  setBusy(true);
  showResponse("Waiting for Grok Build…");
  try {
    const { data } = await api("/api/ask", {
      method: "POST",
      body: JSON.stringify({
        prompt,
        inject_context: els.injectContext.checked,
        screenshot: els.includeShot.checked,
        cwd: currentCwd,
      }),
    });
    if (data.ok) {
      showResponse(data.response || "(empty response)");
      if (data.session_id) lastResponseBySession[data.session_id] = data.response;
      toast("Done");
      refreshHistory();
      refreshSessions();
    } else {
      showResponse(data.response || data.error || "Request failed");
      toast(data.error || "Failed", true);
    }
  } catch (e) {
    showResponse(String(e));
    toast("Network error", true);
  } finally {
    setBusy(false);
    refreshStatus();
  }
}

async function openSession() {
  setBusy(true);
  try {
    const prompt = els.prompt.value.trim() || null;
    const { data } = await api("/api/session", {
      method: "POST",
      body: JSON.stringify({ prompt, cwd: currentCwd }),
    });
    if (data.ok) {
      toast(data.message || "Session launched");
      refreshSessions();
      document.querySelector('.tab[data-tab="sessions"]')?.click();
    } else {
      toast(data.error || "Failed to launch", true);
      showResponse(data.error || "Failed");
    }
  } catch (e) {
    toast(String(e), true);
  } finally {
    setBusy(false);
    refreshStatus();
  }
}

async function askAboutWindow() {
  setBusy(true);
  showResponse("Capturing window context and asking Grok Build…");
  try {
    const extra = els.prompt.value.trim();
    const { data } = await api("/api/ask-about-window", {
      method: "POST",
      body: JSON.stringify({ prompt: extra }),
    });
    if (data.ok) {
      showResponse(data.response || "(empty response)");
      if (data.context) renderContext(data.context);
      toast("Window analysis ready");
      refreshSessions();
      refreshHistory();
    } else {
      showResponse(data.response || data.error || "Failed");
      toast(data.error || "Failed", true);
    }
  } catch (e) {
    showResponse(String(e));
    toast("Network error", true);
  } finally {
    setBusy(false);
    refreshStatus();
  }
}

function timeAgo(ts) {
  if (!ts) return "";
  const sec = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

async function refreshSessions() {
  try {
    const { data } = await api("/api/sessions?limit=40");
    if (!data.ok) return;
    const sessions = data.sessions || [];
    if (!sessions.length) {
      els.sessionsList.innerHTML = `<div class="muted">No sessions yet. Send a prompt or open a full session.</div>`;
      return;
    }
    els.sessionsList.innerHTML = sessions
      .map((s) => {
        const title = escapeHtml(s.label || s.prompt || s.kind);
        const status = escapeHtml(s.status || "");
        const kind = escapeHtml(s.kind || "");
        const cwd = escapeHtml(s.cwd || "");
        const preview = escapeHtml((s.response_preview || s.error || "").slice(0, 160));
        const stopBtn =
          s.status === "running" && s.kind === "interactive"
            ? `<button type="button" class="secondary stop-btn" data-id="${escapeHtml(s.id)}">Stop</button>`
            : "";
        const reuseBtn = s.prompt
          ? `<button type="button" class="secondary reuse-btn" data-prompt="${escapeHtml(s.prompt)}">Reuse</button>`
          : "";
        return `<div class="list-item" data-id="${escapeHtml(s.id)}">
          <div class="title">${title}</div>
          <div class="meta">
            <span><span class="badge ${status}">${status}</span> · ${kind} · ${timeAgo(s.created_at)}</span>
            <span>${cwd}</span>
          </div>
          ${preview ? `<div class="muted">${preview}</div>` : ""}
          <div class="item-actions">${reuseBtn}${stopBtn}</div>
        </div>`;
      })
      .join("");

    els.sessionsList.querySelectorAll(".stop-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute("data-id");
        await api("/api/session/stop", { method: "POST", body: JSON.stringify({ id }) });
        toast("Stop signal sent");
        refreshSessions();
        refreshStatus();
      });
    });
    els.sessionsList.querySelectorAll(".reuse-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        els.prompt.value = btn.getAttribute("data-prompt") || "";
        document.querySelector('.tab[data-tab="ask"]')?.click();
        els.prompt.focus();
      });
    });
    els.sessionsList.querySelectorAll(".list-item").forEach((item) => {
      item.addEventListener("click", () => {
        const id = item.getAttribute("data-id");
        const s = sessions.find((x) => x.id === id);
        if (!s) return;
        if (s.response_preview) {
          showResponse(s.response_preview);
          document.querySelector('.tab[data-tab="ask"]')?.click();
        }
      });
    });
  } catch (_) {
    els.sessionsList.innerHTML = `<div class="muted">Failed to load sessions</div>`;
  }
}

async function refreshHistory() {
  try {
    const { data } = await api("/api/history");
    if (!data.ok) return;
    const prompts = data.prompts || [];
    if (!prompts.length) {
      els.historyList.innerHTML = `<div class="muted">No recent prompts yet.</div>`;
      return;
    }
    els.historyList.innerHTML = prompts
      .map(
        (p) => `<div class="list-item history-item">
          <div class="title">${escapeHtml(p)}</div>
        </div>`
      )
      .join("");
    els.historyList.querySelectorAll(".history-item").forEach((item, idx) => {
      item.addEventListener("click", () => {
        els.prompt.value = prompts[idx];
        document.querySelector('.tab[data-tab="ask"]')?.click();
        els.prompt.focus();
      });
    });
  } catch (_) {
    els.historyList.innerHTML = `<div class="muted">Failed to load history</div>`;
  }
}

// Tabs
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    const name = tab.getAttribute("data-tab");
    $(`panel-${name}`)?.classList.add("active");
    if (name === "sessions") refreshSessions();
    if (name === "history") refreshHistory();
  });
});

els.sendBtn.addEventListener("click", sendPrompt);
els.sessionBtn.addEventListener("click", openSession);
els.askWindowBtn.addEventListener("click", askAboutWindow);
els.refreshContext.addEventListener("click", refreshContext);
els.refreshSessions?.addEventListener("click", refreshSessions);
els.refreshHistory?.addEventListener("click", refreshHistory);
els.clearResponse.addEventListener("click", () => {
  els.response.textContent = "Send a prompt or open a full Grok Build session.";
  els.response.classList.add("muted");
  els.response.dataset.userCleared = "1";
  delete els.response.dataset.hasContent;
});
els.includeShot.addEventListener("change", () => {
  if (els.includeShot.checked) refreshContext();
});
els.prompt.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    sendPrompt();
  }
});

// Init
loadConfig();
refreshStatus();
refreshContext();
refreshSessions();
refreshHistory();
setInterval(refreshStatus, 4000);
