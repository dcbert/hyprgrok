"""Local HTTP panel server for the glass UI."""

from __future__ import annotations

import json
import mimetypes
import os
import socket
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from hyprgrok import __version__
from hyprgrok.config import (
    PANEL_TITLE,
    Config,
    find_grok_binary,
    load_config,
    ui_root,
)
from hyprgrok.context import ask_about_window_prompt, gather_context, smart_launch_cwd
from hyprgrok import hypr as hypr_api
from hyprgrok.launcher import (
    grok_missing_message,
    launch_interactive_session,
    notify,
    run_headless_prompt,
)
from hyprgrok.runtime import (
    clear_runtime_files,
    is_server_alive,
    read_running_port,
    write_runtime_files,
)
from hyprgrok.session import SessionManager, load_prompt_history, push_prompt_history
from hyprgrok.status import build_status


class PanelState:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.sessions = SessionManager()
        self.lock = threading.Lock()
        self.last_response: str = ""
        self.last_error: str = ""
        self.busy: bool = False


def _json_response(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def make_handler(state: PanelState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)

            if path == "/api/status":
                grok = find_grok_binary(state.cfg.grok_binary)
                state.sessions.reaping_note()
                st = build_status()
                _json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "version": __version__,
                        "title": PANEL_TITLE,
                        "grok_found": bool(grok),
                        "grok_path": grok,
                        "busy": state.busy,
                        "last_response": state.last_response,
                        "last_error": state.last_error,
                        "missing_message": None if grok else grok_missing_message(),
                        "sessions_summary": state.sessions.summary(),
                        "waybar": st,
                    },
                )
                return

            if path == "/api/context":
                include_shot = "1" in qs.get("screenshot", []) or qs.get("screenshot") == ["true"]
                ctx = gather_context(include_screenshot=include_shot)
                _json_response(
                    self,
                    200,
                    {"ok": True, "context": ctx.to_dict(), "formatted": ctx.format_for_prompt()},
                )
                return

            if path == "/api/config":
                _json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "config": {
                            "panel": state.cfg.panel.__dict__,
                            "theme": state.cfg.theme.__dict__,
                            "auto_inject_context": state.cfg.panel.auto_inject_context,
                        },
                    },
                )
                return

            if path == "/api/sessions":
                limit = 30
                try:
                    limit = int(qs.get("limit", ["30"])[0])
                except ValueError:
                    pass
                _json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "sessions": state.sessions.list_recent(limit=limit),
                        "running": state.sessions.list_running(),
                        "summary": state.sessions.summary(),
                    },
                )
                return

            if path == "/api/history":
                _json_response(self, 200, {"ok": True, "prompts": load_prompt_history()})
                return

            if path == "/api/hypr/snapshot":
                _json_response(self, 200, {"ok": True, "snapshot": hypr_api.snapshot()})
                return

            if path == "/api/waybar":
                _json_response(self, 200, build_status())
                return

            if path in {"/", "/index.html"}:
                self._serve_file(ui_root() / "index.html")
                return

            if path.startswith("/"):
                rel = path.lstrip("/")
                candidate = (ui_root() / rel).resolve()
                if str(candidate).startswith(str(ui_root().resolve())) and candidate.is_file():
                    self._serve_file(candidate)
                    return

            _json_response(self, 404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            data = _read_json(self)

            if path == "/api/ask":
                self._handle_ask(data)
                return
            if path == "/api/session":
                self._handle_session(data)
                return
            if path == "/api/ask-about-window":
                self._handle_ask_about_window(data)
                return
            if path == "/api/session/stop":
                sid = str(data.get("id") or "")
                ok = state.sessions.stop(sid) if sid else False
                _json_response(self, 200, {"ok": ok, "id": sid})
                return
            if path == "/api/hide":
                _json_response(
                    self,
                    200,
                    {"ok": True, "message": "Close the panel window or press Super+G"},
                )
                return
            if path == "/api/reload-config":
                state.cfg = load_config()
                _json_response(self, 200, {"ok": True})
                return
            if path == "/api/hypr/dispatch":
                cmd = str(data.get("command") or "").strip()
                if not cmd:
                    _json_response(self, 400, {"ok": False, "error": "command required"})
                    return
                # Allowlist-ish: only common safe dispatches from panel
                allowed_prefixes = (
                    "focuswindow",
                    "closewindow",
                    "workspace",
                    "togglefloating",
                    "fullscreen",
                    "movefocus",
                    "cyclenext",
                )
                if not any(cmd.startswith(p) for p in allowed_prefixes):
                    _json_response(
                        self,
                        400,
                        {"ok": False, "error": f"dispatch not allowed from panel: {cmd}"},
                    )
                    return
                _json_response(self, 200, hypr_api.dispatch(cmd))
                return

            _json_response(self, 404, {"ok": False, "error": "not found"})

        def _handle_ask(self, data: dict[str, Any]) -> None:
            prompt = str(data.get("prompt") or "").strip()
            if not prompt:
                _json_response(self, 400, {"ok": False, "error": "prompt is required"})
                return

            inject = bool(data.get("inject_context", state.cfg.panel.auto_inject_context))
            include_shot = bool(data.get("screenshot", False))
            cwd = data.get("cwd")
            ctx = gather_context(include_screenshot=include_shot)
            workdir = str(cwd) if cwd else (ctx.project_root or ctx.cwd or os.getcwd())

            full_prompt = prompt
            if inject:
                full_prompt = f"{ctx.format_for_prompt()}\n\nUser request:\n{prompt}"

            with state.lock:
                if state.busy:
                    _json_response(self, 409, {"ok": False, "error": "already running a prompt"})
                    return
                state.busy = True
                state.last_error = ""

            push_prompt_history(prompt)
            record = state.sessions.add(
                kind="headless",
                cwd=workdir,
                prompt=prompt,
                status="running",
            )

            try:
                result = run_headless_prompt(state.cfg, full_prompt, cwd=workdir)
                if result.ok:
                    state.last_response = result.stdout or ""
                    state.last_error = ""
                    state.sessions.update(
                        record.id,
                        status="completed",
                        response_preview=state.last_response,
                    )
                    if state.cfg.notify_on_complete:
                        notify("HyprGrok", "Grok Build replied")
                    _json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "response": state.last_response,
                            "cwd": workdir,
                            "session_id": record.id,
                            "context_injected": inject,
                        },
                    )
                else:
                    state.last_error = result.message
                    body = result.stdout or result.message
                    state.sessions.update(
                        record.id,
                        status="failed",
                        error=result.message,
                        response_preview=body,
                    )
                    _json_response(
                        self,
                        200,
                        {
                            "ok": False,
                            "error": result.message,
                            "response": body,
                            "cwd": workdir,
                            "session_id": record.id,
                        },
                    )
            except Exception as exc:  # noqa: BLE001
                state.last_error = str(exc)
                state.sessions.update(record.id, status="failed", error=str(exc))
                _json_response(
                    self,
                    500,
                    {"ok": False, "error": str(exc), "trace": traceback.format_exc()},
                )
            finally:
                with state.lock:
                    state.busy = False

        def _handle_ask_about_window(self, data: dict[str, Any]) -> None:
            extra = str(data.get("prompt") or "").strip()
            full_prompt, ctx = ask_about_window_prompt(extra)
            workdir = ctx.project_root or ctx.cwd or os.getcwd()
            with state.lock:
                if state.busy:
                    _json_response(self, 409, {"ok": False, "error": "already running a prompt"})
                    return
                state.busy = True

            label = "Ask about current window"
            push_prompt_history(extra or label)
            record = state.sessions.add(
                kind="headless",
                cwd=workdir,
                prompt=extra or label,
                status="running",
                label=label,
            )
            try:
                result = run_headless_prompt(state.cfg, full_prompt, cwd=workdir)
                if result.ok:
                    state.last_response = result.stdout or ""
                    state.sessions.update(
                        record.id,
                        status="completed",
                        response_preview=state.last_response,
                    )
                    if state.cfg.notify_on_complete:
                        notify("HyprGrok", "Window analysis ready")
                    _json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "response": state.last_response,
                            "cwd": workdir,
                            "session_id": record.id,
                            "context": ctx.to_dict(),
                        },
                    )
                else:
                    body = result.stdout or result.message
                    state.sessions.update(
                        record.id,
                        status="failed",
                        error=result.message,
                        response_preview=body,
                    )
                    _json_response(
                        self,
                        200,
                        {"ok": False, "error": result.message, "response": body, "cwd": workdir},
                    )
            except Exception as exc:  # noqa: BLE001
                state.sessions.update(record.id, status="failed", error=str(exc))
                _json_response(self, 500, {"ok": False, "error": str(exc)})
            finally:
                with state.lock:
                    state.busy = False

        def _handle_session(self, data: dict[str, Any]) -> None:
            prompt = data.get("prompt")
            prompt_s = str(prompt).strip() if prompt else None
            cwd = data.get("cwd")
            workdir = str(cwd) if cwd else smart_launch_cwd()
            result = launch_interactive_session(state.cfg, cwd=workdir, prompt=prompt_s)
            if result.ok:
                state.sessions.add(
                    kind="interactive",
                    cwd=workdir,
                    prompt=prompt_s or "",
                    pid=result.pid,
                    status="running",
                    label=prompt_s or f"session @ {Path(workdir).name}",
                )
                if prompt_s:
                    push_prompt_history(prompt_s)
                _json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "message": result.message,
                        "cwd": workdir,
                        "pid": result.pid,
                        "command": result.command,
                    },
                )
            else:
                _json_response(self, 200, {"ok": False, "error": result.message, "cwd": workdir})

        def _serve_file(self, path: Path) -> None:
            try:
                data = path.read_bytes()
            except OSError:
                _json_response(self, 404, {"ok": False, "error": "file not found"})
                return
            ctype, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def port_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def start_server(cfg: Config | None = None, port: int | None = None) -> ThreadingHTTPServer:
    cfg = cfg or load_config()
    host = "127.0.0.1"
    chosen = port or cfg.panel.port
    if not port_available(chosen, host):
        for candidate in range(chosen, chosen + 50):
            if port_available(candidate, host):
                chosen = candidate
                break
        else:
            raise RuntimeError(f"No free port near {cfg.panel.port}")

    state = PanelState(cfg)
    handler = make_handler(state)
    server = ThreadingHTTPServer((host, chosen), handler)
    write_runtime_files(chosen)
    return server


def serve_forever(cfg: Config | None = None, port: int | None = None) -> int:
    server = start_server(cfg=cfg, port=port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        clear_runtime_files()
    return 0
