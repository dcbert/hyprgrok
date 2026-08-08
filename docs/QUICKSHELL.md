# Quickshell / Illogical Impulse bar module

HyprGrok is **not** Waybar on this setup — the top bar is **Quickshell** (`qs -c ii`).

## What you get

A **smart_toy (robot)** icon on the right side of the bar:

| Click | Action |
|-------|--------|
| Left | Toggle HyprGrok glass panel |
| Right | Open full Grok Build session |
| Middle | Analyze focused window |

Tooltip shows status; a badge appears when sessions are active.

## Install / enable

If you used `./install.sh` on a machine already running II, the module may already be wired.

Manual:

```bash
# from a HyprGrok clone
./configs/quickshell/install-bar-module.sh
```

Then ensure the toggle is on:

1. Open **II Settings** (quickshell settings)
2. **Bar → Utility buttons → HyprGrok**
3. Reload shell: `killall qs; qs -c ii &`

Or set in `~/.config/illogical-impulse/config.json` under `bar.utilButtons`:

```json
"showHyprGrok": true
```

## Requirements

- `~/.local/bin/hyprgrok` installed
- Illogical Impulse Quickshell config at `~/.config/quickshell/ii`
