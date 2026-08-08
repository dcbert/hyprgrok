"""CLI entrypoint for HyprGrok."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from hyprgrok import __app_name__, __version__
from hyprgrok.config import (
    CONFIG_DIR,
    CONFIG_PATH,
    PANEL_TITLE,
    Config,
    ensure_dirs,
    find_grok_binary,
    load_config,
    package_root,
    write_default_config,
)
from hyprgrok.context import ask_about_window_prompt, gather_context, smart_launch_cwd
from hyprgrok.launcher import (
    grok_missing_message,
    launch_interactive_session,
    notify,
    run_headless_prompt,
)
from hyprgrok.panel_server import serve_forever
from hyprgrok.runtime import clear_runtime_files, is_server_alive, read_running_port
from hyprgrok.session import SessionManager, load_prompt_history
from hyprgrok.status import build_status, waybar_json


def _http_json(method: str, url: str, payload: dict | None = None, timeout: float = 600.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_browser(preferred: str = "auto") -> str | None:
    if preferred and preferred != "auto":
        if shutil.which(preferred) or Path(preferred).expanduser().is_file():
            return preferred
    for name in (
        "google-chrome-stable",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "brave",
        "brave-browser",
        "microsoft-edge-stable",
        "firefox",
    ):
        if shutil.which(name):
            return name
    return None


def _hypr_clients() -> list[dict]:
    if not shutil.which("hyprctl"):
        return []
    try:
        out = subprocess.run(
            ["hyprctl", "clients", "-j"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0 or not out.stdout.strip():
        return []
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def is_panel_client(client: dict) -> bool:
    """True only for the HyprGrok glass panel — not Code/kitty with 'HyprGrok' in the title."""
    title = str(client.get("title") or "").strip()
    initial = str(client.get("initialTitle") or "").strip()
    klass = str(client.get("class") or "").lower()
    initial_class = str(client.get("initialClass") or "").lower()

    # Exact panel title from <title>HyprGrok</title>
    if title == PANEL_TITLE or initial == PANEL_TITLE:
        return True
    # Chromium --class=hyprgrok-panel (if honored)
    if "hyprgrok-panel" in klass or "hyprgrok-panel" in initial_class:
        return True
    # Do NOT match "Preview README.md - HyprGrok - Code" or "…/HyprGrok" terminals
    return False


def find_panel_clients() -> list[dict]:
    return [c for c in _hypr_clients() if is_panel_client(c)]


def focus_panel_window() -> bool:
    panels = find_panel_clients()
    if not panels:
        return False
    addr = str(panels[0].get("address") or "")
    if not addr:
        return False
    try:
        subprocess.run(
            ["hyprctl", "dispatch", "focuswindow", f"address:{addr}"],
            capture_output=True,
            timeout=2,
            check=False,
        )
        # Bring to current workspace if needed
        subprocess.run(
            ["hyprctl", "dispatch", "alterzorder", "top", f"address:{addr}"],
            capture_output=True,
            timeout=2,
            check=False,
        )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def open_panel_window(port: int, browser: str | None, cfg: Config | None = None) -> bool:
    # If panel already exists, just focus it
    if find_panel_clients():
        return focus_panel_window()

    url = f"http://127.0.0.1:{port}/"
    profile = CONFIG_DIR / "browser-profile"
    profile.mkdir(parents=True, exist_ok=True)
    cfg = cfg or load_config()

    if browser:
        name = Path(browser).name
        if "firefox" in name:
            cmd = [browser, "--new-window", url]
        else:
            # Chromium family app window — title comes from page <title>
            # Explicit size avoids half-empty Chrome app surfaces on wide monitors
            w = max(480, int(cfg.panel.width or 560))
            h = max(720, int(cfg.panel.height or 980))
            cmd = [
                browser,
                f"--app={url}",
                f"--user-data-dir={profile}",
                f"--window-size={w},{h}",
                "--no-first-run",
                "--disable-extensions",
                f"--class={__app_name__}-panel",
                f"--name={__app_name__}-panel",
            ]
        try:
            subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait briefly for window, then focus
            for _ in range(20):
                time.sleep(0.1)
                if find_panel_clients():
                    focus_panel_window()
                    break
            return True
        except OSError:
            pass

    if shutil.which("xdg-open"):
        try:
            subprocess.Popen(
                ["xdg-open", url],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except OSError:
            pass
    return False


def panel_window_open() -> bool:
    """True if the glass panel window is mapped (exact match only)."""
    return bool(find_panel_clients())


def close_panel_window() -> bool:
    panels = find_panel_clients()
    if not panels:
        return False
    ok = False
    for client in panels:
        addr = str(client.get("address") or "")
        if not addr:
            continue
        try:
            subprocess.run(
                ["hyprctl", "dispatch", "closewindow", f"address:{addr}"],
                capture_output=True,
                timeout=2,
                check=False,
            )
            ok = True
        except (OSError, subprocess.TimeoutExpired):
            pass
    return ok


def ensure_server_running(cfg=None) -> int:
    cfg = cfg or load_config()
    if is_server_alive():
        port = read_running_port()
        return port or cfg.panel.port

    # Start server in background (-P: don't put cwd ahead of package on sys.path)
    python = sys.executable
    env = os.environ.copy()
    env["PYTHONPATH"] = str(package_root()) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    log = CONFIG_DIR / "panel.log"
    ensure_dirs()
    serve_cmd = [python, "-P", "-m", "hyprgrok", "serve"]
    # Older Python without -P still works via plain -m
    try:
        subprocess.run([python, "-P", "-c", "pass"], capture_output=True, check=True, timeout=2)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
        serve_cmd = [python, "-m", "hyprgrok", "serve"]
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n--- starting panel server {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        proc = subprocess.Popen(
            serve_cmd,
            cwd=str(package_root()),
            env=env,
            start_new_session=True,
            stdout=fh,
            stderr=fh,
        )
    # Wait for readiness
    for _ in range(50):
        time.sleep(0.1)
        if is_server_alive():
            port = read_running_port()
            if port:
                return port
    raise RuntimeError(f"Panel server failed to start (pid={proc.pid}). See {log}")


def cmd_toggle(_args: argparse.Namespace) -> int:
    cfg = load_config()
    browser = find_browser(cfg.panel.browser)

    # Exact panel window only (not Code/kitty with "HyprGrok" in the title)
    if panel_window_open():
        close_panel_window()
        return 0

    try:
        port = ensure_server_running(cfg)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        if shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", "--app-name=HyprGrok", "HyprGrok", str(exc)],
                check=False,
                capture_output=True,
            )
        return 1

    if not open_panel_window(port, browser, cfg=cfg):
        msg = f"Panel server is on http://127.0.0.1:{port}/ but no browser opened"
        print(msg, file=sys.stderr)
        if shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", "--app-name=HyprGrok", "HyprGrok", msg],
                check=False,
                capture_output=True,
            )
        return 1
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    cfg = load_config()
    port = args.port or cfg.panel.port

    def _cleanup(signum, frame):  # noqa: ANN001, ARG001
        clear_runtime_files()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)
    print(f"HyprGrok panel server on http://127.0.0.1:{port}/", flush=True)
    return serve_forever(cfg=cfg, port=port)


def cmd_ask(args: argparse.Namespace) -> int:
    cfg = load_config()
    prompt = args.prompt
    if not prompt:
        print("Prompt required", file=sys.stderr)
        return 2

    ctx = gather_context(include_screenshot=bool(args.screenshot))
    workdir = args.cwd or ctx.project_root or ctx.cwd or os.getcwd()
    full = prompt
    if args.context or cfg.panel.auto_inject_context:
        full = f"{ctx.format_for_prompt()}\n\nUser request:\n{prompt}"

    # Prefer local server if running (keeps history); else direct headless
    if is_server_alive() and not args.direct:
        port = read_running_port()
        try:
            result = _http_json(
                "POST",
                f"http://127.0.0.1:{port}/api/ask",
                {
                    "prompt": prompt,
                    "inject_context": bool(args.context or cfg.panel.auto_inject_context),
                    "screenshot": bool(args.screenshot),
                    "cwd": workdir,
                },
                timeout=cfg.launch.headless_timeout_sec + 30,
            )
            if result.get("ok"):
                print(result.get("response") or "")
                return 0
            print(result.get("error") or result.get("response") or "failed", file=sys.stderr)
            return 1
        except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            print(f"Panel server ask failed ({exc}); falling back to direct.", file=sys.stderr)

    result = run_headless_prompt(cfg, full, cwd=workdir)
    if result.ok:
        print(result.stdout or "")
        if cfg.notify_on_complete:
            notify("HyprGrok", "Done")
        return 0
    print(result.message, file=sys.stderr)
    if result.stdout:
        print(result.stdout, file=sys.stderr)
    return 1


def cmd_session(args: argparse.Namespace) -> int:
    cfg = load_config()
    workdir = args.cwd or smart_launch_cwd()
    result = launch_interactive_session(cfg, cwd=workdir, prompt=args.prompt)
    if result.ok:
        print(result.message)
        return 0
    print(result.message, file=sys.stderr)
    return 1


def cmd_context(args: argparse.Namespace) -> int:
    ctx = gather_context(include_screenshot=bool(args.screenshot))
    if args.json:
        print(json.dumps(ctx.to_dict(), indent=2))
    else:
        print(ctx.format_for_prompt())
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    cfg = load_config()
    print(f"HyprGrok {__version__}")
    print(f"Config: {CONFIG_PATH} ({'exists' if CONFIG_PATH.is_file() else 'missing — will create defaults'})")
    print(f"Package root: {package_root()}")

    checks = [
        ("python", sys.executable),
        ("hyprctl", shutil.which("hyprctl")),
        ("grim", shutil.which("grim")),
        ("jq", shutil.which("jq")),
        ("notify-send", shutil.which("notify-send")),
    ]
    grok = find_grok_binary(cfg.grok_binary)
    checks.append(("grok", grok))
    browser = find_browser(cfg.panel.browser)
    checks.append(("browser", browser))

    from hyprgrok.launcher import resolve_terminal

    terminal = resolve_terminal(cfg)
    checks.append(("terminal", terminal))

    worst = 0
    for name, value in checks:
        ok = bool(value)
        if name == "grok" and not ok:
            worst = 1
        status = "ok" if ok else "MISSING"
        print(f"  [{status}] {name}: {value or '—'}")

    if not grok:
        print()
        print(grok_missing_message())

    if is_server_alive():
        print(f"Panel server: running on port {read_running_port()}")
    else:
        print("Panel server: not running")

    return worst


def cmd_init(_args: argparse.Namespace) -> int:
    path = write_default_config(force=False)
    print(f"Config ready at {path}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    if args.waybar:
        print(waybar_json())
        return 0
    data = build_status()
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"HyprGrok {data.get('version')}")
        print(f"  grok: {'found' if data.get('grok_found') else 'MISSING'}")
        print(f"  panel: {'running :' + str(data.get('panel_port')) if data.get('panel_running') else 'stopped'}")
        s = data.get("sessions") or {}
        print(f"  sessions: {s.get('running', 0)} running / {s.get('total', 0)} total")
        print(f"  waybar text: {data.get('text')} ({data.get('class')})")
    return 0 if data.get("grok_found") else 1


def cmd_sessions(args: argparse.Namespace) -> int:
    from hyprgrok import grok_store

    if args.stop:
        mgr = SessionManager()
        ok = mgr.stop(args.stop)
        print("stopped" if ok else "could not stop (missing pid or already dead)")
        return 0 if ok else 1
    if args.resume:
        cfg = load_config()
        detail = grok_store.get_session(args.resume)
        workdir = args.cwd or (detail or {}).get("cwd") or smart_launch_cwd()
        result = launch_interactive_session(cfg, cwd=workdir, resume=args.resume)
        print(result.message)
        return 0 if result.ok else 1

    if args.panel_only:
        mgr = SessionManager()
        rows = mgr.list_running() if args.running else mgr.list_recent(limit=args.limit)
    elif args.q:
        rows = grok_store.search_sessions(args.q, limit=args.limit)
    else:
        rows = grok_store.list_sessions(limit=args.limit, include_first_prompt=True, include_todos=False)
        if args.running:
            rows = [r for r in rows if r.get("active")]

    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("(no Grok Build sessions under ~/.grok/sessions)")
        return 0
    for s in rows:
        # Grok store shape
        if "title" in s or s.get("source") == "grok-build":
            flag = "●" if s.get("active") else "○"
            print(
                f"{flag} {str(s.get('id', ''))[:8]}  {(s.get('title') or '')[:48]:48}  "
                f"{(s.get('cwd') or '')[:40]}"
            )
        else:
            pid = s.get("pid") or "-"
            print(
                f"{s.get('id', '')[:8]}  {s.get('status'):10}  {s.get('kind'):12}  "
                f"pid={pid}  {s.get('label') or s.get('prompt', '')[:50]}"
            )
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    from hyprgrok import grok_store

    if args.panel_only:
        items = load_prompt_history(limit=args.limit)
        rows = [{"prompt": p, "source": "hyprgrok"} for p in items]
    else:
        rows = grok_store.list_prompt_history(limit=args.limit, cwd_filter=args.cwd)
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("(no prompt history in ~/.grok/sessions)")
        return 0
    for i, p in enumerate(rows, 1):
        text = p.get("prompt", p) if isinstance(p, dict) else p
        cwd = (p.get("cwd") if isinstance(p, dict) else "") or ""
        print(f"{i:2}. {str(text)[:100]}")
        if cwd:
            print(f"    @ {cwd}")
    return 0


def cmd_ask_window(args: argparse.Namespace) -> int:
    cfg = load_config()
    extra = args.prompt or ""
    full, ctx = ask_about_window_prompt(extra)
    workdir = args.cwd or ctx.project_root or ctx.cwd or os.getcwd()
    if args.print_only:
        print(full)
        return 0
    result = run_headless_prompt(cfg, full, cwd=workdir)
    if result.ok:
        print(result.stdout or "")
        return 0
    print(result.message, file=sys.stderr)
    if result.stdout:
        print(result.stdout, file=sys.stderr)
    return 1


def cmd_hypr(args: argparse.Namespace) -> int:
    from hyprgrok import hypr as hypr_api

    if args.action == "snapshot":
        print(json.dumps(hypr_api.snapshot(), indent=2))
        return 0
    if args.action == "clients":
        print(json.dumps(hypr_api.clients(), indent=2))
        return 0
    if args.action == "reload":
        out = hypr_api.reload()
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1
    if args.action == "dispatch":
        if not args.command:
            print("dispatch requires --command", file=sys.stderr)
            return 2
        out = hypr_api.dispatch(args.command)
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1
    print(f"unknown hypr action: {args.action}", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description="Hyprland companion panel for official Grok Build (never calls xAI API directly).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_toggle = sub.add_parser("toggle", help="Toggle the glass panel (default action)")
    p_toggle.set_defaults(func=cmd_toggle)

    p_serve = sub.add_parser("serve", help="Run the local panel HTTP server in the foreground")
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.set_defaults(func=cmd_serve)

    p_ask = sub.add_parser("ask", help="Send a quick prompt to Grok Build (headless -p)")
    p_ask.add_argument("prompt", help="Prompt text")
    p_ask.add_argument("--context", "-c", action="store_true", help="Inject desktop context")
    p_ask.add_argument("--screenshot", action="store_true", help="Include grim screenshot path in context")
    p_ask.add_argument("--cwd", help="Working directory for Grok Build")
    p_ask.add_argument("--direct", action="store_true", help="Bypass panel server")
    p_ask.set_defaults(func=cmd_ask)

    p_session = sub.add_parser("session", help="Launch a full interactive Grok Build session")
    p_session.add_argument("prompt", nargs="?", default=None, help="Optional initial prompt")
    p_session.add_argument("--cwd", help="Working directory / project folder")
    p_session.set_defaults(func=cmd_session)

    p_ctx = sub.add_parser("context", help="Print current desktop context")
    p_ctx.add_argument("--json", action="store_true")
    p_ctx.add_argument("--screenshot", action="store_true")
    p_ctx.set_defaults(func=cmd_context)

    p_doc = sub.add_parser("doctor", help="Check dependencies and Grok Build availability")
    p_doc.set_defaults(func=cmd_doctor)

    p_init = sub.add_parser("init", help="Create default config under ~/.config/hyprgrok/")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="Status for humans or Waybar")
    p_status.add_argument("--json", action="store_true")
    p_status.add_argument("--waybar", action="store_true", help="Waybar custom module JSON")
    p_status.set_defaults(func=cmd_status)

    p_sessions = sub.add_parser("sessions", help="List / resume Grok Build sessions from ~/.grok")
    p_sessions.add_argument("--json", action="store_true")
    p_sessions.add_argument("--running", action="store_true", help="Only active (open) sessions")
    p_sessions.add_argument("--limit", type=int, default=20)
    p_sessions.add_argument("-q", "--query", dest="q", help="Search titles/prompts")
    p_sessions.add_argument("--resume", metavar="ID", help="Resume session in a terminal")
    p_sessions.add_argument("--cwd", help="Working directory for resume")
    p_sessions.add_argument("--panel-only", action="store_true", help="Only HyprGrok panel activity log")
    p_sessions.add_argument("--stop", metavar="ID", help="Stop panel-tracked process by id")
    p_sessions.set_defaults(func=cmd_sessions)

    p_hist = sub.add_parser("history", help="Recent prompts from Grok Build (~/.grok)")
    p_hist.add_argument("--json", action="store_true")
    p_hist.add_argument("--limit", type=int, default=30)
    p_hist.add_argument("--cwd", help="Filter to a project folder")
    p_hist.add_argument("--panel-only", action="store_true", help="Only HyprGrok local history")
    p_hist.set_defaults(func=cmd_history)

    p_aw = sub.add_parser("ask-window", help="Analyze the focused window with Grok Build")
    p_aw.add_argument("prompt", nargs="?", default=None, help="Optional extra instruction")
    p_aw.add_argument("--cwd", help="Working directory")
    p_aw.add_argument("--print-only", action="store_true", help="Print assembled prompt only")
    p_aw.set_defaults(func=cmd_ask_window)

    p_hypr = sub.add_parser("hypr", help="Hyprland helpers (hyprctl wrappers)")
    p_hypr.add_argument(
        "action",
        choices=["snapshot", "clients", "reload", "dispatch"],
        help="Action to run",
    )
    p_hypr.add_argument("--command", help="For dispatch: e.g. 'workspace 2'")
    p_hypr.set_defaults(func=cmd_hypr)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        # Default: toggle panel
        return cmd_toggle(argparse.Namespace())
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
