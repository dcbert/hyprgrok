# Quickshell / Illogical Impulse bar module

Many Hyprland users run **Quickshell** with the Illogical Impulse (`ii`) config, not Waybar.

## What you get

A **robot** (`smart_toy`) button on the right side of the bar:

| Click | Action |
|-------|--------|
| **Left** | Toggle HyprGrok glass panel |
| **Right** | Full Grok Build session |
| **Middle** | Analyze focused window |

Tooltip shows status; a badge appears when Grok sessions are active.

## Install

`./install.sh` copies `HyprGrokButton.qml` and enables `showHyprGrok` when II is detected.

Manual:

```bash
./configs/quickshell/install-bar-module.sh
```

Then:

1. II **Settings → Bar → Utility buttons → HyprGrok** (on)  
2. Reload: `killall qs; qs -c ii &`  

Or in `~/.config/illogical-impulse/config.json`:

```json
"bar": {
  "utilButtons": {
    "showHyprGrok": true
  }
}
```

`BarContent.qml` should load `HyprGrokButton` in a `BarGroup` on the right side.  
On Illogical Impulse upgrades that overwrite `BarContent.qml`, re-run the install helper or re-add the loader block.

## Requirements

- `~/.local/bin/hyprgrok`  
- Quickshell config at `~/.config/quickshell/ii`  
