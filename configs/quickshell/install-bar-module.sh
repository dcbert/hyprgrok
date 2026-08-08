#!/usr/bin/env bash
# Install HyprGrok into Illogical Impulse Quickshell bar
set -euo pipefail
QS_II="${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/ii"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ii/bar/HyprGrokButton.qml"
if [[ ! -d "$QS_II/modules/ii/bar" ]]; then
  echo "Illogical Impulse Quickshell not found at $QS_II"
  exit 1
fi
install -m 644 "$SRC" "$QS_II/modules/ii/bar/HyprGrokButton.qml"
echo "Installed HyprGrokButton.qml"
echo "If the robot icon is missing from the bar, ensure showHyprGrok is true in"
echo "  Settings → Bar → Utility buttons → HyprGrok"
echo "Then reload:  killall qs; qs -c ii &"
