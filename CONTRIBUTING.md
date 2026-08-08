# Contributing to HyprGrok

Thanks for helping make Grok Build feel at home on Hyprland.

## Principles

1. Prefer the real `grok` binary — never call the xAI API directly  
2. Never store or handle API keys  
3. Keep the panel fast and the install reversible  
4. Hyprland binds/rules must stay in marked `BEGIN/END HYPRGROK` blocks  

## Dev setup

```bash
git clone https://github.com/dcbert/hyprgrok.git
cd hyprgrok
export PYTHONPATH=.
python3 -m hyprgrok doctor
python3 -m unittest discover -s tests -v
```

Run from a checkout:

```bash
python3 -m hyprgrok toggle
python3 -m hyprgrok serve --port 8765
```

Or reinstall into `~/.local`:

```bash
./install.sh --no-hyprland   # or full install
```

## Project layout

```
hyprgrok/          # Python package
ui/                # Glass panel (static HTML/CSS/JS)
configs/           # Default TOML + Hyprland / Waybar / Quickshell snippets
docs/              # Specs and integration guides
tests/             # unittest suite
install.sh         # Primary install path for end users
```

## Pull requests

- Keep PRs focused (one concern per PR when possible)  
- Add/adjust tests for non-trivial logic  
- Update README or docs when behavior or keybinds change  
- Run `python3 -m unittest discover -s tests -v` before pushing  

## Code style

- Python 3.12+, stdlib-first (no hard deps beyond what Hyprland users already have)  
- Type hints on public functions where practical  
- Fail gracefully when `grok` / `hyprctl` / browsers are missing  

## Reporting bugs

Include:

- Distro + Hyprland version  
- `hyprgrok doctor` output  
- Whether you use Illogical Impulse / Quickshell or plain conf  
- Relevant lines from `~/.config/hyprgrok/panel.log`  

Security issues: see [SECURITY.md](SECURITY.md).
