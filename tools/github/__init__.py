"""
GitHub Tool Package

Provides comprehensive GitHub repository management, code searching, and analysis
capabilities for Discord bots. Includes repository cloning, file searching,
pattern matching, and code navigation features.
"""

from .github_tool import GitHubTool
from .config import GitHubConfig
from .exceptions import (
    GitHubToolError,
    RepoNotFoundError,
    CloneError,
    UpdateError,
    FileNotFoundError,
    RateLimitError,
)

__version__ = "0.1.0"

__all__ = [
    "GitHubTool",
    "GitHubConfig", 
    "GitHubToolError",
    "RepoNotFoundError",
    "CloneError",
    "UpdateError",
    "FileNotFoundError",
    "RateLimitError",
] 