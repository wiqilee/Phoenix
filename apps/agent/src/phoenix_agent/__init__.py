"""Phoenix Agent - Autonomous GitLab pipeline repair agent."""

__version__ = "0.1.0"
__author__ = "Wiqi Lee"

from phoenix_agent.adk_agents import phoenix_coordinator as root_agent

__all__ = ["root_agent"]
