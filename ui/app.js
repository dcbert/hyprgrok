/* HyprGrok panel frontend — usability-focused copy */

const $ = (id) => document.getElementById(id);

const EMPTY_RESPONSE =
  "No answer yet.\n\n" +
  "• Type a question above → Get quick answer\n" +
  "• Need tools & multi-step work → Open full Grok session\n" +
  "• Curious about the focused app → Analyze focused window";

const CONTEXT_LABELS = {
  kind: "Type",
  title: "Window title",
  class: "App class",
  file: "Likely file",
  cwd: "Folder",
  project: "Project root",
  name: "Project name",
  workspace: "Workspace",
  shot: "Screenshot file",
};

const KIND_LABELS = {
  terminal: "Terminal",
  editor: "Code editor",
  browser: "Browser",
  other: "Other app",
  unknown: "Unknown",
};

const STATUS_LABELS = {
  running: "In progress",
  completed: "Done",
  failed: "Failed",
  stopped: "Stopped",
};

const KIND_HELP = {
  headless: "Quick answer (in panel)",
  interactive: "Full terminal session",
};

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
  responseHint: $("responseHint"),
};

let currentCwd = null;
let busy = false;
let lastResponseBySession = {};

function toast(msg, isError = false) {
  els.toast.textContent = msg;
  els.toast.classList.toggle("error", isError);
  els.toast.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => els.toast.classList.add("hidden"), 3600);
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

function setBusy(on, phase = "Working with Grok Build…") {
  busy = on;
  [els.sendBtn, els.sessionBtn, els.askWindowBtn].forEach((b) => {
    if (b) b.disabled = on;
  });
  els.sendSpinner.classList.toggle("hidden", !on);
  const label = els.sendBtn.querySelector(".btn-label");
  if (label) label.textContent = on ? "Waiting for Grok…" : "Get quick answer";
  if (on) {
    els.statusPill.textContent = "Working…";
    els.statusPill.className = "status-pill busy";
    els.statusPill.title = phase;
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
    els.contextBody.innerHTML = `<div class="empty-block">Could not read the active window. Is Hyprland running?</div>`;
    return;
  }
  currentCwd = ctx.project_root || ctx.cwd || null;
  if (els.cwdLabel) {
    els.cwdLabel.textContent = currentCwd
      ? `Grok will start in: ${currentCwd}`
      : "No project folder detected — Grok uses the current directory.";
  }

  const kindNice = KIND_LABELS[ctx.kind] || ctx.kind || "Unknown";
  const rows = [
    ["kind", kindNice],
    ["title", ctx.window_title],
    ["class", ctx.window_class],
    ["file", ctx.file_hint],
    ["cwd", ctx.cwd],
    ["project", ctx.project_root],
    ["name", ctx.project_name],
    ["workspace", ctx.workspace],
    ["shot", ctx.screenshot_path],
  ].filter(([, v]) => v);

  if (!rows.length) {
    els.contextBody.innerHTML = `<div class="empty-block">No window details yet. Focus a terminal or editor, then hit Refresh.</div>`;
    return;
  }

  els.contextBody.innerHTML = rows
    .map(([k, v]) => {
      const label = CONTEXT_LABELS[k] || k;
      return `<div class="ctx-row" title="${escapeHtml(label)}">
        <span class="k">${escapeHtml(label)}</span>
        <span class="v">${escapeHtml(String(v))}</span>
      </div>`;
    })
    .join("");
}

function setEmptyResponse() {
  els.response.textContent = EMPTY_RESPONSE;
  els.response.classList.add("muted", "empty-state");
  els.response.dataset.userCleared = "1";
  delete els.response.dataset.hasContent;
  if (els.responseHint) {
    els.responseHint.textContent =
      "Shows up after a quick answer or window analysis. Full sessions open in a separate terminal.";
  }
}

function showResponse(text, mode = "answer") {
  els.response.classList.remove("muted", "empty-state");
  els.response.textContent = text || "(Grok returned an empty reply.)";
  els.response.dataset.hasContent = "1";
  delete els.response.dataset.userCleared;
  if (els.responseHint) {
    if (mode === "waiting") {
      els.responseHint.textContent = "Grok Build is working — this can take a bit for complex prompts.";
    } else if (mode === "error") {
      els.responseHint.textContent = "Something went wrong. Check that grok is installed and you’re signed in.";
    } else {
      els.responseHint.textContent = "Reply from a quick headless run (grok -p). For multi-step work, open a full session.";
    }
  }
}

async function refreshStatus() {
  try {
    const { data } = await api("/api/status");
    if (!data.ok) return;
    if (data.version && els.verLabel) els.verLabel.textContent = data.version;

    if (data.missing_message) {
      els.missingBanner.innerHTML = `<strong>Grok Build is not installed (or not on PATH).</strong><br>${escapeHtml(
        data.missing_message
      )}`;
      els.missingBanner.classList.remove("hidden");
    } else {
      els.missingBanner.classList.add("hidden");
    }

    if (busy) return;

    const run = data.sessions_summary?.running || 0;
    if (data.grok_found) {
      if (run > 0) {
        els.statusPill.textContent = run === 1 ? "1 session open" : `${run} sessions open`;
        els.statusPill.title = "Interactive or in-progress Grok work tracked by HyprGrok";
      } else {
        els.statusPill.textContent = "Ready";
        els.statusPill.title = `Official grok found at ${data.grok_path || "PATH"}`;
      }
      els.statusPill.className = "status-pill ok";
    } else {
      els.statusPill.textContent = "Grok missing";
      els.statusPill.className = "status-pill bad";
      els.statusPill.title = "Install the official Grok Build CLI, then reopen this panel";
      if (!els.response.dataset.hasContent) {
        showResponse(data.missing_message || "Install Grok Build (`grok`) to use this panel.", "error");
      }
    }
  } catch (_) {
    els.statusPill.textContent = "Panel offline";
    els.statusPill.className = "status-pill bad";
    els.statusPill.title = "Cannot reach the local HyprGrok server";
  }
}

async function refreshContext() {
  const shot = els.includeShot.checked ? "?screenshot=1" : "";
  try {
    const { data } = await api(`/api/context${shot}`);
    if (data.ok) renderContext(data.context);
  } catch (_) {
    els.contextBody.innerHTML = `<div class="empty-block">Could not load desktop context.</div>`;
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

async function sendPrompt() {
  const prompt = els.prompt.value.trim();
  if (!prompt) {
    toast("Write a question first", true);
    els.prompt.focus();
    return;
  }
  setBusy(true, "Sending quick answer request to grok -p…");
  showResponse("Waiting for Grok Build…\n\nThis is a single-turn request. The reply will appear here.", "waiting");
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
      showResponse(data.response || "(empty response)", "answer");
      if (data.session_id) lastResponseBySession[data.session_id] = data.response;
      const bits = [];
      if (data.context_injected) bits.push("with desktop context");
      toast(bits.length ? `Answer ready (${bits.join(", ")})` : "Answer ready");
      refreshHistory();
      refreshSessions();
    } else {
      showResponse(data.response || data.error || "Request failed", "error");
      toast(data.error || "Quick answer failed", true);
    }
  } catch (e) {
    showResponse(String(e), "error");
    toast("Could not reach HyprGrok server", true);
  } finally {
    setBusy(false);
    refreshStatus();
  }
}

async function openSession() {
  setBusy(true, "Launching interactive Grok Build in your terminal…");
  try {
    const prompt = els.prompt.value.trim() || null;
    const { data } = await api("/api/session", {
      method: "POST",
      body: JSON.stringify({ prompt, cwd: currentCwd }),
    });
    if (data.ok) {
      toast(data.message || "Full session opened in a terminal");
      showResponse(
        "Full Grok Build session launched in a new terminal window.\n\n" +
          `Folder: ${data.cwd || currentCwd || "(default)"}\n\n` +
          "Continue the conversation there. This panel stays free for quick asks.\n" +
          "Track it under the Sessions tab.",
        "answer"
      );
      refreshSessions();
      document.querySelector('.tab[data-tab="sessions"]')?.click();
    } else {
      toast(data.error || "Could not open session", true);
      showResponse(data.error || "Failed to open full session", "error");
    }
  } catch (e) {
    toast(String(e), true);
  } finally {
    setBusy(false);
    refreshStatus();
  }
}

async function askAboutWindow() {
  setBusy(true, "Capturing focused window and asking Grok…");
  showResponse(
    "Capturing the focused window (title, folder, screenshot) and asking Grok to analyze it…",
    "waiting"
  );
  try {
    const extra = els.prompt.value.trim();
    const { data } = await api("/api/ask-about-window", {
      method: "POST",
      body: JSON.stringify({ prompt: extra }),
    });
    if (data.ok) {
      showResponse(data.response || "(empty response)", "answer");
      if (data.context) renderContext(data.context);
      toast("Window analysis ready");
      refreshSessions();
      refreshHistory();
    } else {
      showResponse(data.response || data.error || "Failed", "error");
      toast(data.error || "Window analysis failed", true);
    }
  } catch (e) {
    showResponse(String(e), "error");
    toast("Could not reach HyprGrok server", true);
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
      els.sessionsList.innerHTML = `<div class="empty-block">
        <strong>No activity yet</strong>
        <p>Send a <em>quick answer</em> or open a <em>full Grok session</em> from the Ask tab. They’ll show up here.</p>
      </div>`;
      return;
    }
    els.sessionsList.innerHTML = sessions
      .map((s) => {
        const title = escapeHtml(s.label || s.prompt || s.kind);
        const status = s.status || "";
        const statusLabel = STATUS_LABELS[status] || status;
        const kindHelp = KIND_HELP[s.kind] || s.kind || "";
        const cwd = escapeHtml(s.cwd || "");
        const preview = escapeHtml((s.response_preview || s.error || "").slice(0, 160));
        const stopBtn =
          s.status === "running" && s.kind === "interactive"
            ? `<button type="button" class="secondary stop-btn" data-id="${escapeHtml(
                s.id
              )}" title="Send stop to the terminal session process">Stop session</button>`
            : "";
        const reuseBtn = s.prompt
          ? `<button type="button" class="secondary reuse-btn" data-prompt="${escapeHtml(
              s.prompt
            )}" title="Copy this prompt back into the Ask box">Use prompt again</button>`
          : "";
        const clickHint =
          s.response_preview && s.kind === "headless"
            ? "Click to show this answer in Ask"
            : "";
        return `<div class="list-item" data-id="${escapeHtml(s.id)}" title="${escapeHtml(clickHint)}">
          <div class="title">${title}</div>
          <div class="meta">
            <span>
              <span class="badge ${escapeHtml(status)}">${escapeHtml(statusLabel)}</span>
              · ${escapeHtml(kindHelp)}
              · ${timeAgo(s.created_at)}
            </span>
            <span title="Working directory">${cwd}</span>
          </div>
          ${preview ? `<div class="preview muted">${preview}</div>` : ""}
          <div class="item-actions">${reuseBtn}${stopBtn}</div>
        </div>`;
      })
      .join("");

    els.sessionsList.querySelectorAll(".stop-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute("data-id");
        await api("/api/session/stop", { method: "POST", body: JSON.stringify({ id }) });
        toast("Stop signal sent to that session");
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
        toast("Prompt loaded — edit if you want, then Get quick answer");
      });
    });
    els.sessionsList.querySelectorAll(".list-item").forEach((item) => {
      item.addEventListener("click", () => {
        const id = item.getAttribute("data-id");
        const s = sessions.find((x) => x.id === id);
        if (!s) return;
        if (s.response_preview) {
          showResponse(s.response_preview, s.status === "failed" ? "error" : "answer");
          document.querySelector('.tab[data-tab="ask"]')?.click();
          toast("Showing saved answer");
        } else if (s.kind === "interactive") {
          toast("That was a full terminal session — continue in the terminal window", false);
        }
      });
    });
  } catch (_) {
    els.sessionsList.innerHTML = `<div class="empty-block">Could not load sessions.</div>`;
  }
}

async function refreshHistory() {
  try {
    const { data } = await api("/api/history");
    if (!data.ok) return;
    const prompts = data.prompts || [];
    if (!prompts.length) {
      els.historyList.innerHTML = `<div class="empty-block">
        <strong>No saved prompts yet</strong>
        <p>After you send a quick answer or analyze a window, the prompt text is remembered here for reuse.</p>
      </div>`;
      return;
    }
    els.historyList.innerHTML = prompts
      .map(
        (p) => `<div class="list-item history-item" title="Click to load into Ask">
          <div class="title">${escapeHtml(p)}</div>
          <div class="meta"><span class="muted">Click to edit &amp; send again</span></div>
        </div>`
      )
      .join("");
    els.historyList.querySelectorAll(".history-item").forEach((item, idx) => {
      item.addEventListener("click", () => {
        els.prompt.value = prompts[idx];
        document.querySelector('.tab[data-tab="ask"]')?.click();
        els.prompt.focus();
        toast("Prompt loaded into Ask");
      });
    });
  } catch (_) {
    els.historyList.innerHTML = `<div class="empty-block">Could not load history.</div>`;
  }
}

// Tabs
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.remove("active");
      t.setAttribute("aria-selected", "false");
    });
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    tab.setAttribute("aria-selected", "true");
    const name = tab.getAttribute("data-tab");
    $(`panel-${name}`)?.classList.add("active");
    if (name === "sessions") refreshSessions();
    if (name === "history") refreshHistory();
  });
});

els.sendBtn.addEventListener("click", sendPrompt);
els.sessionBtn.addEventListener("click", openSession);
els.askWindowBtn.addEventListener("click", askAboutWindow);
els.refreshContext.addEventListener("click", () => {
  refreshContext();
  toast("Desktop context refreshed");
});
els.refreshSessions?.addEventListener("click", refreshSessions);
els.refreshHistory?.addEventListener("click", refreshHistory);
els.clearResponse.addEventListener("click", () => {
  setEmptyResponse();
  toast("Answer cleared");
});
els.includeShot.addEventListener("change", () => {
  if (els.includeShot.checked) {
    refreshContext();
    toast("Screenshot will be captured with the next quick answer / analysis");
  }
});
els.prompt.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    sendPrompt();
  }
});

// Init
setEmptyResponse();
loadConfig();
refreshStatus();
refreshContext();
refreshSessions();
refreshHistory();
setInterval(refreshStatus, 4000);
