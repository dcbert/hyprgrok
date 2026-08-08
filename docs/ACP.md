# Future: Agent Client Protocol (ACP) integration

HyprGrok launches and enhances **official Grok Build** via:

- Headless: `grok -p`
- Interactive: full TUI in a terminal
- Desktop context injection

## Why ACP later?

When Grok Build’s ACP surface is stable enough for third-party clients, HyprGrok can:

1. Attach to running agent sessions without scraping TUI output  
2. Stream partial messages into the glass panel  
3. Offer multi-session switcher with live status  
4. Expose Hyprland tools (`hyprgrok hypr …`) as agent tools / MCP  

## Current posture

- Do **not** reimplement the agent loop  
- Do **not** store xAI API keys  
- Keep a thin launcher abstraction in `hyprgrok/launcher.py` so ACP can slot in without rewriting the panel  

## Proposed adapter shape (not implemented)

```
class GrokBackend(Protocol):
    def headless(prompt, cwd) -> str: ...
    def start_interactive(cwd, prompt) -> SessionHandle: ...
    def attach_acp(session_id) -> AcpStream: ...  # future
```

Track upstream Grok Build release notes before investing.
