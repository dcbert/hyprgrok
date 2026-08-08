# HyprGrok Technical Spec — Phase 0–3 (through v0.2)

## Scope

Ship a usable Hyprland companion for official Grok Build:

- Config system under `~/.config/hyprgrok/`
- Detect `grok` binary (never handle API keys)
- Context: active window + cwd + project root (+ active-window grim)
- Headless ask via `grok -p`
- Interactive launch in preferred terminal
- Local glass panel UI (HTTP + Chromium app window)
- Install / uninstall with marked Hyprland binds & rules
- Multi-session tracking, prompt history, Waybar status
- Hyprland helper commands for future MCP/ACP

## Module map

| Module | Responsibility |
|--------|----------------|
| `config.py` | Paths, TOML load/merge, grok binary discovery |
| `context.py` | `hyprctl activewindow -j`, `/proc/<pid>/cwd`, project markers |
| `launcher.py` | Terminal selection, `grok` interactive & `-p` headless |
| `session.py` | Recent session history JSON |
| `panel_server.py` | Threading HTTP server + REST API + static UI |
| `main.py` | CLI: toggle, serve, ask, session, context, doctor, init, status, sessions, history, ask-window, hypr |
| `status.py` | Waybar / machine-readable status |
| `hypr.py` | Safe hyprctl wrappers |

## CLI

```
hyprgrok                 # alias for toggle
hyprgrok toggle
hyprgrok serve [--port N]
hyprgrok ask [-c] [--screenshot] [--cwd DIR] PROMPT
hyprgrok session [PROMPT] [--cwd DIR]
hyprgrok context [--json] [--screenshot]
hyprgrok doctor
hyprgrok init
```

## Panel API (localhost only)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/status` | grok found?, busy, version |
| GET | `/api/context?screenshot=1` | desktop context |
| GET | `/api/config` | theme + panel options for UI |
| GET | `/api/sessions` | recent history |
| POST | `/api/ask` | `{prompt, inject_context, screenshot, cwd}` |
| POST | `/api/session` | `{prompt?, cwd?}` launch interactive |
| GET | `/` | glass UI |

## Grok Build integration

```bash
# Headless quick prompt
grok -p "$PROMPT" --cwd "$DIR" --output-format plain

# Interactive
grok --cwd "$DIR" [initial prompt]
# launched inside kitty/foot/alacritty/…
```

Launcher layer abstracts CLI flags so upstream changes stay isolated.

## Context algorithm

1. `hyprctl activewindow -j` → title, class, pid, workspace
2. Resolve cwd: `/proc/<pid>/cwd` → parent pid → title parse → process cwd
3. Walk parents for project markers (`.git`, `package.json`, `pyproject.toml`, …)
4. Optional: `grim` → `~/.cache/hyprgrok/context-screenshot.png` (path injected into prompt text only)

## Panel presentation

MVP uses a **Chromium/Chrome `--app=`** window titled `HyprGrok`, ruled by Hyprland:

- float, pin, fixed size, right-edge move, slight opacity
- CSS glass (blur, translucent cards) for feel when compositor blur is globally disabled

Fallback: `xdg-open` to localhost URL.

Future: GTK4 layer-shell for true exclusive-zone panel without a browser.

## Install layouts

### Files

```
~/.local/bin/hyprgrok
~/.local/share/hyprgrok/{hyprgrok,ui,configs,assets}
~/.config/hyprgrok/config.toml
~/.local/state/hyprgrok/{panel.pid,panel.port,sessions.json}
```

### Hyprland

Markers `BEGIN HYPRGROK` / `END HYPRGROK` (conf) or Lua comment equivalents.

- **Lua (illogical-impulse):** append to `~/.config/hypr/custom/{keybinds,rules}.lua`
- **Conf:** write snippets under `~/.config/hyprgrok/hyprland/` and `source` from main conf

## Security / privacy

- Server binds `127.0.0.1` only
- No xAI keys in process env managed by HyprGrok
- Screenshots stay local unless user attaches them inside a Grok session themselves

## Testing (MVP)

- Unit: config merge, project root detection, marked-block strip logic (shell)
- Smoke: `hyprgrok doctor`, `context --json`, import package, HTTP `/api/status`
- Manual on Hyprland: Super+G toggle, ask, session launch, uninstall cleanliness

## Phase 2+ hooks

- Multi-session registry + switcher in panel
- ACP client if stable
- Waybar/Quickshell module reading `sessions.json` / status endpoint
- Layer-shell native panel (drop browser dependency)
