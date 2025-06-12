"""
GitHub Tool Implementation

Core GitHub tool class providing repository management, file searching,
and code analysis capabilities for Discord bots.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any
from enum import Enum

from .config import GitHubConfig
from .exceptions import (
    GitHubToolError,
    RepoNotFoundError,
    CloneError,
    UpdateError,
    ConfigurationError,
)

# Configure logging
logger = logging.getLogger(__name__)


class RepoStatus(Enum):
    """Enumeration of repository states."""
    NOT_CLONED = "not_cloned"
    CLONING = "cloning"
    CLONED = "cloned"
    UPDATING = "updating"
    ERROR = "error"
    STALE = "stale"


@dataclass
class RepoInfo:
    """
    Information about a managed repository.
    
    Attributes:
        url: Repository URL
        local_path: Local filesystem path
        status: Current repository status
        last_updated: When the repository was last updated
        last_checked: When the repository status was last checked
        branch: Current branch name
        commit_hash: Current commit hash
        error_message: Last error message if status is ERROR
    """
    url: str
    local_path: Path
    status: RepoStatus = RepoStatus.NOT_CLONED
    last_updated: Optional[datetime] = None
    last_checked: Optional[datetime] = None
    branch: Optional[str] = None
    commit_hash: Optional[str] = None
    error_message: Optional[str] = None
    
    def is_available(self) -> bool:
        """Check if repository is available for operations."""
        return self.status == RepoStatus.CLONED
    
    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Check if repository needs updating."""
        if not self.last_updated:
            return True
        age_hours = (datetime.now() - self.last_updated).total_seconds() / 3600
        return age_hours > max_age_hours


@dataclass
class ToolStats:
    """
    Statistics and metrics for tool operations.
    
    Attributes:
        repos_managed: Number of repositories being managed
        total_clones: Total number of clone operations performed
        total_updates: Total number of update operations performed
        total_searches: Total number of search operations performed
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
        errors_encountered: Total number of errors encountered
        last_operation_time: When the last operation was performed
    """
    repos_managed: int = 0
    total_clones: int = 0
    total_updates: int = 0
    total_searches: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors_encountered: int = 0
    last_operation_time: Optional[datetime] = None
    
    def record_operation(self, operation_type: str):
        """Record that an operation was performed."""
        self.last_operation_time = datetime.now()
        if operation_type == "clone":
            self.total_clones += 1
        elif operation_type == "update":
            self.total_updates += 1
        elif operation_type == "search":
            self.total_searches += 1
    
    def record_error(self):
        """Record that an error occurred."""
        self.errors_encountered += 1


class GitHubTool:
    """
    Main GitHub tool class for repository management and code analysis.
    
    This class provides a comprehensive interface for working with GitHub repositories
    in the context of a Discord bot. It handles repository cloning, updating, searching,
    and provides integration hooks for memory systems like Honcho.
    
    Key Features:
    - Asynchronous repository cloning and updating
    - File and code pattern searching
    - Repository state management
    - Configurable caching and timeouts
    - Integration-ready for Discord bots
    - Memory system integration support
    
    Attributes:
        config: Configuration object containing settings
        repos: Dictionary mapping repository URLs to RepoInfo objects
        stats: Statistics and metrics object
        _initialized: Whether the tool has been initialized
        _clone_locks: Locks to prevent concurrent cloning of same repo
    """
    
    def __init__(
        self, 
        config: Optional[GitHubConfig] = None,
        repos: Optional[List[str]] = None
    ):
        """
        Initialize the GitHub tool.
        
        Args:
            config: Configuration object. If None, uses default configuration.
            repos: List of repository URLs to manage. If None, uses config default.
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        self.config = config or GitHubConfig()
        
        # Override config repos if provided
        if repos is not None:
            self.config.repos_to_clone = repos
            
        # Initialize repository tracking
        self.repos: Dict[str, RepoInfo] = {}
        self._initialize_repos()
        
        # Initialize statistics
        self.stats = ToolStats(repos_managed=len(self.repos))
        
        # State management
        self._initialized = False
        self._clone_locks: Dict[str, asyncio.Lock] = {}
        
        # Validate configuration
        self._validate_config()
        
        logger.info(f"GitHubTool initialized with {len(self.repos)} repositories")
    
    def _initialize_repos(self):
        """Initialize repository tracking from configuration."""
        for repo_url in self.config.repos_to_clone:
            local_path = self.config.get_local_repo_path(repo_url)
            self.repos[repo_url] = RepoInfo(
                url=repo_url,
                local_path=local_path,
                branch=self.config.get_default_branch(repo_url)
            )
            # Initialize clone lock for each repo
            self._clone_locks[repo_url] = asyncio.Lock()
    
    def _validate_config(self):
        """Validate the configuration settings."""
        if not self.config.repos_to_clone:
            raise ConfigurationError(
                "repos_to_clone", 
                "At least one repository must be configured"
            )
        
        if not self.config.cache_dir:
            raise ConfigurationError(
                "cache_dir",
                "Cache directory must be specified"
            )
        
        # Ensure cache directory exists and is writable
        try:
            self.config.cache_dir.mkdir(parents=True, exist_ok=True)
            test_file = self.config.cache_dir / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
        except (OSError, PermissionError) as e:
            raise ConfigurationError(
                "cache_dir",
                f"Cache directory is not writable: {e}"
            )
    
    # Properties for accessing repo states
    
    @property
    def available_repos(self) -> Dict[str, RepoInfo]:
        """Get repositories that are available for operations."""
        return {url: info for url, info in self.repos.items() if info.is_available()}
    
    @property
    def cloned_repos(self) -> Dict[str, RepoInfo]:
        """Get repositories that have been cloned."""
        return {
            url: info for url, info in self.repos.items() 
            if info.status == RepoStatus.CLONED
        }
    
    @property
    def stale_repos(self) -> Dict[str, RepoInfo]:
        """Get repositories that need updating."""
        return {
            url: info for url, info in self.repos.items() 
            if info.is_stale()
        }
    
    @property
    def error_repos(self) -> Dict[str, RepoInfo]:
        """Get repositories that have errors."""
        return {
            url: info for url, info in self.repos.items() 
            if info.status == RepoStatus.ERROR
        }
    
    # Abstract methods that will be implemented in future prompts
    
    async def initialize(self) -> bool:
        """
        Initialize the tool and ensure repositories are ready.
        
        This method should be called before using the tool. It performs
        initial setup and ensures all configured repositories are available.
        
        Returns:
            True if initialization was successful, False otherwise
            
        Raises:
            GitHubToolError: If initialization fails
        """
        if self._initialized:
            return True
            
        try:
            logger.info("Initializing GitHubTool...")
            
            # Check repository states
            await self._check_repo_states()
            
            # Clone missing repositories if needed
            missing_repos = [
                url for url, info in self.repos.items() 
                if info.status == RepoStatus.NOT_CLONED
            ]
            
            if missing_repos:
                logger.info(f"Found {len(missing_repos)} repositories to clone")
                # This will be implemented in the next prompt
                # await self.ensure_repos_cloned()
            
            self._initialized = True
            logger.info("GitHubTool initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"GitHubTool initialization failed: {e}")
            raise GitHubToolError(
                "Failed to initialize GitHub tool",
                operation="initialize",
                details=str(e)
            )
    
    async def _check_repo_states(self):
        """Check the current state of all managed repositories."""
        for repo_url, repo_info in self.repos.items():
            repo_info.last_checked = datetime.now()
            
            if repo_info.local_path.exists() and (repo_info.local_path / ".git").exists():
                repo_info.status = RepoStatus.CLONED
                # Get additional info about the repo
                try:
                    # This will be expanded in future prompts
                    pass
                except Exception as e:
                    logger.warning(f"Could not get repo info for {repo_url}: {e}")
            else:
                repo_info.status = RepoStatus.NOT_CLONED
    
    def get_repo_info(self, repo_url: str) -> Optional[RepoInfo]:
        """
        Get information about a managed repository.
        
        Args:
            repo_url: The repository URL
            
        Returns:
            RepoInfo object if repository is managed, None otherwise
        """
        return self.repos.get(repo_url)
    
    def add_repository(self, repo_url: str, branch: Optional[str] = None) -> RepoInfo:
        """
        Add a new repository to be managed.
        
        Args:
            repo_url: The repository URL to add
            branch: The branch to use (defaults to 'main')
            
        Returns:
            RepoInfo object for the new repository
            
        Raises:
            ConfigurationError: If repository URL is invalid
        """
        if repo_url in self.repos:
            return self.repos[repo_url]
        
        # Validate URL format
        if not repo_url.startswith(("https://", "git@")):
            raise ConfigurationError(
                "repository_url",
                f"Invalid repository URL format: {repo_url}"
            )
        
        local_path = self.config.get_local_repo_path(repo_url)
        repo_info = RepoInfo(
            url=repo_url,
            local_path=local_path,
            branch=branch or "main"
        )
        
        self.repos[repo_url] = repo_info
        self._clone_locks[repo_url] = asyncio.Lock()
        self.stats.repos_managed = len(self.repos)
        
        logger.info(f"Added repository to management: {repo_url}")
        return repo_info
    
    def remove_repository(self, repo_url: str) -> bool:
        """
        Remove a repository from management.
        
        Args:
            repo_url: The repository URL to remove
            
        Returns:
            True if repository was removed, False if it wasn't managed
        """
        if repo_url not in self.repos:
            return False
        
        del self.repos[repo_url]
        if repo_url in self._clone_locks:
            del self._clone_locks[repo_url]
        
        self.stats.repos_managed = len(self.repos)
        logger.info(f"Removed repository from management: {repo_url}")
        return True
    
    def get_stats(self) -> ToolStats:
        """
        Get current tool statistics and metrics.
        
        Returns:
            ToolStats object with current metrics
        """
        return self.stats
    
    def __repr__(self) -> str:
        """String representation of the GitHubTool."""
        return (
            f"GitHubTool(repos={len(self.repos)}, "
            f"available={len(self.available_repos)}, "
            f"initialized={self._initialized})"
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Cleanup operations if needed
        pass 