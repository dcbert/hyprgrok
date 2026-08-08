"""Launch interactive and headless Grok Build sessions."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from hyprgrok.config import Config, find_grok_binary


@dataclass
class LaunchResult:
    ok: bool
    message: str
    command: list[str] | None = None
    pid: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    returncode: int | None = None


def resolve_terminal(cfg: Config) -> str | None:
    preferred = cfg.launch.terminal
    if preferred and preferred != "auto":
        if shutil.which(preferred) or Path(preferred).expanduser().is_file():
            return preferred
    for name in cfg.launch.preferred_terminals:
        if shutil.which(name):
            return name
    return None


def _terminal_command(terminal: str, cwd: str, command: list[str]) -> list[str]:
    term = Path(terminal).name
    joined = " ".join(shlex.quote(c) for c in command)
    # Keep a shell so `cd` + interactive grok behave well
    shell_cmd = f"cd {shlex.quote(cwd)} && exec {joined}"
    app_class = "hyprgrok-session"

    if term.startswith("kitty"):
        return [terminal, "--class", app_class, "--directory", cwd, *command]
    if term.startswith("foot"):
        return [terminal, "--app-id", app_class, "--working-directory", cwd, *command]
    if term.startswith("alacritty"):
        return [terminal, "--class", app_class, "--working-directory", cwd, "-e", *command]
    if term.startswith("wezterm"):
        return [terminal, "start", "--class", app_class, "--cwd", cwd, "--", *command]
    if term.startswith("ghostty"):
        return [terminal, f"--working-directory={cwd}", f"--class={app_class}", "-e", *command]
    if term.startswith("konsole"):
        return [terminal, "--workdir", cwd, "-e", *command]
    if term in {"gnome-terminal", "kgx"}:
        return [terminal, f"--working-directory={cwd}", "--", *command]
    # Generic fallback
    return [terminal, "-e", "sh", "-c", shell_cmd]


def ensure_grok(cfg: Config) -> str | None:
    return find_grok_binary(cfg.grok_binary)


def grok_missing_message() -> str:
    return (
        "Grok Build (`grok`) was not found on PATH.\n\n"
        "Install the official Grok Build CLI, then re-run HyprGrok.\n"
        "Docs: https://grok.x.ai/  (or your Grok Build install instructions)\n\n"
        "HyprGrok never stores xAI API keys — authentication stays with `grok`."
    )


def launch_interactive_session(
    cfg: Config,
    *,
    cwd: str | None = None,
    prompt: str | None = None,
    extra_args: list[str] | None = None,
) -> LaunchResult:
    grok = ensure_grok(cfg)
    if not grok:
        return LaunchResult(ok=False, message=grok_missing_message())

    workdir = cwd or os.getcwd()
    cmd = [grok, "--cwd", workdir]
    cmd.extend(cfg.launch.full_session_args)
    if extra_args:
        cmd.extend(extra_args)
    if prompt:
        cmd.append(prompt)

    terminal = resolve_terminal(cfg)
    if terminal:
        full = _terminal_command(terminal, workdir, cmd)
        try:
            proc = subprocess.Popen(
                full,
                cwd=workdir,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            return LaunchResult(ok=False, message=f"Failed to launch terminal: {exc}", command=full)
        return LaunchResult(
            ok=True,
            message=f"Launched Grok Build in {terminal} ({workdir})",
            command=full,
            pid=proc.pid,
        )

    # No terminal found — try hyprctl exec, else raw Popen
    if shutil.which("hyprctl"):
        joined = " ".join(shlex.quote(c) for c in cmd)
        try:
            subprocess.Popen(
                ["hyprctl", "dispatch", "exec", joined],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return LaunchResult(ok=True, message=f"Dispatched via hyprctl: {joined}", command=cmd)
        except OSError as exc:
            return LaunchResult(ok=False, message=str(exc), command=cmd)

    try:
        proc = subprocess.Popen(cmd, cwd=workdir, start_new_session=True)
    except OSError as exc:
        return LaunchResult(ok=False, message=str(exc), command=cmd)
    return LaunchResult(
        ok=True,
        message=f"Launched Grok Build (pid {proc.pid})",
        command=cmd,
        pid=proc.pid,
    )


def run_headless_prompt(
    cfg: Config,
    prompt: str,
    *,
    cwd: str | None = None,
    timeout: int | None = None,
) -> LaunchResult:
    grok = ensure_grok(cfg)
    if not grok:
        return LaunchResult(ok=False, message=grok_missing_message())

    workdir = cwd or os.getcwd()
    cmd = [grok, "-p", prompt, "--cwd", workdir, "--output-format", "plain"]
    wait = timeout if timeout is not None else cfg.launch.headless_timeout_sec

    try:
        result = subprocess.run(
            cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=wait,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return LaunchResult(
            ok=False,
            message=f"Grok Build timed out after {wait}s",
            command=cmd,
        )
    except OSError as exc:
        return LaunchResult(ok=False, message=str(exc), command=cmd)

    ok = result.returncode == 0
    text = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if ok and not text and err:
        text = err
    if not ok and not text:
        text = err or f"grok exited with code {result.returncode}"

    return LaunchResult(
        ok=ok,
        message="ok" if ok else "Grok Build returned an error",
        command=cmd,
        stdout=text,
        stderr=err,
        returncode=result.returncode,
    )


def notify(summary: str, body: str = "") -> None:
    if not shutil.which("notify-send"):
        return
    try:
        subprocess.run(
            ["notify-send", "--app-name=HyprGrok", summary, body],
            check=False,
            capture_output=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
