-- BEGIN HYPRGROK
-- HyprGrok window rules for illogical-impulse / hyprland.lua setups
-- Appended to ~/.config/hypr/custom/rules.lua by install.sh

-- Glass companion panel
hl.window_rule({ match = { title = "^(HyprGrok)$" }, float = true })
hl.window_rule({ match = { title = "^(HyprGrok)$" }, pin = true })
hl.window_rule({ match = { title = "^(HyprGrok)$" }, size = { 420, 720 } })
hl.window_rule({ match = { title = "^(HyprGrok)$" }, move = { "(monitor_w-440)", 40 } })
hl.window_rule({ match = { title = "^(HyprGrok)$" }, opacity = 0.94 })

-- Optional ruled Grok Build terminal sessions
hl.window_rule({ match = { class = "^(hyprgrok-session)$" }, float = true })
hl.window_rule({ match = { class = "^(hyprgrok-session)$" }, size = { "(monitor_w*0.70)", "(monitor_h*0.75)" } })
hl.window_rule({ match = { class = "^(hyprgrok-session)$" }, center = true })

-- END HYPRGROK
