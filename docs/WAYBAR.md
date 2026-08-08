# Waybar module

## Snippet

Add to your Waybar config (see also `configs/waybar/hyprgrok.jsonc`):

```jsonc
"modules-right": ["custom/hyprgrok", "..."],

"custom/hyprgrok": {
  "exec": "hyprgrok status --waybar",
  "return-type": "json",
  "interval": 5,
  "format": " {}",
  "on-click": "hyprgrok toggle",
  "on-click-right": "hyprgrok session",
  "on-click-middle": "hyprgrok ask-window",
  "tooltip": true
}
```

Optional CSS: `configs/waybar/style-snippet.css`.

Ensure `hyprgrok` is on the PATH Waybar inherits, or use the absolute path:

```jsonc
"exec": "/home/YOU/.local/bin/hyprgrok status --waybar",
"on-click": "/home/YOU/.local/bin/hyprgrok toggle"
```

## JSON shape

```json
{
  "text": "Grok",
  "alt": "idle",
  "class": "idle",
  "tooltip": "HyprGrok idle — Super+Space to open",
  "percentage": 0,
  "grok_found": true,
  "panel_running": false,
  "sessions": { "running": 0, "grok_active": 0, "grok_total": 12 }
}
```

Classes: `idle` | `active` | `missing`.
