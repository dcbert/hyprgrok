# HyprGrok

**Grok Build, made for Hyprland.**

HyprGrok is a native Hyprland companion for the official **Grok Build** (`grok` CLI).  
It does **not** call the xAI API itself. It launches, manages, and enhances real Grok Build sessions with desktop awareness and a polished glass panel.

> Your Grok Build companion for Hyprland.

**Current version: 0.2.0** (MVP + polish + power features)

---

## Features

### Core (v0.1)

| Feature | Description |
|---------|-------------|
| **Glass panel** | Toggleable floating glass UI (`Super + G`) |
| **Quick prompt** | Headless `grok -p` from the panel or CLI |
| **Full session** | Interactive Grok Build in a ruled terminal |
| **Desktop context** | Window title/class + cwd + project root |
| **Smart launch** | Prefer focused terminal/editor project dir |
| **Install / uninstall** | Marked Hyprland binds & rules, clean removal |

### Polish & power (v0.2)

| Feature | Description |
|---------|-------------|
| **Screenshot context** | Active-window capture with `grim` |
| **Ask about window** | One-click / `Super + Ctrl + G` |
| **Multi-session** | Track interactive + headless sessions; stop/reuse |
| **History** | Recent prompts in panel + CLI |
| **Waybar module** | `hyprgrok status --waybar` |
| **Hyprland tools** | Safe `hyprctl` wrappers for desktop awareness |
| **ACP roadmap** | Ready for deeper Grok Build integration later |

---

## Requirements

- **Hyprland** (Wayland)
- **Python 3.12+**
- Official **Grok Build** CLI (`grok`)
- Optional: `grim`, Chrome/Chromium, `kitty`/`foot`/…, Waybar

---

## Install

```bash
git clone https://github.com/dcbert/hyprgrok.git
cd hyprgrok
./install.sh
```

One-liner (recommended — avoids occasional raw.githubusercontent.com cache lag):

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/dcbert/hyprgrok@main/install.sh | bash
```

GitHub raw (may lag a few minutes after updates):

```bash
curl -fsSL https://raw.githubusercontent.com/dcbert/hyprgrok/main/install.sh | bash
```

Skip Hyprland edits when piping:

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/dcbert/hyprgrok@main/install.sh | bash -s -- --no-hyprland
```

### Uninstall

```bash
hyprgrok-uninstall
# or ./uninstall.sh --purge
```

---

## Keybinds (defaults)

| Bind | Action |
|------|--------|
| `Super + G` | Toggle glass panel |
| `Super + Shift + G` | Full Grok Build session |
| `Super + Alt + G` | Print desktop context |
| `Super + Ctrl + G` | Ask about current window |

---

## CLI

```bash
hyprgrok                 # toggle panel
hyprgrok toggle
hyprgrok ask "explain this project" -c
hyprgrok session
hyprgrok ask-window
hyprgrok context --json
hyprgrok sessions
hyprgrok history
hyprgrok status
hyprgrok status --waybar
hyprgrok hypr snapshot
hyprgrok doctor
```

---

## Configuration

`~/.config/hyprgrok/config.toml` — panel position, terminal, theme, timeouts.  
HyprGrok **never** stores xAI API keys.

---

## Waybar

See [docs/WAYBAR.md](docs/WAYBAR.md) and `configs/waybar/hyprgrok.jsonc`.

```bash
hyprgrok status --waybar
```

---


## Top bar (Quickshell / Illogical Impulse)

This setup uses **Quickshell**, not Waybar. After install you should see a **robot** icon on the right of the bar:

- **Left-click** — open/close HyprGrok panel  
- **Right-click** — full Grok session  
- **Middle-click** — analyze focused window  

See [docs/QUICKSHELL.md](docs/QUICKSHELL.md). For plain Waybar, use `configs/waybar/hyprgrok.jsonc`.

## Architecture

```
Glass Panel (HTML)  ←→  Panel Server (Python, localhost)
                              │
              ┌───────────────┼──────────────────┐
              ▼               ▼                  ▼
         Context Engine   Session/History    Launcher
          (hyprctl/grim)                     (`grok` / `grok -p`)
              │
              └── Hyprland helpers (`hyprgrok hypr …`)
```

---

## Development

```bash
export PYTHONPATH=.
python3 -m hyprgrok doctor
python3 -m unittest discover -s tests -v
./install.sh
```

Docs: [TECH_SPEC](docs/TECH_SPEC.md) · [WAYBAR](docs/WAYBAR.md) · [ACP](docs/ACP.md) · [CHANGELOG](CHANGELOG.md)

---

## Philosophy

1. Prefer the real `grok` binary over any API  
2. Never store or handle xAI API keys  
3. Mark window rules / binds for clean uninstall  
4. Fail gracefully if `grok` is missing  
5. Keep the panel lightweight  

---

## License

MIT — see [LICENSE](LICENSE).

**Not affiliated with xAI.** Grok Build is the official CLI; HyprGrok is a community companion for Hyprland.
