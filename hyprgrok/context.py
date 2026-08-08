"""Desktop context gathering via hyprctl and process inspection."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PROJECT_MARKERS = (
    ".git",
    ".hg",
    ".svn",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "pnpm-workspace.yaml",
    "yarn.lock",
    "Cargo.toml",
    "go.mod",
    "CMakeLists.txt",
    "Makefile",
    "meson.build",
    "composer.json",
    "Gemfile",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "flake.nix",
    "shell.nix",
    "deno.json",
    "deno.jsonc",
    "mix.exs",
    "Package.swift",
    ".grok",
    ".projectile",
    ".idea",
    "uv.lock",
    "Pipfile",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
    "tox.ini",
    "poetry.lock",
    "tsconfig.json",
    "nx.json",
    "turbo.json",
    "lerna.json",
    "Cargo.lock",
    "WORKSPACE",
    "WORKSPACE.bazel",
    "MODULE.bazel",
)

_EDITOR_CLASSES = re.compile(
    r"(code|codium|cursor|zed|nvim|neovide|emacs|kate|jetbrains|"
    r"idea|pycharm|webstorm|goland|clion|rider|phpstorm|rubymine|"
    r"sublime|helix|windsurf|antigravity|vscodium|code-oss|"
    r"lapce|fleet|theia|vim|gvim)",
    re.I,
)
_TERMINAL_CLASSES = re.compile(
    r"(kitty|foot|alacritty|wezterm|ghostty|konsole|gnome-terminal|"
    r"kgx|xterm|uxterm|termite|tilix|rio|st|urxvt|terminator)",
    re.I,
)
_BROWSER_CLASSES = re.compile(
    r"(chrome|chromium|firefox|brave|zen|edge|librewolf|vivaldi|opera)",
    re.I,
)


@dataclass
class DesktopContext:
    window_title: str = ""
    window_class: str = ""
    window_address: str = ""
    pid: int | None = None
    cwd: str | None = None
    project_root: str | None = None
    project_name: str | None = None
    workspace: str = ""
    monitor: int | None = None
    at: list[int] = field(default_factory=list)
    size: list[int] = field(default_factory=list)
    floating: bool | None = None
    screenshot_path: str | None = None
    kind: str = "unknown"  # terminal | editor | browser | other
    file_hint: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def format_for_prompt(self, include_screenshot_note: bool = True) -> str:
        lines = ["[HyprGrok Desktop Context]"]
        if self.window_title:
            lines.append(f"Active window title: {self.window_title}")
        if self.window_class:
            lines.append(f"Active window class: {self.window_class}")
        if self.kind and self.kind != "unknown":
            lines.append(f"Window kind: {self.kind}")
        if self.file_hint:
            lines.append(f"Likely open file/path: {self.file_hint}")
        if self.cwd:
            lines.append(f"Working directory: {self.cwd}")
        if self.project_root and self.project_root != self.cwd:
            lines.append(f"Project root: {self.project_root}")
        if self.project_name:
            lines.append(f"Project name: {self.project_name}")
        if self.workspace:
            lines.append(f"Workspace: {self.workspace}")
        if self.screenshot_path and include_screenshot_note:
            lines.append(
                f"Screenshot of active window/desktop saved at: {self.screenshot_path} "
                "(use local tools to read this image if available)"
            )
        if self.notes:
            lines.append("Notes: " + "; ".join(self.notes))
        return "\n".join(lines)


def _run(cmd: list[str], timeout: float = 2.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def hyprctl_json(args: list[str]) -> Any | None:
    if not shutil.which("hyprctl"):
        return None
    try:
        result = _run(["hyprctl", *args, "-j"])
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def get_active_window() -> dict[str, Any] | None:
    data = hyprctl_json(["activewindow"])
    if isinstance(data, dict) and data.get("address"):
        return data
    return None


def classify_window(window_class: str, title: str = "") -> str:
    if _TERMINAL_CLASSES.search(window_class or ""):
        return "terminal"
    if _EDITOR_CLASSES.search(window_class or "") or _EDITOR_CLASSES.search(title or ""):
        return "editor"
    if _BROWSER_CLASSES.search(window_class or ""):
        return "browser"
    return "other"


def resolve_cwd_for_pid(pid: int | None) -> str | None:
    if not pid:
        return None
    try:
        path = Path(f"/proc/{pid}/cwd").resolve()
        if path.is_dir():
            return str(path)
    except (OSError, PermissionError, RuntimeError):
        pass
    try:
        link = os.readlink(f"/proc/{pid}/cwd")
        if link and Path(link).is_dir():
            return link
    except (OSError, PermissionError):
        pass
    return None


def _ancestor_pids(pid: int, max_depth: int = 8) -> list[int]:
    chain: list[int] = []
    current = pid
    for _ in range(max_depth):
        try:
            status = Path(f"/proc/{current}/status").read_text(encoding="utf-8", errors="ignore")
        except OSError:
            break
        parent = None
        for line in status.splitlines():
            if line.startswith("PPid:"):
                try:
                    parent = int(line.split()[1])
                except (IndexError, ValueError):
                    parent = None
                break
        if not parent or parent <= 1:
            break
        chain.append(parent)
        current = parent
    return chain


def find_project_root(start: str | Path | None) -> str | None:
    if not start:
        return None
    try:
        current = Path(start).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    if current.is_file():
        current = current.parent

    best: Path | None = None
    best_score = -1
    for directory in [current, *current.parents]:
        score = 0
        for marker in PROJECT_MARKERS:
            if (directory / marker).exists():
                # Prefer VCS roots and strong project files
                if marker in {".git", ".hg", ".svn"}:
                    score += 10
                elif marker in {"pyproject.toml", "package.json", "Cargo.toml", "go.mod", ".grok"}:
                    score += 5
                else:
                    score += 2
        if score > best_score:
            best_score = score
            best = directory
        # Stop climbing past home once we already have a strong match
        if best_score >= 10 and directory == Path.home():
            break
        if directory == directory.parent:
            break

    if best is not None and best_score > 0:
        return str(best)
    return str(current) if current.is_dir() else None


def _cwd_from_title(title: str) -> str | None:
    if not title:
        return None
    m = re.search(r"(?:[:\s~])(/[^\s]+|~/[^\s]+)\s*$", title)
    if not m:
        m = re.search(r"(~/[^\s]+|/[A-Za-z0-9_./~-]+)", title)
    if not m:
        return None
    candidate = Path(m.group(1).rstrip(".,;:)")).expanduser()
    try:
        if candidate.is_dir():
            return str(candidate.resolve())
        if candidate.is_file():
            return str(candidate.parent.resolve())
        if candidate.parent.is_dir():
            return str(candidate.parent.resolve())
    except (OSError, RuntimeError):
        return None
    return None


def _file_hint_from_title(title: str) -> str | None:
    if not title:
        return None
    # VS Code / Cursor: "file.py - project - Cursor"
    # nvim: "nvim file.py" or "file.py"
    patterns = [
        r"^(.+?\.\w{1,12})\s+[-—–]",
        r"[-—–]\s*(.+?\.\w{1,12})\s*$",
        r"((?:~|/|[\w.-]+/)+[\w.-]+\.\w{1,12})",
    ]
    for pat in patterns:
        m = re.search(pat, title)
        if m:
            hint = m.group(1).strip().strip("\"'")
            if hint and len(hint) < 400:
                return hint
    return None


def take_screenshot(
    dest_dir: Path | None = None,
    *,
    region: list[int] | None = None,
    active_window: bool = True,
) -> str | None:
    if not shutil.which("grim"):
        return None
    dest_dir = dest_dir or (Path.home() / ".cache" / "hyprgrok")
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / "context-screenshot.png"

    geometry: str | None = None
    if region and len(region) >= 4:
        x, y, w, h = (int(region[0]), int(region[1]), int(region[2]), int(region[3]))
        if w > 0 and h > 0:
            geometry = f"{x},{y} {w}x{h}"
    elif active_window:
        window = get_active_window()
        if window:
            at = window.get("at") or [0, 0]
            size = window.get("size") or [0, 0]
            try:
                x, y = int(at[0]), int(at[1])
                w, h = int(size[0]), int(size[1])
                if w > 0 and h > 0:
                    geometry = f"{x},{y} {w}x{h}"
            except (TypeError, ValueError, IndexError):
                geometry = None

    cmd = ["grim"]
    if geometry:
        cmd.extend(["-g", geometry])
    cmd.append(str(out))
    try:
        result = _run(cmd, timeout=5.0)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode == 0 and out.is_file():
        return str(out)
    # Fallback full-screen
    if geometry:
        try:
            result = _run(["grim", str(out)], timeout=5.0)
            if result.returncode == 0 and out.is_file():
                return str(out)
        except (subprocess.TimeoutExpired, OSError):
            return None
    return None


def gather_context(
    *,
    include_screenshot: bool = False,
    screenshot_dir: Path | None = None,
    active_window_only: bool = True,
) -> DesktopContext:
    ctx = DesktopContext()
    window = get_active_window()
    if not window:
        ctx.notes.append("hyprctl activewindow unavailable (not on Hyprland?)")
        ctx.cwd = os.getcwd()
        ctx.project_root = find_project_root(ctx.cwd)
        ctx.project_name = Path(ctx.project_root).name if ctx.project_root else None
        return ctx

    ctx.window_title = str(window.get("title") or "")
    ctx.window_class = str(window.get("class") or window.get("initialClass") or "")
    ctx.window_address = str(window.get("address") or "")
    pid = window.get("pid")
    ctx.pid = int(pid) if pid is not None else None
    workspace = window.get("workspace") or {}
    if isinstance(workspace, dict):
        ctx.workspace = str(workspace.get("name") or workspace.get("id") or "")
    else:
        ctx.workspace = str(workspace)
    monitor = window.get("monitor")
    ctx.monitor = int(monitor) if monitor is not None else None
    at = window.get("at") or []
    size = window.get("size") or []
    try:
        ctx.at = [int(at[0]), int(at[1])] if len(at) >= 2 else []
        ctx.size = [int(size[0]), int(size[1])] if len(size) >= 2 else []
    except (TypeError, ValueError):
        ctx.at, ctx.size = [], []
    ctx.floating = bool(window.get("floating")) if "floating" in window else None
    ctx.kind = classify_window(ctx.window_class, ctx.window_title)
    ctx.file_hint = _file_hint_from_title(ctx.window_title)

    cwd = resolve_cwd_for_pid(ctx.pid)
    if not cwd and ctx.kind == "terminal":
        cwd = _cwd_from_title(ctx.window_title)
    if not cwd and ctx.pid:
        for ancestor in _ancestor_pids(ctx.pid):
            cwd = resolve_cwd_for_pid(ancestor)
            if cwd:
                ctx.notes.append(f"cwd from ancestor pid {ancestor}")
                break
    if not cwd and ctx.file_hint:
        expanded = Path(ctx.file_hint).expanduser()
        try:
            if expanded.is_file():
                cwd = str(expanded.parent.resolve())
            elif expanded.is_dir():
                cwd = str(expanded.resolve())
        except (OSError, RuntimeError):
            pass
    if not cwd:
        cwd = os.getcwd()
        ctx.notes.append("fell back to HyprGrok process cwd")

    ctx.cwd = cwd
    # Prefer project from file hint path when available
    project_seed = cwd
    if ctx.file_hint:
        try:
            fh = Path(ctx.file_hint).expanduser()
            if fh.exists():
                project_seed = str(fh)
        except OSError:
            pass
    ctx.project_root = find_project_root(project_seed)
    ctx.project_name = Path(ctx.project_root).name if ctx.project_root else None

    if include_screenshot:
        region = None
        if active_window_only and len(ctx.at) == 2 and len(ctx.size) == 2:
            region = [ctx.at[0], ctx.at[1], ctx.size[0], ctx.size[1]]
        ctx.screenshot_path = take_screenshot(
            screenshot_dir,
            region=region,
            active_window=active_window_only,
        )
        if not ctx.screenshot_path:
            ctx.notes.append("screenshot failed (is grim installed?)")

    return ctx


def smart_launch_cwd() -> str:
    """Prefer project root of focused terminal/editor when possible."""
    ctx = gather_context(include_screenshot=False)
    if ctx.kind in {"terminal", "editor"} and ctx.project_root:
        return ctx.project_root
    if ctx.project_root and ctx.kind != "browser":
        return ctx.project_root
    if ctx.cwd:
        return ctx.cwd
    return os.getcwd()


def ask_about_window_prompt(extra: str = "") -> tuple[str, DesktopContext]:
    """Build a rich prompt for the current window."""
    ctx = gather_context(include_screenshot=True, active_window_only=True)
    parts = [
        "Please analyze my current desktop focus and help me with it.",
        ctx.format_for_prompt(),
    ]
    if extra.strip():
        parts.append("Additional user request:")
        parts.append(extra.strip())
    else:
        parts.append(
            "Explain what I'm looking at, note the project if any, "
            "and suggest useful next actions for development."
        )
    return "\n\n".join(parts), ctx
