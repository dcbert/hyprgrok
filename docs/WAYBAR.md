# Waybar / status bar integration

## One-liner module

```jsonc
"custom/hyprgrok": {
  "exec": "hyprgrok status --waybar",
  "return-type": "json",
  "interval": 5,
  "format": "󰚩 {}",
  "on-click": "hyprgrok toggle",
  "on-click-right": "hyprgrok session",
  "on-click-middle": "hyprgrok ask-window",
  "tooltip": true
}
```

Copy from `configs/waybar/hyprgrok.jsonc` and optional `style-snippet.css`.

## Output schema

`hyprgrok status --waybar` prints:

```json
{
  "text": "Grok",
  "alt": "idle",
  "class": "idle",
  "tooltip": "HyprGrok idle — Super+G to open",
  "percentage": 0,
  "grok_found": true,
  "panel_running": false,
  "sessions": { "running": 0, "total": 0 }
}
```

Classes: `idle` | `active` | `missing`.

## Quickshell

Poll the same command or `GET http://127.0.0.1:8765/api/waybar` when the panel server is running.
