"""ADK entry point for the Phoenix root agent.

`adk web` and `adk run` discover an agent app by importing
`<app_name>.agent` and reading the module-level `root_agent` symbol.

Run the Dev UI from the `apps/agent/src` directory so the app name
resolves to `phoenix_agent`:

    cd apps/agent/src
    adk web

Then open http://127.0.0.1:8000 and pick `phoenix_agent` in the
app dropdown (or go straight to /dev-ui/?app=phoenix_agent).

For a local smoke test without the GitLab MCP OAuth handshake, set
PHOENIX_DISABLE_MCP=1 in the root .env first.
"""

from __future__ import annotations

from phoenix_agent.adk_agents import phoenix_coordinator

# The symbol the ADK loader looks for: `phoenix_agent.agent.root_agent`
root_agent = phoenix_coordinator

__all__ = ["root_agent"]
