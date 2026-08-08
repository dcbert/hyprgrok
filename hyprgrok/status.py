"""Machine-readable status for Waybar / Quickshell / scripts."""

from __future__ import annotations

import json
from typing import Any

from hyprgrok import __version__
from hyprgrok.config import find_grok_binary, load_config
from hyprgrok.runtime import is_server_alive, read_running_port
from hyprgrok.session import SessionManager


def build_status() -> dict[str, Any]:
    from hyprgrok import grok_store

    cfg = load_config()
    sessions = SessionManager()
    summary = sessions.summary()
    grok = find_grok_binary(cfg.grok_binary)
    server = is_server_alive()
    port = read_running_port() if server else None

    # Prefer live Grok Build processes from ~/.grok/active_sessions.json
    active_map = grok_store.load_active_sessions()
    grok_active = sum(1 for v in active_map.values() if v.get("alive"))
    running = max(summary["running"], grok_active)

    text = "Grok"
    if not grok:
        text = "Grok?"
        css = "missing"
        tooltip = "Grok Build CLI not found"
    elif running:
        text = f"Grok {running}"
        css = "active"
        tooltip = f"{running} Grok Build session(s) open"
    elif server:
        text = "Grok"
        css = "idle"
        tooltip = f"Panel server on :{port}"
    else:
        text = "Grok"
        css = "idle"
        tooltip = "HyprGrok idle — Super+G to open"

    store = grok_store.store_summary()
    return {
        "text": text,
        "alt": css,
        "tooltip": tooltip,
        "class": css,
        "percentage": min(100, running * 20),
        "version": __version__,
        "grok_found": bool(grok),
        "panel_running": server,
        "panel_port": port,
        "sessions": {
            **summary,
            "grok_active": grok_active,
            "grok_total": store.get("total_sessions", 0),
        },
    }


def waybar_json() -> str:
    return json.dumps(build_status(), ensure_ascii=False)
