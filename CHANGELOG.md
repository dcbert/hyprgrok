# Changelog

All notable changes to HyprGrok are documented here.

## [0.3.0] — 2026-08-08

Public-ready polish release.

### Added
- Read official Grok Build sessions & history from `~/.grok/sessions`
- Resume sessions via `grok --resume` from the panel and CLI
- Session search (FTS when available)
- Quickshell / Illogical Impulse bar button (`smart_toy`)
- CONTRIBUTING.md, SECURITY.md, docs index
- Real product screenshots in README

### Fixed
- Panel detection false positives (Code/kitty titles containing “HyprGrok”)
- Focused-window context always showing the HyprGrok panel after Refresh
- Panel opening partially off-screen (`window_w` race in Hyprland move rules)
- `curl | bash` install with unbound `BASH_SOURCE` under `set -u`
- Super+G conflict with Illogical Impulse widget overlay → **Super+Space**

### Changed
- Clearer panel UX (labels, action descriptions, empty states)
- Default panel size 560×~88% height, safe on-screen placement
- Installer wires Quickshell module when II is detected

## [0.2.0] — 2026-08-08

### Added
- Active-window screenshots via `grim`
- Stronger project detection
- Session list / history in panel
- Ask about current window
- Waybar status JSON
- Hyprland helper CLI (`hypr hypr …`)

## [0.1.0] — 2026-08-08

### Added
- Glass panel, quick ask (`grok -p`), full session launch
- Desktop context via `hyprctl`
- install.sh / uninstall.sh with marked Hyprland binds & rules
