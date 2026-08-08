-- BEGIN HYPRGROK
-- HyprGrok window rules for illogical-impulse / hyprland.lua setups
-- Appended to ~/.config/hypr/custom/rules.lua by install.sh

-- Glass companion panel — fixed layout so it never opens off-screen.
-- NOTE: do not use window_w in move (race: move runs before final size).
hl.window_rule({ match = { title = "^(HyprGrok)$" }, float = true })
hl.window_rule({ match = { title = "^(HyprGrok)$" }, pin = true })
hl.window_rule({ match = { title = "^(HyprGrok)$" }, size = { 560, "(monitor_h*0.88)" } })
hl.window_rule({ match = { title = "^(HyprGrok)$" }, move = { "(monitor_w-576)", 48 } })
hl.window_rule({ match = { title = "^(HyprGrok)$" }, opacity = 0.96 })

-- Optional ruled Grok Build terminal sessions
hl.window_rule({ match = { class = "^(hyprgrok-session)$" }, float = true })
hl.window_rule({ match = { class = "^(hyprgrok-session)$" }, size = { "(monitor_w*0.70)", "(monitor_h*0.75)" } })
hl.window_rule({ match = { class = "^(hyprgrok-session)$" }, center = true })

-- END HYPRGROK
