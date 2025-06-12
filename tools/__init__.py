"""
Tools package for Discord bot integrations.

This package provides a collection of tools that can be integrated into Discord bots
to extend their functionality. Each tool is designed to be modular, reusable, and
memory-aware through integration with the Honcho memory system.
"""

from typing import Dict, Type, Any

__version__ = "0.1.0"

# Tool registry for future expansion - import lazily to avoid circular imports
def _get_available_tools():
    from .github import GitHubTool
    return {
        "github": GitHubTool,
    }

AVAILABLE_TOOLS: Dict[str, Type[Any]] = _get_available_tools()

__all__ = ["AVAILABLE_TOOLS"] 