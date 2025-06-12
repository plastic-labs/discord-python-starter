"""
GitHub Tool Configuration

Contains configuration settings for GitHub repository management,
including repository lists, cache settings, and timeout values.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
import os

# Repository configuration
REPOS_TO_CLONE = [
    "https://github.com/plastic-labs/honcho",
    "https://github.com/plastic-labs/honcho-python", 
    "https://github.com/plastic-labs/honcho-node",
]

# Default branches for each repository
DEFAULT_BRANCHES: Dict[str, str] = {
    "https://github.com/plastic-labs/honcho": "main",
    "https://github.com/plastic-labs/honcho-python": "main",
    "https://github.com/plastic-labs/honcho-node": "main", 
}

# Cache and timeout settings
CACHE_DIR = Path(".cache/repos")
CLONE_TIMEOUT = 300  # 5 minutes in seconds
FETCH_TIMEOUT = 120  # 2 minutes in seconds
UPDATE_TIMEOUT = 180  # 3 minutes in seconds

# File search settings
MAX_FILE_SIZE_MB = 10  # Maximum file size to read in MB
SEARCH_TIMEOUT = 60  # Search operation timeout in seconds
MAX_SEARCH_RESULTS = 1000  # Maximum number of search results to return

# Git operation settings
GIT_CLONE_DEPTH = 1  # Use shallow clone by default
GIT_FETCH_TAGS = False  # Don't fetch tags by default
GIT_SUBMODULES = False  # Don't clone submodules by default


@dataclass
class GitHubConfig:
    """
    Configuration class for GitHub tool settings.
    
    Attributes:
        repos_to_clone: List of repository URLs to manage
        cache_dir: Directory for storing cloned repositories
        default_branches: Mapping of repo URLs to their default branches
        clone_timeout: Timeout for git clone operations in seconds
        fetch_timeout: Timeout for git fetch operations in seconds
        update_timeout: Timeout for git pull operations in seconds
        max_file_size_mb: Maximum file size to read in MB
        search_timeout: Search operation timeout in seconds
        max_search_results: Maximum number of search results to return
        git_clone_depth: Depth for shallow clones (None for full clone)
        git_fetch_tags: Whether to fetch tags during operations
        git_submodules: Whether to clone/update submodules
    """
    
    repos_to_clone: List[str] = None
    cache_dir: Path = None
    default_branches: Dict[str, str] = None
    clone_timeout: int = CLONE_TIMEOUT
    fetch_timeout: int = FETCH_TIMEOUT
    update_timeout: int = UPDATE_TIMEOUT
    max_file_size_mb: int = MAX_FILE_SIZE_MB
    search_timeout: int = SEARCH_TIMEOUT
    max_search_results: int = MAX_SEARCH_RESULTS
    git_clone_depth: Optional[int] = GIT_CLONE_DEPTH
    git_fetch_tags: bool = GIT_FETCH_TAGS
    git_submodules: bool = GIT_SUBMODULES
    
    def __post_init__(self):
        """Initialize default values after instantiation."""
        if self.repos_to_clone is None:
            self.repos_to_clone = REPOS_TO_CLONE.copy()
        if self.cache_dir is None:
            self.cache_dir = CACHE_DIR
        if self.default_branches is None:
            self.default_branches = DEFAULT_BRANCHES.copy()
            
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_env(cls) -> "GitHubConfig":
        """
        Create configuration from environment variables.
        
        Returns:
            GitHubConfig instance with values from environment variables
        """
        return cls(
            cache_dir=Path(os.getenv("GITHUB_TOOL_CACHE_DIR", CACHE_DIR)),
            clone_timeout=int(os.getenv("GITHUB_TOOL_CLONE_TIMEOUT", CLONE_TIMEOUT)),
            fetch_timeout=int(os.getenv("GITHUB_TOOL_FETCH_TIMEOUT", FETCH_TIMEOUT)),
            update_timeout=int(os.getenv("GITHUB_TOOL_UPDATE_TIMEOUT", UPDATE_TIMEOUT)),
            max_file_size_mb=int(os.getenv("GITHUB_TOOL_MAX_FILE_SIZE_MB", MAX_FILE_SIZE_MB)),
            search_timeout=int(os.getenv("GITHUB_TOOL_SEARCH_TIMEOUT", SEARCH_TIMEOUT)),
            max_search_results=int(os.getenv("GITHUB_TOOL_MAX_SEARCH_RESULTS", MAX_SEARCH_RESULTS)),
            git_clone_depth=int(os.getenv("GITHUB_TOOL_CLONE_DEPTH", GIT_CLONE_DEPTH)) if os.getenv("GITHUB_TOOL_CLONE_DEPTH") else None,
            git_fetch_tags=os.getenv("GITHUB_TOOL_FETCH_TAGS", "false").lower() == "true",
            git_submodules=os.getenv("GITHUB_TOOL_SUBMODULES", "false").lower() == "true",
        )
    
    def get_repo_name(self, repo_url: str) -> str:
        """
        Extract repository name from URL.
        
        Args:
            repo_url: The repository URL
            
        Returns:
            Repository name (e.g., 'honcho' from 'https://github.com/plastic-labs/honcho')
        """
        return repo_url.rstrip("/").split("/")[-1]
    
    def get_local_repo_path(self, repo_url: str) -> Path:
        """
        Get the local path for a repository.
        
        Args:
            repo_url: The repository URL
            
        Returns:
            Path where the repository should be/is cloned
        """
        repo_name = self.get_repo_name(repo_url)
        return self.cache_dir / repo_name
    
    def get_default_branch(self, repo_url: str) -> str:
        """
        Get the default branch for a repository.
        
        Args:
            repo_url: The repository URL
            
        Returns:
            Default branch name (defaults to 'main' if not specified)
        """
        return self.default_branches.get(repo_url, "main") 