#!/usr/bin/env bash
# HyprGrok uninstaller — removes binds, rules, and installed files cleanly

set -euo pipefail

APP_NAME="hyprgrok"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$APP_NAME"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/$APP_NAME"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/$APP_NAME"
HYPR_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/hypr"
MARKER_BEGIN="# BEGIN HYPRGROK"
MARKER_END="# END HYPRGROK"
LUA_BEGIN="-- BEGIN HYPRGROK"
LUA_END="-- END HYPRGROK"
KEEP_CONFIG=0
PURGE=0

RED=$'\033[0;31m'
GRN=$'\033[0;32m'
YLW=$'\033[0;33m'
CYN=$'\033[0;36m'
RST=$'\033[0m'

info()  { printf "%s==>%s %s\n" "$CYN" "$RST" "$*"; }
ok()    { printf "%s[ok]%s %s\n" "$GRN" "$RST" "$*"; }
warn()  { printf "%s[warn]%s %s\n" "$YLW" "$RST" "$*"; }

usage() {
  cat <<EOF
HyprGrok uninstaller

Options:
  --keep-config   Keep ~/.config/hyprgrok
  --purge         Also remove config, state, and cache
  -h, --help      Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep-config) KEEP_CONFIG=1; shift ;;
    --purge) PURGE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) warn "Unknown option: $1"; shift ;;
  esac
done

strip_marked_block() {
  local file="$1" begin="$2" end="$3"
  [[ -f "$file" ]] || return 0
  local tmp
  tmp="$(mktemp)"
  awk -v b="$begin" -v e="$end" '
    $0 == b {skip=1; next}
    $0 == e {skip=0; next}
    !skip {print}
  ' "$file" > "$tmp"
  mv "$tmp" "$file"
  ok "Cleaned markers from $file"
}

# Resolve install meta if present
PREFIX="${PREFIX:-$HOME/.local}"
SHARE_DIR="$PREFIX/share/$APP_NAME"
BIN_DIR="$PREFIX/bin"
if [[ -f "$CONFIG_DIR/install-meta.toml" ]]; then
  # shellcheck disable=SC2002
  meta_prefix=$(grep -E '^prefix\s*=' "$CONFIG_DIR/install-meta.toml" | head -1 | sed -E 's/.*=\s*"?([^"]+)"?/\1/' || true)
  meta_share=$(grep -E '^share_dir\s*=' "$CONFIG_DIR/install-meta.toml" | head -1 | sed -E 's/.*=\s*"?([^"]+)"?/\1/' || true)
  meta_bin=$(grep -E '^bin_dir\s*=' "$CONFIG_DIR/install-meta.toml" | head -1 | sed -E 's/.*=\s*"?([^"]+)"?/\1/' || true)
  [[ -n "${meta_prefix:-}" ]] && PREFIX="$meta_prefix"
  [[ -n "${meta_share:-}" ]] && SHARE_DIR="$meta_share"
  [[ -n "${meta_bin:-}" ]] && BIN_DIR="$meta_bin"
fi

info "Stopping panel server if running…"
if [[ -f "$STATE_DIR/panel.pid" ]]; then
  pid=$(cat "$STATE_DIR/panel.pid" 2>/dev/null || true)
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    ok "Stopped pid $pid"
  fi
fi
# Also try pkill by module
pkill -f "python3 -m hyprgrok serve" 2>/dev/null || true

info "Removing Hyprland integration…"
strip_marked_block "$HYPR_DIR/custom/keybinds.lua" "$LUA_BEGIN" "$LUA_END"
strip_marked_block "$HYPR_DIR/custom/rules.lua" "$LUA_BEGIN" "$LUA_END"
for conf in "$HYPR_DIR/hyprland.conf" "$HYPR_DIR/hypr.conf" "$HYPR_DIR/config.conf"; do
  strip_marked_block "$conf" "$MARKER_BEGIN" "$MARKER_END"
done

if command -v hyprctl >/dev/null 2>&1; then
  hyprctl reload >/dev/null 2>&1 || true
fi

info "Removing installed files…"
rm -f "$BIN_DIR/hyprgrok" "$BIN_DIR/hyprgrok-uninstall"
rm -rf "$SHARE_DIR"
ok "Removed $BIN_DIR/hyprgrok and $SHARE_DIR"

if [[ "$PURGE" == "1" ]]; then
  info "Purging config/state/cache…"
  rm -rf "$CONFIG_DIR" "$STATE_DIR" "$CACHE_DIR"
  ok "Removed $CONFIG_DIR $STATE_DIR $CACHE_DIR"
elif [[ "$KEEP_CONFIG" == "1" ]]; then
  ok "Kept $CONFIG_DIR"
else
  # Default: remove install meta + browser profile, keep config.toml unless empty desire
  rm -f "$CONFIG_DIR/install-meta.toml"
  rm -rf "$CONFIG_DIR/browser-profile" "$CONFIG_DIR/hyprland" "$CONFIG_DIR/panel.log"
  rm -rf "$STATE_DIR"
  ok "Removed runtime state; kept $CONFIG_DIR/config.toml (use --purge to delete)"
fi

echo ""
echo "${GRN}HyprGrok uninstalled.${RST}"
echo "  If you still have Super+G bound, reload Hyprland or remove leftover binds manually."
echo ""
