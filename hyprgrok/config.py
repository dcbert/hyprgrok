"""Configuration loading and defaults for HyprGrok."""

from __future__ import annotations

import os
import shutil
import tomllib
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


APP_NAME = "hyprgrok"
PANEL_TITLE = "HyprGrok"
DEFAULT_PORT = 8765

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / APP_NAME
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / APP_NAME

CONFIG_PATH = CONFIG_DIR / "config.toml"
PID_PATH = STATE_DIR / "panel.pid"
PORT_PATH = STATE_DIR / "panel.port"
SOCKET_PATH = STATE_DIR / "panel.sock"
RUNTIME_DIR = STATE_DIR


def package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def bundled_default_config_path() -> Path:
    return package_root() / "configs" / "default.toml"


def ui_root() -> Path:
    return package_root() / "ui"


@dataclass
class PanelConfig:
    position: str = "right"  # left | right
    width: int = 560
    height: int = 980
    opacity: float = 0.92
    port: int = DEFAULT_PORT
    auto_inject_context: bool = False
    browser: str = "auto"  # auto | google-chrome-stable | chromium | firefox


@dataclass
class LaunchConfig:
    terminal: str = "auto"
    preferred_terminals: list[str] = field(
        default_factory=lambda: [
            "kitty",
            "foot",
            "alacritty",
            "wezterm",
            "ghostty",
            "konsole",
            "gnome-terminal",
        ]
    )
    full_session_args: list[str] = field(default_factory=list)
    headless_timeout_sec: int = 300


@dataclass
class KeybindConfig:
    # Super+G is taken by Illogical Impulse ("Toggle widget overlay") — use Super+Space
    toggle_panel: str = "SUPER, SPACE"
    open_session: str = "SUPER SHIFT, G"
    quick_context: str = "SUPER ALT, G"


@dataclass
class ThemeConfig:
    accent: str = "#7aa2f7"
    background: str = "rgba(20, 22, 30, 0.72)"
    text: str = "#c0caf5"
    muted: str = "#565f89"
    success: str = "#9ece6a"
    error: str = "#f7768e"
    border: str = "rgba(122, 162, 247, 0.35)"
    font_family: str = "Inter, JetBrains Mono, ui-sans-serif, system-ui, sans-serif"


@dataclass
class Config:
    panel: PanelConfig = field(default_factory=PanelConfig)
    launch: LaunchConfig = field(default_factory=LaunchConfig)
    keybinds: KeybindConfig = field(default_factory=KeybindConfig)
    theme: ThemeConfig = field(default_factory=ThemeConfig)
    grok_binary: str = "grok"
    notify_on_complete: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _dict_to_config(data: dict[str, Any]) -> Config:
    panel = PanelConfig(**{k: v for k, v in data.get("panel", {}).items() if k in PanelConfig.__dataclass_fields__})
    launch_raw = data.get("launch", {})
    launch = LaunchConfig(
        **{k: v for k, v in launch_raw.items() if k in LaunchConfig.__dataclass_fields__}
    )
    keybinds = KeybindConfig(
        **{k: v for k, v in data.get("keybinds", {}).items() if k in KeybindConfig.__dataclass_fields__}
    )
    theme = ThemeConfig(
        **{k: v for k, v in data.get("theme", {}).items() if k in ThemeConfig.__dataclass_fields__}
    )
    return Config(
        panel=panel,
        launch=launch,
        keybinds=keybinds,
        theme=theme,
        grok_binary=str(data.get("grok_binary", "grok")),
        notify_on_complete=bool(data.get("notify_on_complete", True)),
    )


def default_config() -> Config:
    path = bundled_default_config_path()
    if path.is_file():
        with path.open("rb") as fh:
            return _dict_to_config(tomllib.load(fh))
    return Config()


def ensure_dirs() -> None:
    for path in (CONFIG_DIR, DATA_DIR, STATE_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def write_default_config(force: bool = False) -> Path:
    ensure_dirs()
    if CONFIG_PATH.exists() and not force:
        return CONFIG_PATH
    source = bundled_default_config_path()
    if source.is_file():
        shutil.copy2(source, CONFIG_PATH)
    else:
        CONFIG_PATH.write_text(_config_to_toml(default_config()), encoding="utf-8")
    return CONFIG_PATH


def load_config(path: Path | None = None) -> Config:
    ensure_dirs()
    cfg_path = path or CONFIG_PATH
    base = default_config().to_dict()
    if cfg_path.is_file():
        with cfg_path.open("rb") as fh:
            user = tomllib.load(fh)
        merged = _merge_dict(base, user)
        return _dict_to_config(merged)
    return _dict_to_config(base)


def _config_to_toml(cfg: Config) -> str:
    """Minimal TOML writer for defaults (stdlib has no tomllib dump)."""
    d = cfg.to_dict()
    lines: list[str] = [
        f'grok_binary = "{d["grok_binary"]}"',
        f"notify_on_complete = {'true' if d['notify_on_complete'] else 'false'}",
        "",
        "[panel]",
        f'position = "{d["panel"]["position"]}"',
        f'width = {d["panel"]["width"]}',
        f'height = {d["panel"]["height"]}',
        f'opacity = {d["panel"]["opacity"]}',
        f'port = {d["panel"]["port"]}',
        f'auto_inject_context = {"true" if d["panel"]["auto_inject_context"] else "false"}',
        f'browser = "{d["panel"]["browser"]}"',
        "",
        "[launch]",
        f'terminal = "{d["launch"]["terminal"]}"',
        "preferred_terminals = ["
        + ", ".join(f'"{t}"' for t in d["launch"]["preferred_terminals"])
        + "]",
        f"headless_timeout_sec = {d['launch']['headless_timeout_sec']}",
        "",
        "[keybinds]",
        f'toggle_panel = "{d["keybinds"]["toggle_panel"]}"',
        f'open_session = "{d["keybinds"]["open_session"]}"',
        f'quick_context = "{d["keybinds"]["quick_context"]}"',
        "",
        "[theme]",
        f'accent = "{d["theme"]["accent"]}"',
        f'background = "{d["theme"]["background"]}"',
        f'text = "{d["theme"]["text"]}"',
        f'muted = "{d["theme"]["muted"]}"',
        f'success = "{d["theme"]["success"]}"',
        f'error = "{d["theme"]["error"]}"',
        f'border = "{d["theme"]["border"]}"',
        f'font_family = "{d["theme"]["font_family"]}"',
        "",
    ]
    return "\n".join(lines)


def find_grok_binary(preferred: str = "grok") -> str | None:
    """Locate the official Grok Build binary. Never handles API keys."""
    candidates: list[str] = []
    if preferred and preferred != "grok":
        candidates.append(preferred)
    candidates.extend(
        [
            "grok",
            str(Path.home() / ".grok" / "bin" / "grok"),
            str(Path.home() / ".local" / "bin" / "grok"),
            "/usr/local/bin/grok",
            "/usr/bin/grok",
        ]
    )
    seen: set[str] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        path = Path(cand).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path.resolve())
        found = shutil.which(cand)
        if found:
            return found
    return None
