"""
GitHub Tool Exceptions

Custom exception classes for GitHub tool operations.
Provides specific error types for different failure scenarios.
"""

from typing import Optional


class GitHubToolError(Exception):
    """
    Base exception for all GitHub tool operations.
    
    This is the parent exception for all GitHub tool related errors.
    It provides a consistent interface for error handling across the tool.
    
    Attributes:
        message: Human-readable error message
        operation: The operation that failed (e.g., 'clone', 'search', 'read')
        repo_url: The repository URL if applicable
        details: Additional error details
    """
    
    def __init__(
        self, 
        message: str, 
        operation: Optional[str] = None,
        repo_url: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.message = message
        self.operation = operation
        self.repo_url = repo_url
        self.details = details
        
        # Build comprehensive error message
        parts = [message]
        if operation:
            parts.append(f"Operation: {operation}")
        if repo_url:
            parts.append(f"Repository: {repo_url}")
        if details:
            parts.append(f"Details: {details}")
            
        super().__init__(" | ".join(parts))


class RepoNotFoundError(GitHubToolError):
    """
    Raised when a repository cannot be found or accessed.
    
    This can occur when:
    - Repository URL is invalid
    - Repository is private and credentials are insufficient
    - Repository has been deleted or moved
    - Network issues prevent access
    """
    
    def __init__(self, repo_url: str, details: Optional[str] = None):
        super().__init__(
            f"Repository not found or inaccessible: {repo_url}",
            operation="repository_access",
            repo_url=repo_url,
            details=details
        )


class CloneError(GitHubToolError):
    """
    Raised when repository cloning fails.
    
    This can occur when:
    - Git clone command fails
    - Insufficient disk space
    - Network connectivity issues
    - Authentication failures
    - Invalid repository URL
    """
    
    def __init__(self, repo_url: str, details: Optional[str] = None):
        super().__init__(
            f"Failed to clone repository: {repo_url}",
            operation="clone",
            repo_url=repo_url,
            details=details
        )


class UpdateError(GitHubToolError):
    """
    Raised when repository update operations fail.
    
    This can occur when:
    - Git fetch/pull commands fail
    - Merge conflicts cannot be resolved
    - Local repository is in an invalid state
    - Network connectivity issues
    - Remote repository has been force-pushed
    """
    
    def __init__(self, repo_url: str, details: Optional[str] = None):
        super().__init__(
            f"Failed to update repository: {repo_url}",
            operation="update",
            repo_url=repo_url,
            details=details
        )


class FileNotFoundError(GitHubToolError):
    """
    Raised when a requested file cannot be found or read.
    
    This can occur when:
    - File path does not exist in the repository
    - File exists but is not readable (permissions, binary file, etc.)
    - Repository is not cloned locally
    - File path is outside repository bounds
    """
    
    def __init__(self, file_path: str, repo_url: Optional[str] = None, details: Optional[str] = None):
        super().__init__(
            f"File not found or not readable: {file_path}",
            operation="file_read",
            repo_url=repo_url,
            details=details
        )
        self.file_path = file_path


class RateLimitError(GitHubToolError):
    """
    Raised when rate limits are exceeded.
    
    This can occur when:
    - GitHub API rate limits are exceeded
    - Internal tool rate limits are exceeded
    - Too many concurrent operations
    - Automated usage limits reached
    """
    
    def __init__(
        self, 
        operation: str, 
        retry_after: Optional[int] = None, 
        details: Optional[str] = None
    ):
        message = f"Rate limit exceeded for operation: {operation}"
        if retry_after:
            message += f" (retry after {retry_after} seconds)"
            
        super().__init__(
            message,
            operation=operation,
            details=details
        )
        self.retry_after = retry_after


class SearchError(GitHubToolError):
    """
    Raised when search operations fail.
    
    This can occur when:
    - Search pattern is invalid (malformed regex)
    - Search timeout is exceeded
    - Repository is not available for searching
    - Search index is corrupted or missing
    """
    
    def __init__(self, pattern: str, details: Optional[str] = None):
        super().__init__(
            f"Search operation failed for pattern: {pattern}",
            operation="search",
            details=details
        )
        self.pattern = pattern


class ParseError(GitHubToolError):
    """
    Raised when file parsing or code analysis fails.
    
    This can occur when:
    - File content is not valid for the expected language
    - Syntax errors in the source code
    - Encoding issues
    - Unsupported file format
    """
    
    def __init__(self, file_path: str, language: Optional[str] = None, details: Optional[str] = None):
        message = f"Failed to parse file: {file_path}"
        if language:
            message += f" (language: {language})"
            
        super().__init__(
            message,
            operation="parse",
            details=details
        )
        self.file_path = file_path
        self.language = language


class CacheError(GitHubToolError):
    """
    Raised when cache operations fail.
    
    This can occur when:
    - Cache directory is not writable
    - Cache corruption
    - Insufficient disk space for cache
    - Cache key conflicts
    """
    
    def __init__(self, cache_operation: str, details: Optional[str] = None):
        super().__init__(
            f"Cache operation failed: {cache_operation}",
            operation="cache",
            details=details
        )
        self.cache_operation = cache_operation


class AuthenticationError(GitHubToolError):
    """
    Raised when authentication to GitHub fails.
    
    This can occur when:
    - Invalid or expired GitHub token
    - Insufficient permissions for private repositories
    - Token missing required scopes
    - Two-factor authentication required
    """
    
    def __init__(self, repo_url: Optional[str] = None, details: Optional[str] = None):
        super().__init__(
            "GitHub authentication failed",
            operation="authentication",
            repo_url=repo_url,
            details=details
        )


class ConfigurationError(GitHubToolError):
    """
    Raised when configuration is invalid or missing.
    
    This can occur when:
    - Required configuration values are missing
    - Configuration values are invalid
    - Configuration file is malformed
    - Environment variable conflicts
    """
    
    def __init__(self, config_item: str, details: Optional[str] = None):
        super().__init__(
            f"Configuration error: {config_item}",
            operation="configuration",
            details=details
        )
        self.config_item = config_item 