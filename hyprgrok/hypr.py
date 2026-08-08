"""Hyprland control helpers (safe wrappers around hyprctl).

These can be used by HyprGrok itself and later exposed to Grok Build via MCP
or custom tools. They never touch xAI credentials.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


def available() -> bool:
    return bool(shutil.which("hyprctl"))


def _run(args: list[str], timeout: float = 3.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["hyprctl", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def dispatch(command: str) -> dict[str, Any]:
    if not available():
        return {"ok": False, "error": "hyprctl not found"}
    try:
        result = _run(["dispatch", command])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": result.returncode == 0,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
        "command": command,
    }


def clients() -> list[dict[str, Any]]:
    if not available():
        return []
    try:
        result = _run(["clients", "-j"])
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout or "[]")
        return data if isinstance(data, list) else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def workspaces() -> list[dict[str, Any]]:
    if not available():
        return []
    try:
        result = _run(["workspaces", "-j"])
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout or "[]")
        return data if isinstance(data, list) else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def active_workspace() -> dict[str, Any] | None:
    if not available():
        return None
    try:
        result = _run(["activeworkspace", "-j"])
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout or "{}")
        return data if isinstance(data, dict) else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def focus_window(address: str) -> dict[str, Any]:
    address = address.strip()
    if not address:
        return {"ok": False, "error": "address required"}
    if not address.startswith("address:"):
        address = f"address:{address}"
    return dispatch(f"focuswindow {address}")


def close_window(matcher: str) -> dict[str, Any]:
    return dispatch(f"closewindow {matcher}")


def reload() -> dict[str, Any]:
    if not available():
        return {"ok": False, "error": "hyprctl not found"}
    try:
        result = _run(["reload"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": result.returncode == 0, "stdout": (result.stdout or "").strip()}


def keyword(key: str, value: str) -> dict[str, Any]:
    if not available():
        return {"ok": False, "error": "hyprctl not found"}
    try:
        result = _run(["keyword", key, value])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": result.returncode == 0,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
    }


def snapshot() -> dict[str, Any]:
    """Compact desktop snapshot for tools / MCP later."""
    from hyprgrok.context import gather_context

    ctx = gather_context(include_screenshot=False)
    return {
        "active": ctx.to_dict(),
        "workspace": active_workspace(),
        "client_count": len(clients()),
        "workspaces": [
            {
                "id": w.get("id"),
                "name": w.get("name"),
                "windows": w.get("windows"),
            }
            for w in workspaces()
        ],
    }
