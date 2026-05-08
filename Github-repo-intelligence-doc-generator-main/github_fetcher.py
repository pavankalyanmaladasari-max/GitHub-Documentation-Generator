"""
GitHub Repository Fetcher
Recursively fetches repository tree and file contents via GitHub REST API.
"""

import re
import time
import base64
from typing import Optional
from urllib.parse import urlparse

import requests

MAX_FILES = 100
MAX_FILE_SIZE_BYTES = 200 * 1024  # 200KB

SKIP_DIRECTORIES = {
    "node_modules",
    ".git",
    "dist",
    "build",
    ".next",
    "coverage",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".env",
}

GITHUB_API_BASE = "https://api.github.com"


def parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL."""
    url = url.strip().rstrip("/")
    # Handle various GitHub URL formats
    patterns = [
        r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
        r"github\.com/([^/]+)/([^/]+?)(?:/tree/.*)?$",
        r"github\.com/([^/]+)/([^/]+?)(?:/blob/.*)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    raise ValueError(
        f"Invalid GitHub URL: {url}. Expected format: https://github.com/owner/repo"
    )


def _get_headers(token: Optional[str] = None) -> dict:
    """Build request headers with optional auth token."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _handle_rate_limit(response: requests.Response) -> None:
    """Check rate limit and sleep if needed."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    if remaining is not None and int(remaining) < 5:
        reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
        wait_seconds = max(reset_time - int(time.time()), 1)
        if wait_seconds > 120:
            raise RuntimeError(
                f"GitHub API rate limit exceeded. Resets in {wait_seconds}s. "
                "Provide a GitHub token to increase limits."
            )
        time.sleep(min(wait_seconds, 60))


def _api_get(url: str, headers: dict, params: dict = None) -> dict:
    """Make a GET request with error handling."""
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
    except requests.exceptions.Timeout:
        raise RuntimeError("GitHub API request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to GitHub API. Check your network.")

    _handle_rate_limit(response)

    if response.status_code == 404:
        raise ValueError(
            "Repository not found. Ensure the URL is correct and the repo is public."
        )
    if response.status_code == 403:
        raise RuntimeError(
            "GitHub API rate limit reached. Provide a GitHub token or wait."
        )
    if response.status_code != 200:
        raise RuntimeError(
            f"GitHub API error {response.status_code}: {response.text[:200]}"
        )
    return response.json()


def get_default_branch(owner: str, repo: str, token: Optional[str] = None) -> str:
    """Fetch the default branch of a repository."""
    headers = _get_headers(token)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    data = _api_get(url, headers)
    return data.get("default_branch", "main")


def _should_skip_path(path: str) -> bool:
    """Check if a file path should be skipped based on directory rules."""
    parts = path.split("/")
    for part in parts:
        if part in SKIP_DIRECTORIES:
            return True
    return False


def fetch_repo_tree(
    owner: str, repo: str, branch: str, token: Optional[str] = None
) -> list[dict]:
    """
    Fetch recursive repository tree.
    Returns list of file entries (blobs only, filtered).
    """
    headers = _get_headers(token)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}"
    data = _api_get(url, headers, params={"recursive": "1"})

    if data.get("truncated", False):
        pass  # Large repos may truncate; we still process what we get

    tree = data.get("tree", [])
    files = []
    for item in tree:
        if item["type"] != "blob":
            continue
        path = item["path"]
        if _should_skip_path(path):
            continue
        size = item.get("size", 0)
        if size > MAX_FILE_SIZE_BYTES:
            continue
        files.append(
            {
                "path": path,
                "size": size,
                "sha": item["sha"],
                "url": item.get("url", ""),
            }
        )
        if len(files) >= MAX_FILES:
            break

    return files


def fetch_file_content(
    owner: str, repo: str, path: str, token: Optional[str] = None
) -> Optional[str]:
    """Fetch raw content of a single file from GitHub."""
    headers = _get_headers(token)
    headers["Accept"] = "application/vnd.github.v3.raw"
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        _handle_rate_limit(response)
        if response.status_code == 200:
            return response.text
        return None
    except Exception:
        return None


def fetch_repository(
    url: str, token: Optional[str] = None, progress_callback=None
) -> dict:
    """
    Main entry point: fetch full repository data.
    Returns dict with owner, repo, branch, and file entries with content.
    """
    owner, repo = parse_github_url(url)
    branch = get_default_branch(owner, repo, token)
    file_entries = fetch_repo_tree(owner, repo, branch, token)

    total = len(file_entries)
    for i, entry in enumerate(file_entries):
        if progress_callback:
            progress_callback(i + 1, total, entry["path"])

        # Only fetch content for text-parseable files
        ext = entry["path"].rsplit(".", 1)[-1].lower() if "." in entry["path"] else ""
        text_extensions = {
            "py", "js", "ts", "tsx", "jsx", "java", "cpp", "go", "cs", "php",
            "json", "txt", "md", "rst", "yml", "yaml", "toml", "cfg", "ini",
            "xml", "html", "css", "scss", "less", "sh", "bash", "bat",
            "dockerfile", "env", "gitignore", "editorconfig",
        }
        filename = entry["path"].rsplit("/", 1)[-1].lower()
        is_text = ext in text_extensions or filename in {
            "dockerfile", "makefile", "procfile", "gemfile",
            "requirements.txt", "docker-compose.yml", "docker-compose.yaml",
            ".env", ".gitignore", ".editorconfig",
        }

        if is_text:
            content = fetch_file_content(owner, repo, entry["path"], token)
            entry["content"] = content
        else:
            entry["content"] = None

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "files": file_entries,
    }
