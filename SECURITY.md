# Security Policy

## What HyprGrok does *not* do

- Call the xAI HTTP API  
- Store, proxy, or log xAI API keys  
- Bind its panel server outside `127.0.0.1`  

Official Grok Build (`grok`) owns authentication and model access.

## Trust boundaries

| Component | Risk notes |
|-----------|------------|
| Panel HTTP server | Localhost only; serves static UI + control API |
| `hyprgrok hypr dispatch` | Allowlisted dispatch prefixes only |
| Grok session store | **Read-only** access to `~/.grok/sessions` |
| Browser panel | Runs as a normal user app (`--app=` / new window) |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Email or open a **private** security advisory on the GitHub repository  
(https://github.com/dcbert/hyprgrok/security) with:

- Description and impact  
- Reproduction steps  
- Affected version / commit if known  

We will acknowledge reports as soon as practical and coordinate a fix before public disclosure when appropriate.
