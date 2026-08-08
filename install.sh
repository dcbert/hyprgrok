#!/usr/bin/env bash
# HyprGrok installer — Grok Build companion for Hyprland
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<user>/hyprgrok/main/install.sh | bash
#   ./install.sh
#   ./install.sh --no-hyprland   # skip keybinds/rules
#   ./install.sh --prefix ~/.local

set -euo pipefail

APP_NAME="hyprgrok"
VERSION="0.2.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
SHARE_DIR="$PREFIX/share/$APP_NAME"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$APP_NAME"
HYPR_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/hypr"
MARKER_BEGIN="# BEGIN HYPRGROK"
MARKER_END="# END HYPRGROK"
LUA_BEGIN="-- BEGIN HYPRGROK"
LUA_END="-- END HYPRGROK"
INSTALL_HYPRLAND=1
FORCE=0

RED=$'\033[0;31m'
GRN=$'\033[0;32m'
YLW=$'\033[0;33m'
CYN=$'\033[0;36m'
RST=$'\033[0m'

info()  { printf "%s==>%s %s\n" "$CYN" "$RST" "$*"; }
ok()    { printf "%s[ok]%s %s\n" "$GRN" "$RST" "$*"; }
warn()  { printf "%s[warn]%s %s\n" "$YLW" "$RST" "$*"; }
err()   { printf "%s[err]%s %s\n" "$RED" "$RST" "$*" >&2; }

usage() {
  cat <<EOF
HyprGrok installer v${VERSION}

Options:
  --prefix DIR       Install prefix (default: ~/.local)
  --no-hyprland      Do not modify Hyprland keybinds/window rules
  --force            Overwrite existing user config.toml
  -h, --help         Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="$2"; BIN_DIR="$PREFIX/bin"; SHARE_DIR="$PREFIX/share/$APP_NAME"; shift 2 ;;
    --no-hyprland) INSTALL_HYPRLAND=0; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) err "Unknown option: $1"; usage; exit 1 ;;
  esac
done

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

check_deps() {
  info "Checking dependencies…"
  local missing=()
  need_cmd python3 || missing+=("python3")
  if ! need_cmd grok && [[ ! -x "$HOME/.grok/bin/grok" ]]; then
    warn "Official Grok Build (\`grok\`) not found — HyprGrok will guide you at first run"
  else
    ok "grok found: $(command -v grok 2>/dev/null || echo "$HOME/.grok/bin/grok")"
  fi
  need_cmd hyprctl && ok "hyprctl found" || warn "hyprctl not found (are you on Hyprland?)"
  need_cmd grim && ok "grim found" || warn "grim not found (screenshot context disabled until installed)"
  need_cmd jq && ok "jq found" || warn "jq optional"
  if need_cmd google-chrome-stable || need_cmd chromium || need_cmd firefox; then
    ok "browser found for glass panel"
  else
    warn "No Chrome/Chromium/Firefox found — panel will try xdg-open"
  fi
  if ((${#missing[@]})); then
    err "Missing required: ${missing[*]}"
    exit 1
  fi
  ok "python3: $(python3 --version 2>&1)"
}

install_files() {
  info "Installing to $PREFIX …"
  mkdir -p "$BIN_DIR" "$SHARE_DIR" "$CONFIG_DIR"

  # Copy package tree
  rsync -a --delete \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache' \
    "$SCRIPT_DIR/hyprgrok" \
    "$SCRIPT_DIR/ui" \
    "$SCRIPT_DIR/configs" \
    "$SCRIPT_DIR/assets" \
    "$SCRIPT_DIR/docs" \
    "$SHARE_DIR/" 2>/dev/null || {
    # Fallback without rsync
    rm -rf "$SHARE_DIR/hyprgrok" "$SHARE_DIR/ui" "$SHARE_DIR/configs" "$SHARE_DIR/assets" "$SHARE_DIR/docs"
    cp -a "$SCRIPT_DIR/hyprgrok" "$SHARE_DIR/"
    cp -a "$SCRIPT_DIR/ui" "$SHARE_DIR/"
    cp -a "$SCRIPT_DIR/configs" "$SHARE_DIR/"
    mkdir -p "$SHARE_DIR/assets"
    if [[ -d "$SCRIPT_DIR/assets" ]]; then
      cp -a "$SCRIPT_DIR/assets/." "$SHARE_DIR/assets/" 2>/dev/null || true
    fi
    if [[ -d "$SCRIPT_DIR/docs" ]]; then
      cp -a "$SCRIPT_DIR/docs" "$SHARE_DIR/"
    fi
  }

  # Optional docs
  [[ -f "$SCRIPT_DIR/README.md" ]] && cp -f "$SCRIPT_DIR/README.md" "$SHARE_DIR/"
  [[ -f "$SCRIPT_DIR/LICENSE" ]] && cp -f "$SCRIPT_DIR/LICENSE" "$SHARE_DIR/"

  # Wrapper on PATH
  # -P: do not prepend cwd to sys.path (avoids shadowing the install when run from a source checkout)
  cat > "$BIN_DIR/hyprgrok" <<EOF
#!/usr/bin/env bash
# HyprGrok launcher wrapper
export PYTHONPATH="$SHARE_DIR"
cd "$SHARE_DIR" || true
exec python3 -P -m hyprgrok "\$@"
EOF
  chmod +x "$BIN_DIR/hyprgrok"
  ok "Installed binary: $BIN_DIR/hyprgrok"

  # User config
  if [[ ! -f "$CONFIG_DIR/config.toml" ]] || [[ "$FORCE" == "1" ]]; then
    cp -f "$SHARE_DIR/configs/default.toml" "$CONFIG_DIR/config.toml"
    ok "Wrote $CONFIG_DIR/config.toml"
  else
    ok "Kept existing $CONFIG_DIR/config.toml"
  fi

  # Remember install location for uninstall
  cat > "$CONFIG_DIR/install-meta.toml" <<EOF
prefix = "$PREFIX"
share_dir = "$SHARE_DIR"
bin_dir = "$BIN_DIR"
version = "$VERSION"
installed_at = "$(date -Iseconds)"
EOF
}

strip_marked_block() {
  # $1 file, $2 begin, $3 end
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
}

append_block() {
  local file="$1" block_file="$2" begin="$3" end="$4"
  mkdir -p "$(dirname "$file")"
  touch "$file"
  strip_marked_block "$file" "$begin" "$end"
  {
    echo ""
    cat "$block_file"
    echo ""
  } >> "$file"
}

write_binds_with_absolute_path() {
  # Hyprland's environment often lacks ~/.local/bin — pin the wrapper path.
  local out="$1"
  local mode="$2" # lua | conf
  local bin="$BIN_DIR/hyprgrok"
  if [[ "$mode" == "lua" ]]; then
    cat > "$out" <<EOF
-- BEGIN HYPRGROK
-- HyprGrok keybinds (absolute path for reliable Super+G)
hl.bind("SUPER + G", hl.dsp.exec_cmd("$bin toggle"), { description = "HyprGrok: Toggle panel" })
hl.bind("SUPER + SHIFT + G", hl.dsp.exec_cmd("$bin session"), { description = "HyprGrok: Full Grok Build session" })
hl.bind("SUPER + ALT + G", hl.dsp.exec_cmd("$bin context"), { description = "HyprGrok: Print desktop context" })
hl.bind("SUPER + CTRL + G", hl.dsp.exec_cmd("$bin ask-window"), { description = "HyprGrok: Ask about current window" })
-- END HYPRGROK
EOF
  else
    cat > "$out" <<EOF
# BEGIN HYPRGROK
# HyprGrok keybinds (absolute path for reliable Super+G)
bind = SUPER, G, exec, $bin toggle
bind = SUPER SHIFT, G, exec, $bin session
bind = SUPER ALT, G, exec, $bin context
bind = SUPER CTRL, G, exec, $bin ask-window
# END HYPRGROK
EOF
  fi
}

configure_hyprland() {
  [[ "$INSTALL_HYPRLAND" == "1" ]] || { warn "Skipping Hyprland integration"; return 0; }

  info "Configuring Hyprland keybinds + window rules…"

  local binds_tmp
  binds_tmp="$(mktemp)"

  # Detect illogical-impulse / lua layout
  if [[ -f "$HYPR_DIR/hyprland.lua" ]] || [[ -d "$HYPR_DIR/custom" ]]; then
    write_binds_with_absolute_path "$binds_tmp" lua
    append_block "$HYPR_DIR/custom/keybinds.lua" \
      "$binds_tmp" "$LUA_BEGIN" "$LUA_END"
    append_block "$HYPR_DIR/custom/rules.lua" \
      "$SHARE_DIR/configs/hyprland/rules.lua" "$LUA_BEGIN" "$LUA_END"
    rm -f "$binds_tmp"
    ok "Updated $HYPR_DIR/custom/keybinds.lua and rules.lua (Lua config)"
    if command -v hyprctl >/dev/null 2>&1; then
      hyprctl reload >/dev/null 2>&1 || warn "Could not hyprctl reload — restart Hyprland or reload config"
    fi
    return 0
  fi

  # Traditional conf: write snippets and try to source them
  local conf_dir="$CONFIG_DIR/hyprland"
  mkdir -p "$conf_dir"
  write_binds_with_absolute_path "$conf_dir/binds.conf" conf
  cp -f "$SHARE_DIR/configs/hyprland/windowrules.conf" "$conf_dir/windowrules.conf"
  rm -f "$binds_tmp"

  local main_conf=""
  for candidate in "$HYPR_DIR/hyprland.conf" "$HYPR_DIR/hypr.conf" "$HYPR_DIR/config.conf"; do
    if [[ -f "$candidate" ]]; then
      main_conf="$candidate"
      break
    fi
  done

  if [[ -n "$main_conf" ]]; then
    strip_marked_block "$main_conf" "$MARKER_BEGIN" "$MARKER_END"
    {
      echo ""
      echo "$MARKER_BEGIN"
      echo "source = $conf_dir/binds.conf"
      echo "source = $conf_dir/windowrules.conf"
      echo "$MARKER_END"
    } >> "$main_conf"
    ok "Sourced HyprGrok conf from $main_conf"
    if command -v hyprctl >/dev/null 2>&1; then
      hyprctl reload >/dev/null 2>&1 || true
    fi
  else
    warn "No hyprland.conf found. Manually source:"
    echo "  source = $conf_dir/binds.conf"
    echo "  source = $conf_dir/windowrules.conf"
  fi
}

path_hint() {
  case ":$PATH:" in
    *":$BIN_DIR:"*) ok "$BIN_DIR is on PATH" ;;
    *)
      warn "$BIN_DIR is not on PATH"
      echo "  Add this to your shell rc:"
      echo "    export PATH=\"$BIN_DIR:\$PATH\""
      ;;
  esac
}

main() {
  echo ""
  echo "  HyprGrok v${VERSION} — Grok Build companion for Hyprland"
  echo ""
  check_deps
  install_files
  configure_hyprland
  path_hint

  # Ensure PATH for this session smoke test
  export PATH="$BIN_DIR:$PATH"
  export PYTHONPATH="$SHARE_DIR${PYTHONPATH:+:$PYTHONPATH}"

  info "Running doctor…"
  if "$BIN_DIR/hyprgrok" doctor; then
    ok "doctor passed"
  else
    warn "doctor reported issues (often missing grok — install Grok Build)"
  fi

  cat <<EOF

${GRN}Install complete.${RST}

  Toggle panel:     ${CYN}Super + G${RST}
  Full session:     ${CYN}Super + Shift + G${RST}
  Ask about window: ${CYN}Super + Ctrl + G${RST}
  CLI:              ${CYN}hyprgrok toggle${RST}
                    ${CYN}hyprgrok ask "hello"${RST}
                    ${CYN}hyprgrok session${RST}
                    ${CYN}hyprgrok ask-window${RST}
                    ${CYN}hyprgrok status --waybar${RST}
                    ${CYN}hyprgrok doctor${RST}

  Waybar snippet:   ${CYN}$SHARE_DIR/configs/waybar/hyprgrok.jsonc${RST}

  Config:           ${CYN}$CONFIG_DIR/config.toml${RST}
  Uninstall:        ${CYN}hyprgrok-uninstall${RST} or run uninstall.sh

HyprGrok launches the official ${CYN}grok${RST} binary only — it never handles xAI API keys.

EOF

  # Install uninstall helper next to hyprgrok
  if [[ -f "$SCRIPT_DIR/uninstall.sh" ]]; then
    install -m 755 "$SCRIPT_DIR/uninstall.sh" "$BIN_DIR/hyprgrok-uninstall"
    ok "Installed $BIN_DIR/hyprgrok-uninstall"
  fi
}

main "$@"
