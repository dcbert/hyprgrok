# HyprGrok technical specification

Version: **0.3.0**

## Goals

- Companion UX for official Grok Build on Hyprland  
- Zero direct xAI API usage  
- Fast panel open, clean install/uninstall  
- Reuse Grok’s on-disk session store  

## Modules

| Module | Role |
|--------|------|
| `config.py` | XDG paths, TOML merge, `grok` discovery |
| `context.py` | Active window (skips panel), cwd, project root, grim |
| `launcher.py` | Terminal launch, `grok -p`, resume / continue |
| `grok_store.py` | Read-only `~/.grok/sessions` + `active_sessions.json` |
| `session.py` | Lightweight HyprGrok-local activity log |
| `panel_server.py` | Localhost HTTP API + static UI |
| `runtime.py` | PID/port files for the panel server |
| `status.py` | Waybar / Quickshell JSON status |
| `hypr.py` | Safe `hyprctl` wrappers |
| `main.py` | CLI |

## CLI surface

```
hyprgrok [toggle]
hyprgrok serve [--port N]
hyprgrok ask [-c] [--screenshot] [--cwd DIR] [--direct] PROMPT
hyprgrok session [PROMPT] [--cwd DIR]
hyprgrok ask-window [PROMPT] [--cwd DIR] [--print-only]
hyprgrok context [--json] [--screenshot]
hyprgrok sessions [--json] [--running] [-q QUERY] [--resume ID] [--panel-only]
hyprgrok history [--json] [--cwd DIR] [--panel-only]
hyprgrok status [--json] [--waybar]
hyprgrok hypr {snapshot|clients|reload|dispatch}
hyprgrok doctor
hyprgrok init
```

## Panel HTTP API (`127.0.0.1` only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/status` | grok found?, busy, grok_store summary |
| GET | `/api/context?screenshot=1` | desktop context |
| GET | `/api/config` | theme + panel options for UI |
| GET | `/api/sessions?limit=&q=&cwd=` | Grok Build sessions |
| GET | `/api/session/detail?id=` | one session |
| GET | `/api/history?limit=&cwd=` | prompt history |
| POST | `/api/ask` | headless prompt |
| POST | `/api/session` | launch interactive |
| POST | `/api/session/resume` | `grok --resume` |
| POST | `/api/ask-about-window` | window analysis |
| POST | `/api/session/stop` | stop panel-tracked PID |
| GET | `/api/waybar` | status bar JSON |
| GET | `/` | glass UI |

## Grok Build integration

```bash
grok -p "$PROMPT" --cwd "$DIR" --output-format plain
grok --cwd "$DIR" [prompt]
grok --cwd "$DIR" --resume "$SESSION_ID"
```

Session metadata (read-only):

```
~/.grok/active_sessions.json
~/.grok/sessions/<urlencode(cwd)>/<uuid>/summary.json
~/.grok/sessions/<urlencode(cwd)>/prompt_history.jsonl
~/.grok/sessions/session_search.sqlite
```

## Focus / panel window rules

- **Panel identity:** exact title `HyprGrok` or class containing `hyprgrok-panel`  
- **Context focus:** skip panel windows; use Hyprland `focusHistoryID`  
- **Placement:** fixed width 560px, height `monitor_h*0.88`, move `(monitor_w-576, 48)`  
  (avoid `window_w` in move expressions — races with Chrome resize)

## Install layout

```
~/.local/bin/hyprgrok
~/.local/bin/hyprgrok-uninstall
~/.local/share/hyprgrok/{hyprgrok,ui,configs,assets,docs}
~/.config/hyprgrok/config.toml
~/.local/state/hyprgrok/{panel.pid,panel.port,sessions.json}
```

Hyprland markers: `# BEGIN HYPRGROK` / `# END HYPRGROK` (conf) or Lua `-- BEGIN/END HYPRGROK`.
