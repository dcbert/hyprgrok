-- BEGIN HYPRGROK
-- HyprGrok keybinds for illogical-impulse / hyprland.lua setups
-- Appended to ~/.config/hypr/custom/keybinds.lua by install.sh

hl.bind("SUPER + G", hl.dsp.exec_cmd("hyprgrok toggle"), { description = "HyprGrok: Toggle panel" })
hl.bind("SUPER + SHIFT + G", hl.dsp.exec_cmd("hyprgrok session"), { description = "HyprGrok: Full Grok Build session" })
hl.bind("SUPER + ALT + G", hl.dsp.exec_cmd("hyprgrok context"), { description = "HyprGrok: Print desktop context" })
hl.bind("SUPER + CTRL + G", hl.dsp.exec_cmd("hyprgrok ask-window"), { description = "HyprGrok: Ask about current window" })

-- END HYPRGROK
