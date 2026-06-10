"""Phoenix Agent - Autonomous GitLab pipeline repair agent."""

__version__ = "0.1.0"
__author__ = "Wiqi Lee"

# Expose the ADK entry point at package level.
# `adk web` resolves `phoenix_agent.agent.root_agent` first and
# `phoenix_agent.root_agent` as a fallback, so both paths work.
from phoenix_agent import agent
from phoenix_agent.agent import root_agent

__all__ = ["agent", "root_agent"]
