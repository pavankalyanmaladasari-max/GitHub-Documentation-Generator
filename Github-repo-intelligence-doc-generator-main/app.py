"""
Repo Intelligence Engine — Streamlit Application
Advanced repository intelligence analysis and AI architectural review.
"""

import json
import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests
import streamlit as st

from github_fetcher import fetch_repository, parse_github_url
from file_classifier import (
    classify_all_files,
    detect_primary_language,
    detect_project_type,
)
from static_parser import analyze_all_sources
from config_parser import parse_all_configs
from graph_builder import build_all_graphs
from ai_interpreter import get_ai_review, get_ai_repo_analysis
from semantic_inference import generate_description, enhance_function_descriptions
from pdf_generator import generate_comprehensive_pdf_report

try:
    from local_inference import generate_repo_summary, get_model_status
except ImportError:
    # Backward compatibility for deployments with older local_inference.py
    def generate_repo_summary(repo_info: dict) -> str:
        total_files = repo_info.get("total_source_files", 0)
        total_functions = repo_info.get("total_functions", 0)
        top_files = repo_info.get("top_function_files", [])

        if total_files <= 10 and total_functions <= 40:
            recommendation = "Read the full repository; it is compact and manageable."
        elif total_functions <= 120:
            recommendation = "Start with a targeted read first, then expand to full review if needed."
        else:
            recommendation = "Use targeted reading first; full sequential reading will be time-intensive."

        if top_files:
            return f"{recommendation} Begin with: {', '.join(top_files[:3])}."
        return recommendation

    def get_model_status() -> dict:
        return {
            "model": None,
            "hf_disabled": True,
            "reason": "Local inference module is running in compatibility mode",
        }

GITHUB_API_BASE = "https://api.github.com"
OAUTH_STATE_TTL_MINUTES = 15
_OAUTH_STATE_CACHE: dict[str, datetime] = {}


class GitHubSignInRequired(RuntimeError):
    """Raised when private repository access needs GitHub OAuth sign-in."""

    def __init__(self, message: str, authorize_url: str):
        super().__init__(message)
        self.authorize_url = authorize_url

# ──────────────────────────────────────────────
# Page Configuration
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="Repo Intelligence Engine",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# Custom Styling
# ──────────────────────────────────────────────

st.markdown("""
<style>
    .stApp {
        background:
            radial-gradient(circle at top right, rgba(97, 218, 251, 0.12), transparent 28%),
            radial-gradient(circle at top left, rgba(78, 140, 255, 0.14), transparent 22%),
            linear-gradient(180deg, #06101d 0%, #07131f 55%, #081018 100%);
    }
    .main-header {
        font-size: 2.9rem;
        font-weight: 800;
        background: linear-gradient(90deg, #8be8ff, #67b2ff 55%, #d8fcff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
        letter-spacing: -0.04em;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #96a8be;
        margin-top: 0;
        margin-bottom: 2rem;
    }
    .hero-shell {
        position: relative;
        overflow: hidden;
        padding: 1.4rem 1.4rem 1.2rem 1.4rem;
        margin: 0 0 1rem 0;
        border: 1px solid rgba(124, 184, 255, 0.24);
        border-radius: 22px;
        background: linear-gradient(145deg, rgba(12, 26, 43, 0.92), rgba(8, 18, 31, 0.94));
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.32);
    }
    .hero-shell::after {
        content: "";
        position: absolute;
        inset: auto -80px -120px auto;
        width: 240px;
        height: 240px;
        border-radius: 999px;
        background: radial-gradient(circle, rgba(97, 218, 251, 0.22), transparent 70%);
        pointer-events: none;
    }
    .hero-grid {
        display: grid;
        grid-template-columns: 1.6fr 1fr;
        gap: 1rem;
        align-items: stretch;
    }
    .hero-panel {
        position: relative;
        z-index: 1;
    }
    .signal-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
        margin-top: 0.9rem;
    }
    .signal-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.42rem 0.8rem;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.01em;
        color: #dff7ff;
        border: 1px solid rgba(130, 194, 255, 0.18);
        background: rgba(255, 255, 255, 0.04);
    }
    .hero-kpi-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.8rem;
    }
    .hero-kpi {
        padding: 0.9rem 1rem;
        border-radius: 18px;
        border: 1px solid rgba(135, 205, 255, 0.18);
        background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
    }
    .hero-kpi-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #8fa9c3;
        margin-bottom: 0.35rem;
    }
    .hero-kpi-value {
        font-size: 1.25rem;
        font-weight: 800;
        color: #f3fbff;
    }
    .dashboard-card {
        min-height: 100%;
        padding: 1rem 1rem 0.9rem 1rem;
        border-radius: 18px;
        border: 1px solid rgba(128, 191, 255, 0.18);
        background: linear-gradient(180deg, rgba(18, 31, 51, 0.85), rgba(9, 17, 28, 0.92));
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
    }
    .dashboard-card h4 {
        margin: 0 0 0.45rem 0;
        color: #f3fbff;
        font-size: 1rem;
    }
    .dashboard-card p,
    .dashboard-card li {
        color: #a5b7cb;
        font-size: 0.94rem;
    }
    .dashboard-card ul {
        margin: 0.4rem 0 0 1rem;
        padding: 0;
    }
    .mini-kpi-row {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.8rem;
        margin: 1rem 0 1.1rem 0;
    }
    .mini-kpi {
        padding: 0.95rem 1rem;
        border-radius: 18px;
        border: 1px solid rgba(110, 175, 255, 0.18);
        background: linear-gradient(180deg, rgba(13, 28, 47, 0.9), rgba(9, 18, 29, 0.94));
    }
    .mini-kpi span {
        display: block;
        color: #8ba6c0;
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.3rem;
    }
    .mini-kpi strong {
        color: #f7fcff;
        font-size: 1.15rem;
        font-weight: 800;
    }
    .section-note {
        margin: 0.25rem 0 1rem 0;
        padding: 0.85rem 0.95rem;
        border-left: 3px solid #61dafb;
        border-radius: 12px;
        background: rgba(97, 218, 251, 0.08);
        color: #d4ebf8;
    }
    .metric-card {
        background: #262730;
        border-radius: 10px;
        padding: 1.2rem;
        border-left: 4px solid #4e8cff;
    }
    .stExpander {
        border: 1px solid #333;
        border-radius: 8px;
    }
    .developer-card {
        border-radius: 12px;
        padding: 0.55rem;
        margin-top: 0.6rem;
        animation: developerEnter 0.5s ease-out;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .developer-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
    }
    .developer-image-shell {
        border-radius: 14px;
        overflow: hidden;
        padding: 3px;
        background: linear-gradient(135deg, rgba(139, 232, 255, 0.35), rgba(103, 178, 255, 0.18));
        animation: imagePop 0.55s ease-out;
    }
    .developer-image-shell img {
        border-radius: 11px;
        animation: imageReveal 0.7s ease-out;
    }
    .developer-name {
        font-weight: 700;
        color: #cfe3ff;
        margin: 0.45rem 0 0.35rem 0;
        text-align: center;
        letter-spacing: 0.01em;
    }
    @keyframes developerEnter {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    @keyframes imagePop {
        from {
            opacity: 0;
            transform: scale(0.92);
        }
        to {
            opacity: 1;
            transform: scale(1);
        }
    }
    @keyframes imageReveal {
        from {
            opacity: 0;
            filter: blur(6px);
        }
        to {
            opacity: 1;
            filter: blur(0);
        }
    }
    .feedback-panel {
        margin-top: 1.25rem;
        padding: 1rem;
        border-radius: 14px;
        border: 1px solid rgba(132, 198, 255, 0.28);
        background: linear-gradient(180deg, rgba(13, 28, 47, 0.85), rgba(9, 17, 29, 0.92));
    }
    .feedback-title {
        font-size: 1rem;
        font-weight: 700;
        color: #eaf7ff;
        margin: 0 0 0.25rem 0;
    }
    .feedback-subtitle {
        color: #9eb5cb;
        font-size: 0.92rem;
        margin: 0;
    }
    @media (max-width: 900px) {
        .hero-grid,
        .mini-kpi-row,
        .hero-kpi-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Secrets / Environment
# ──────────────────────────────────────────────

def _get_secret(key: str) -> Optional[str]:
    """Get secret from Streamlit secrets or environment."""
    try:
        value = st.secrets.get(key)
        if value:
            return str(value).strip()
    except Exception:
        pass
    env_value = os.environ.get(key)
    return env_value.strip() if isinstance(env_value, str) else env_value


def _is_placeholder_oauth_value(value: Optional[str]) -> bool:
    """Detect template placeholder values in OAuth configuration."""
    if not value:
        return True

    normalized = value.strip().lower()
    placeholder_markers = (
        "your_",
        "replace_",
        "changeme",
        "example",
        "placeholder",
    )
    return any(marker in normalized for marker in placeholder_markers)


def _get_github_token() -> Optional[str]:
    return _get_secret("GITHUB_TOKEN")


def _get_openai_token() -> Optional[str]:
    return _get_secret("OPENAI_API_KEY")


def _get_github_oauth_client_id() -> Optional[str]:
    return _get_secret("GITHUB_OAUTH_CLIENT_ID")


def _get_github_oauth_client_secret() -> Optional[str]:
    return _get_secret("GITHUB_OAUTH_CLIENT_SECRET")


def _get_github_oauth_redirect_uri() -> Optional[str]:
    return _get_secret("GITHUB_OAUTH_REDIRECT_URI")


def _get_github_oauth_scope() -> str:
    return _get_secret("GITHUB_OAUTH_SCOPE") or "public_repo"


def _feedback_file_path() -> Path:
    """Return path for storing user feedback entries."""
    return Path(__file__).resolve().parent / "user_feedback.json"


def _load_feedback_entries() -> list[dict]:
    """Load existing feedback entries from disk."""
    file_path = _feedback_file_path()
    if not file_path.exists():
        return []

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, ValueError):
        return []

    return []


def _append_feedback_entry(entry: dict) -> bool:
    """Append a feedback entry to local storage."""
    file_path = _feedback_file_path()
    entries = _load_feedback_entries()
    entries.append(entry)

    try:
        file_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def _save_feedback_entries(entries: list[dict]) -> bool:
    """Persist feedback entries to local storage."""
    file_path = _feedback_file_path()
    try:
        file_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def _update_feedback_entry(index: int, updated_entry: dict) -> bool:
    """Update one feedback entry by index."""
    entries = _load_feedback_entries()
    if index < 0 or index >= len(entries):
        return False

    entries[index] = updated_entry
    return _save_feedback_entries(entries)


def _delete_feedback_entry(index: int) -> bool:
    """Delete one feedback entry by index."""
    entries = _load_feedback_entries()
    if index < 0 or index >= len(entries):
        return False

    entries.pop(index)
    return _save_feedback_entries(entries)


def _get_user_github_token() -> Optional[str]:
    """Get end-user GitHub token from OAuth or manual session input."""
    oauth_token = st.session_state.get("github_oauth_token", "").strip()
    if oauth_token:
        return oauth_token

    runtime_token = st.session_state.get("github_token_input", "").strip()
    if runtime_token:
        return runtime_token

    session_token = st.session_state.get("github_token_override", "").strip()
    if session_token:
        return session_token

    return None


def _get_runtime_github_token() -> Optional[str]:
    """Get effective token for generic checks: user token first, then app token."""
    user_token = _get_user_github_token()
    if user_token:
        return user_token

    env_token = _get_github_token()
    return env_token.strip() if env_token else None


def _sync_github_token_from_input() -> None:
    """Sync token input value to session override for immediate use."""
    token = st.session_state.get("github_token_input", "").strip()
    if token:
        st.session_state["github_token_override"] = token
    else:
        st.session_state.pop("github_token_override", None)


def _check_github_token(token: str) -> tuple[bool, str]:
    """Validate GitHub token and return quota info."""
    if not token:
        return False, "Token is empty."

    try:
        response = requests.get(
            "https://api.github.com/rate_limit",
            headers={
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {token}",
            },
            timeout=20,
        )
    except requests.exceptions.RequestException as e:
        return False, f"Unable to reach GitHub API: {e}"

    if response.status_code == 200:
        data = response.json()
        core = data.get("resources", {}).get("core", {})
        remaining = core.get("remaining", "?")
        limit = core.get("limit", "?")
        return True, f"Token valid. Core quota: {remaining}/{limit} remaining."

    if response.status_code in (401, 403):
        return False, "Token rejected by GitHub. Check token value, expiry, and scopes."

    return False, f"GitHub API returned status {response.status_code}."


def _fetch_repo_metadata(owner: str, repo: str, token: Optional[str]) -> tuple[int, Optional[dict]]:
    """Fetch repository metadata and return (status_code, json_or_none)."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = requests.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}",
            headers=headers,
            timeout=20,
        )
    except requests.exceptions.RequestException:
        return 0, None

    if response.status_code == 200:
        try:
            return 200, response.json()
        except ValueError:
            return 200, None

    return response.status_code, None


def _github_json_get(endpoint: str, token: Optional[str], params: Optional[dict] = None) -> tuple[int, Optional[dict | list], dict]:
    """GET a GitHub API endpoint and parse JSON safely."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = requests.get(
            f"{GITHUB_API_BASE}{endpoint}",
            headers=headers,
            params=params,
            timeout=20,
        )
    except requests.exceptions.RequestException:
        return 0, None, {}

    if response.status_code == 200:
        try:
            return 200, response.json(), response.headers
        except ValueError:
            return 200, None, response.headers

    return response.status_code, None, response.headers


def _fetch_owner_repositories(owner: str, token: Optional[str]) -> list[dict]:
    """Fetch owner repositories for portfolio-level insights."""
    status, data, _ = _github_json_get(
        f"/users/{owner}/repos",
        token,
        params={"type": "owner", "per_page": 100, "sort": "updated"},
    )
    if status == 200 and isinstance(data, list):
        return data

    status, data, _ = _github_json_get(
        f"/orgs/{owner}/repos",
        token,
        params={"type": "public", "per_page": 100},
    )
    if status == 200 and isinstance(data, list):
        return data

    return []


def _fetch_repository_insights(owner: str, repo: str, token: Optional[str]) -> dict:
    """Collect repository metrics and activity for dashboard insights."""
    insights: dict = {
        "stars": 0,
        "forks": 0,
        "open_issues": 0,
        "open_pull_requests": 0,
        "commit_count_30d": 0,
        "commit_frequency_weekly": 0.0,
        "top_languages": [],
        "recent_commits": [],
        "most_starred_repo": None,
        "most_active_repo": None,
        # viz extras
        "weekly_commit_activity": [],   # [{week_ts, total, days:[7]}, …] – 52 entries
        "owner_repos_chart": [],        # [{name, stars, forks}, …] for stars-vs-forks chart
        "error": None,
    }

    status, repo_meta, _ = _github_json_get(f"/repos/{owner}/{repo}", token)
    if status != 200 or not isinstance(repo_meta, dict):
        insights["error"] = "Unable to fetch repository insights from GitHub."
        return insights

    insights["stars"] = int(repo_meta.get("stargazers_count", 0) or 0)
    insights["forks"] = int(repo_meta.get("forks_count", 0) or 0)
    insights["open_issues"] = int(repo_meta.get("open_issues_count", 0) or 0)

    q = f"repo:{owner}/{repo} type:pr state:open"
    pr_status, pr_data, _ = _github_json_get("/search/issues", token, params={"q": q, "per_page": 1})
    if pr_status == 200 and isinstance(pr_data, dict):
        insights["open_pull_requests"] = int(pr_data.get("total_count", 0) or 0)

    status, lang_data, _ = _github_json_get(f"/repos/{owner}/{repo}/languages", token)
    if status == 200 and isinstance(lang_data, dict) and lang_data:
        total = sum(lang_data.values())
        lang_rows = []
        for lang, size in sorted(lang_data.items(), key=lambda item: item[1], reverse=True)[:8]:
            pct = round((size / total) * 100, 2) if total else 0.0
            lang_rows.append({"language": lang, "bytes": size, "share_pct": pct})
        insights["top_languages"] = lang_rows

    since_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    status, commits_data, _ = _github_json_get(
        f"/repos/{owner}/{repo}/commits",
        token,
        params={"per_page": 100, "since": since_30d},
    )
    if status == 200 and isinstance(commits_data, list):
        insights["commit_count_30d"] = len(commits_data)
        insights["commit_frequency_weekly"] = round(len(commits_data) / 4.285, 2)

    status, recent_commits, _ = _github_json_get(
        f"/repos/{owner}/{repo}/commits",
        token,
        params={"per_page": 5},
    )
    if status == 200 and isinstance(recent_commits, list):
        simplified = []
        for c in recent_commits:
            commit = c.get("commit", {}) if isinstance(c, dict) else {}
            author = commit.get("author", {}) if isinstance(commit, dict) else {}
            msg = (commit.get("message") or "").split("\n")[0]
            simplified.append(
                {
                    "sha": (c.get("sha") or "")[:7] if isinstance(c, dict) else "",
                    "message": msg,
                    "author": author.get("name") or "Unknown",
                    "date": author.get("date") or "",
                }
            )
        insights["recent_commits"] = simplified

    owner_repos = _fetch_owner_repositories(owner, token)
    if owner_repos:
        most_starred = max(owner_repos, key=lambda r: r.get("stargazers_count", 0) or 0)
        most_active = max(owner_repos, key=lambda r: r.get("pushed_at") or "")
        insights["most_starred_repo"] = {
            "name": most_starred.get("name"),
            "stars": most_starred.get("stargazers_count", 0),
        }
        insights["most_active_repo"] = {
            "name": most_active.get("name"),
            "pushed_at": most_active.get("pushed_at"),
        }
        # Build stars-vs-forks chart data from top repos
        top_repos = sorted(owner_repos, key=lambda r: r.get("stargazers_count", 0) or 0, reverse=True)[:10]
        insights["owner_repos_chart"] = [
            {
                "name": r.get("name", ""),
                "stars": int(r.get("stargazers_count", 0) or 0),
                "forks": int(r.get("forks_count", 0) or 0),
            }
            for r in top_repos
        ]

    # 52-week commit activity (for commits-over-time + activity heatmap)
    # GitHub may return 202 Accepted on first call (computing stats); we try once.
    stat_status, weekly_data, _ = _github_json_get(
        f"/repos/{owner}/{repo}/stats/commit_activity", token
    )
    if stat_status == 200 and isinstance(weekly_data, list):
        insights["weekly_commit_activity"] = [
            {
                "week_ts": int(w.get("week", 0) or 0),
                "total": int(w.get("total", 0) or 0),
                "days": list(w.get("days", [0] * 7)),
            }
            for w in weekly_data
        ]

    return insights


def _select_github_token_for_repo(repo_url: str) -> tuple[Optional[str], str]:
    """
    Select GitHub token based on repository visibility policy.

    Policy:
    - Private repositories: require end-user token (OAuth/manual session token)
    - Public repositories: prefer app credential token (GITHUB_TOKEN), fallback to user token
    """
    owner, repo = parse_github_url(repo_url)
    user_token = _get_user_github_token()
    app_token = _get_github_token()

    public_status, public_meta = _fetch_repo_metadata(owner, repo, token=None)

    # GitHub returns 404 for private repositories when unauthenticated.
    # If OAuth is available and there is no user token yet, prompt sign-in first.
    if public_status == 404 and not user_token:
        authorize_url = _build_github_oauth_authorize_url()
        if authorize_url:
            raise GitHubSignInRequired(
                "Repository is not publicly accessible. If it is private, continue with GitHub sign in.",
                authorize_url,
            )
    if public_status == 200 and public_meta:
        if public_meta.get("private"):
            if user_token:
                return user_token, "user-token-private"
            authorize_url = _build_github_oauth_authorize_url()
            if authorize_url:
                raise GitHubSignInRequired(
                    "Private repository detected. Redirecting to GitHub sign in.",
                    authorize_url,
                )
            raise RuntimeError(
                "Private repository detected. Sign in with GitHub or provide a personal token in this session."
            )

        if app_token:
            return app_token, "app-token-public"
        if user_token:
            return user_token, "user-token-public"
        return None, "unauthenticated-public"

    if user_token:
        user_status, user_meta = _fetch_repo_metadata(owner, repo, token=user_token)
        if user_status == 200 and user_meta:
            if user_meta.get("private"):
                return user_token, "user-token-private"
            return user_token, "user-token-public"

    if app_token:
        app_status, app_meta = _fetch_repo_metadata(owner, repo, token=app_token)
        if app_status == 200 and app_meta:
            if app_meta.get("private"):
                authorize_url = _build_github_oauth_authorize_url()
                if authorize_url:
                    raise GitHubSignInRequired(
                        "Private repository requires end-user access. Redirecting to GitHub sign in.",
                        authorize_url,
                    )
                raise RuntimeError(
                    "Private repository requires the end-user token. Use GitHub Sign In or provide a personal token."
                )
            return app_token, "app-token-public"

    raise ValueError(
        "Repository not found or access denied. For private repositories, sign in with GitHub or provide a personal token."
    )


def _get_query_param_value(name: str) -> Optional[str]:
    """Read a query param value in a Streamlit-version-safe way."""
    try:
        value = st.query_params.get(name)
        if isinstance(value, list):
            return value[0] if value else None
        return value
    except Exception:
        try:
            value = st.experimental_get_query_params().get(name)
            if isinstance(value, list):
                return value[0] if value else None
            return value
        except Exception:
            return None


def _clear_query_params() -> None:
    """Clear URL query params after OAuth callback handling."""
    try:
        st.query_params.clear()
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            pass


def _build_github_oauth_authorize_url() -> Optional[str]:
    """Build GitHub OAuth authorize URL for Sign in button."""
    client_id = _get_github_oauth_client_id()
    redirect_uri = _get_github_oauth_redirect_uri()
    client_secret = _get_github_oauth_client_secret()
    if not client_id or not redirect_uri:
        return None

    state = st.session_state.get("github_oauth_state")
    if not state:
        state = _generate_oauth_state(client_secret)
        st.session_state["github_oauth_state"] = state

    # Cache state server-side for callback validation in case Streamlit session is recreated.
    _OAUTH_STATE_CACHE[state] = datetime.now(timezone.utc) + timedelta(minutes=OAUTH_STATE_TTL_MINUTES)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": _get_github_oauth_scope(),
        "state": state,
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


def _fetch_github_user(access_token: str) -> Optional[dict]:
    """Fetch current user from GitHub API using access token."""
    try:
        response = requests.get(
            "https://api.github.com/user",
            headers={
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {access_token}",
            },
            timeout=20,
        )
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        return None
    return None


def _generate_oauth_state(client_secret: Optional[str]) -> str:
    """Generate CSRF state with signed fallback format for callback validation."""
    nonce = secrets.token_urlsafe(24)
    issued_at = int(datetime.now(timezone.utc).timestamp())

    # When client secret exists, include HMAC signature so state can be validated
    # even if Streamlit session state is reset after OAuth redirect.
    if client_secret:
        payload = f"{nonce}.{issued_at}"
        signature = hmac.new(
            client_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{payload}.{signature}"

    return nonce


def _validate_oauth_state(received_state: str, expected_state: Optional[str], client_secret: Optional[str]) -> bool:
    """Validate OAuth state against session value or signed fallback token."""
    if not received_state:
        return False

    # Primary check: exact match with session state if available.
    if expected_state and hmac.compare_digest(received_state, expected_state):
        return True

    # Fallback check for cases where Streamlit session is recreated after redirect.
    # Accept only signed states generated by this app and not older than 15 minutes.
    if not client_secret:
        return False

    parts = received_state.split(".")
    if len(parts) != 3:
        return False

    nonce, issued_at_raw, signature = parts
    if not nonce or not issued_at_raw or not signature:
        return False

    try:
        issued_at = int(issued_at_raw)
    except ValueError:
        return False

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if now_ts - issued_at > 900 or issued_at > now_ts + 60:
        return False

    payload = f"{nonce}.{issued_at_raw}"
    expected_signature = hmac.new(
        client_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)


def _exchange_github_oauth_code_for_token(code: str, state: str) -> tuple[bool, str]:
    """Exchange OAuth callback code for access token and save session state."""
    client_id = _get_github_oauth_client_id()
    client_secret = _get_github_oauth_client_secret()
    redirect_uri = _get_github_oauth_redirect_uri()

    if not client_id or not client_secret or not redirect_uri:
        return False, "GitHub OAuth is not configured. Set client id, secret, and redirect URI."

    if _is_placeholder_oauth_value(client_id) or _is_placeholder_oauth_value(client_secret):
        return (
            False,
            "GitHub OAuth is not configured correctly. Replace placeholder values for GITHUB_OAUTH_CLIENT_ID and GITHUB_OAUTH_CLIENT_SECRET in .streamlit/secrets.toml.",
        )

    expected_state = st.session_state.get("github_oauth_state")
    now = datetime.now(timezone.utc)

    # Remove expired entries from cache.
    for cached_state, expiry in list(_OAUTH_STATE_CACHE.items()):
        if expiry <= now:
            _OAUTH_STATE_CACHE.pop(cached_state, None)

    state_valid_in_cache = bool(state) and state in _OAUTH_STATE_CACHE and _OAUTH_STATE_CACHE[state] > now
    state_valid_in_session = bool(expected_state) and state == expected_state
    state_valid_signed_fallback = _validate_oauth_state(state, expected_state, client_secret)

    if not (state_valid_in_session or state_valid_in_cache or state_valid_signed_fallback):
        return False, "GitHub OAuth state validation failed. Please try signing in again."

    # Consume one-time state after successful validation.
    if state:
        _OAUTH_STATE_CACHE.pop(state, None)

    try:
        response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "state": state,
            },
            timeout=30,
        )
    except requests.exceptions.RequestException as e:
        return False, f"OAuth token exchange failed: {e}"

    if response.status_code != 200:
        return False, f"OAuth token exchange failed with status {response.status_code}."

    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        error_msg = data.get("error_description") or data.get("error") or "No access token returned."
        return False, f"GitHub OAuth error: {error_msg}"

    st.session_state["github_oauth_token"] = access_token
    st.session_state["github_oauth_user"] = _fetch_github_user(access_token)
    st.session_state["github_oauth_last_code"] = code
    return True, "Signed in with GitHub successfully."


def _revoke_github_oauth_token(token: str) -> tuple[bool, str]:
    """Best-effort token revocation for GitHub OAuth token."""
    client_id = _get_github_oauth_client_id()
    client_secret = _get_github_oauth_client_secret()
    if not client_id or not client_secret:
        return False, "Client credentials missing; cleared local session token only."

    try:
        response = requests.delete(
            f"https://api.github.com/applications/{client_id}/grant",
            auth=(client_id, client_secret),
            headers={"Accept": "application/vnd.github+json"},
            json={"access_token": token},
            timeout=20,
        )
    except requests.exceptions.RequestException as e:
        return False, f"Token revoke request failed: {e}"

    if response.status_code in (204, 404):
        return True, "GitHub token revoked."

    return False, f"Token revoke returned status {response.status_code}."


def _handle_github_oauth_callback() -> Optional[tuple[str, str]]:
    """Handle OAuth callback if present. Returns optional (level, message)."""
    code = _get_query_param_value("code")
    state = _get_query_param_value("state")
    error = _get_query_param_value("error")

    if error:
        _clear_query_params()
        return ("error", f"GitHub OAuth canceled or failed: {error}")

    if not code:
        return None

    if code == st.session_state.get("github_oauth_last_code"):
        _clear_query_params()
        return None

    ok, message = _exchange_github_oauth_code_for_token(code, state or "")
    _clear_query_params()
    return ("success", message) if ok else ("error", message)


def _attempt_browser_redirect(url: str) -> None:
    """Best-effort browser redirect for OAuth flows inside Streamlit."""
    try:
        import streamlit.components.v1 as components

        encoded_url = json.dumps(url)
        components.html(
            f"""
            <script>
                window.top.location.href = {encoded_url};
            </script>
            """,
            height=0,
        )
    except Exception:
        # Keep a visible link as fallback when script-based redirect is blocked.
        pass


def _render_private_repo_access_help(repo_url: str, authorize_url: Optional[str]) -> None:
    """Show clear guidance about private repository access requirements."""
    owner_text = ""
    try:
        owner, _ = parse_github_url(repo_url)
        owner_text = owner
    except Exception:
        owner_text = "this repository"

    st.info(
        "Private repositories can only be opened by GitHub users who already have permission."
    )
    st.markdown(
        "Access is allowed for users with explicit access such as the owner, collaborators, or approved organization/team members."
    )

    if authorize_url:
        st.link_button("Sign in with GitHub", authorize_url, width="stretch")
        st.caption(
            "If the signed-in account does not have access to this private repository, analysis will still be denied."
        )
    else:
        st.warning(
            "GitHub OAuth sign-in is not configured for this app. Configure OAuth secrets or provide a personal token with repository access."
        )
        if owner_text:
            st.caption(f"Required: a GitHub account that already has access to {owner_text} private repositories.")


# ──────────────────────────────────────────────
# Analysis Pipeline
# ──────────────────────────────────────────────

def run_analysis(repo_url: str) -> dict:
    """Execute the full analysis pipeline."""
    github_token, auth_mode = _select_github_token_for_repo(repo_url)
    results = {}

    # Step 1: Fetch repository
    status = st.status("Analyzing repository...", expanded=True)

    with status:
        st.write("📡 Fetching repository tree...")
        st.write(f"🔐 GitHub auth mode: {auth_mode}")
        progress_bar = st.progress(0, text="Connecting to GitHub...")

        def progress_callback(current, total, path):
            pct = current / total if total > 0 else 0
            progress_bar.progress(pct, text=f"Fetching {current}/{total}: {path}")

        repo_data = fetch_repository(repo_url, token=github_token, progress_callback=progress_callback)
        repo_data["auth_mode"] = auth_mode
        files = repo_data["files"]
        progress_bar.progress(1.0, text=f"Fetched {len(files)} files")

        # Step 1.5: GitHub insights
        st.write("📊 Gathering repository insights...")
        insights = _fetch_repository_insights(repo_data["owner"], repo_data["repo"], github_token)

        # Step 2: Classify files
        st.write("📂 Classifying files...")
        classification = classify_all_files(files)
        primary_lang = detect_primary_language(files)
        project_type = detect_project_type(files)

        # Step 3: Parse source files
        st.write("🔍 Parsing source code...")
        source_analysis = analyze_all_sources(files)
        
        # Step 3.5: Enhance with static semantic inference
        st.write("🧠 Generating semantic descriptions...")
        semantic_progress = st.progress(0, text="Preparing semantic analysis...")
        total_source = len(source_analysis)

        for idx, analysis in enumerate(source_analysis, 1):
            file_path = analysis.get("file_path", "unknown")
            semantic_progress.progress(
                idx / total_source if total_source else 1.0,
                text=f"Semantic {idx}/{total_source}: {file_path}",
            )

            try:
                # Generate file-level description
                description = generate_description(analysis)
                if description:
                    analysis["semantic_description"] = description

                # Enhance function descriptions (bounded AI calls + fallback)
                if analysis.get("functions"):
                    analysis["functions"] = enhance_function_descriptions(
                        analysis["functions"],
                        analysis["file_path"],
                        analysis.get("language", ""),
                        max_model_calls=3,
                    )
            except Exception as e:
                print(f"Semantic enhancement failed for {file_path}: {e}")

        semantic_progress.progress(1.0, text="Semantic descriptions completed")

        # Step 4: Parse config files
        st.write("⚙️ Analyzing configurations...")
        config_data = parse_all_configs(files)

        # Step 5: Build graphs
        st.write("📊 Building architecture diagrams...")
        graphs = build_all_graphs(source_analysis)

        status.update(label="Analysis complete!", state="complete")

    # Generate repo summary
    total_functions = sum(len(item.get("functions", [])) for item in source_analysis)
    total_classes = sum(
        len(item.get("classes", [])) + len(item.get("components", []))
        for item in source_analysis
    )
    files_by_function_count = sorted(
        source_analysis,
        key=lambda item: len(item.get("functions", [])),
        reverse=True
    )
    top_function_files = [
        item.get("file_path", "Unknown")
        for item in files_by_function_count
        if len(item.get("functions", [])) > 0
    ][:5]

    repo_info = {
        "total_source_files": len(source_analysis),
        "total_functions": total_functions,
        "total_classes": total_classes,
        "top_function_files": top_function_files,
    }
    repo_summary = generate_repo_summary(repo_info)

    # Build master JSON
    master_json = _build_master_json(
        repo_data, classification, primary_lang,
        project_type, source_analysis, config_data, graphs
    )

    return {
        "repo_data": repo_data,
        "classification": classification,
        "primary_lang": primary_lang,
        "project_type": project_type,
        "source_analysis": source_analysis,
        "config_data": config_data,
        "graphs": graphs,
        "insights": insights,
        "master_json": master_json,
        "repo_summary": repo_summary,
    }


def _build_master_json(
    repo_data: dict,
    classification: dict,
    primary_lang: str,
    project_type: dict,
    source_analysis: list,
    config_data: dict,
    graphs: dict,
) -> dict:
    """Build the structured master JSON output."""
    # Determine project type string
    type_str = "Software Project"
    if project_type["frontend_detected"] and project_type["backend_detected"]:
        type_str = "Full-Stack Application"
    elif project_type["is_nextjs"]:
        type_str = "Next.js Application"
    elif project_type["is_vite"]:
        type_str = "Vite Application"
    elif project_type["frontend_detected"]:
        type_str = "Frontend Application"
    elif project_type["backend_detected"]:
        if primary_lang == "Python":
            type_str = "Python Backend Application"
        elif primary_lang in ("JavaScript", "TypeScript"):
            type_str = "Node.js Backend Application"
        else:
            type_str = "Backend Application"
    
    # Calculate language breakdown
    from file_classifier import detect_language
    lang_breakdown = {}
    for file in repo_data["files"]:
        lang = detect_language(file["path"])
        if lang:
            base_lang = lang.split(" ")[0]  # Normalize "TypeScript (React)" -> "TypeScript"
            lang_breakdown[base_lang] = lang_breakdown.get(base_lang, 0) + 1
    
    return {
        "project_metadata": {
            "owner": repo_data["owner"],
            "repo": repo_data["repo"],
            "branch": repo_data["branch"],
            "primary_language": primary_lang,
            "project_type": type_str,
            "language_breakdown": lang_breakdown,
            "total_files": len(repo_data["files"]),
            "source_files": len(classification["source"]),
            "config_files": len(classification["config"]),
            "documentation_files": len(classification["documentation"]),
            "asset_files": len(classification["asset"]),
            "frontend_detected": project_type["frontend_detected"],
            "backend_detected": project_type["backend_detected"],
            "is_nextjs": project_type.get("is_nextjs", False),
            "is_vite": project_type.get("is_vite", False),
            "auth_mode": repo_data.get("auth_mode", "unknown"),
        },
        "source_analysis": source_analysis,
        "dependencies": {
            "frontend": config_data.get("frontend_dependencies", []),
            "backend": config_data.get("backend_dependencies", []),
        },
        "frameworks": {
            "frontend": config_data.get("frontend_frameworks", []),
            "backend": config_data.get("backend_frameworks", []),
        },
        "infrastructure": {
            "docker_used": config_data.get("docker_used", False),
            "ci_cd_detected": classification.get("ci_cd_detected", False),
            "dockerfile": config_data.get("dockerfile"),
            "docker_compose": config_data.get("docker_compose"),
        },
        "graph_adjacency": {
            "module_dependencies": graphs["module_dependency"]["adjacency"],
            "api_routes": graphs["api_routes"]["adjacency"],
            "component_graph": graphs["component_graph"]["adjacency"],
        },
    }


def render_repository_insights(results: dict):
    """Render repository metrics and activity insights dashboard with Plotly + Altair charts."""
    import plotly.graph_objects as go

    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:0.8rem;margin-bottom:1.4rem;">
            <span style="font-size:1.55rem;font-weight:800;
                background:linear-gradient(90deg,#34d399,#60a5fa);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                Repository Insights Dashboard
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    insights = results.get("insights", {})

    if not insights:
        st.info("Repository insights are not available for this analysis run.")
        return

    if insights.get("error"):
        st.warning(insights["error"])

    # ── KPI row ───────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("⭐ Stars", f"{insights.get('stars', 0):,}")
    c2.metric("🍴 Forks", f"{insights.get('forks', 0):,}")
    c3.metric("🐞 Open Issues", f"{insights.get('open_issues', 0):,}")
    c4.metric("🔀 Open PRs", f"{insights.get('open_pull_requests', 0):,}")
    c5.metric("🗓 Commits (30d)", f"{insights.get('commit_count_30d', 0):,}")
    c6.metric("📈 Avg / Week", f"{insights.get('commit_frequency_weekly', 0.0):.1f}")

    st.divider()

    # ── ROW 1 – Language Distribution + Stars vs Forks ────────────────────────
    col_lang, col_sf = st.columns(2)

    # ── Language Distribution (Plotly donut) ─────────────────────────────────
    with col_lang:
        st.subheader("🌐 Language Distribution")
        top_languages = insights.get("top_languages", [])
        if top_languages:
            langs = [r["language"] for r in top_languages]
            pcts  = [r["share_pct"] for r in top_languages]
            colors = [
                "#60a5fa", "#34d399", "#f472b6", "#fbbf24",
                "#a78bfa", "#f87171", "#38bdf8", "#4ade80",
            ]
            fig_lang = go.Figure(
                go.Pie(
                    labels=langs,
                    values=pcts,
                    hole=0.52,
                    marker=dict(colors=colors[: len(langs)], line=dict(color="#0d1b2a", width=2)),
                    textinfo="percent+label",
                    textfont=dict(size=13, color="#e2e8f0"),
                    insidetextorientation="radial",
                )
            )
            fig_lang.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(
                    font=dict(color="#94a3b8", size=12),
                    bgcolor="rgba(0,0,0,0)",
                ),
                height=320,
            )
            st.plotly_chart(fig_lang, width="stretch")
        else:
            # Fallback: use master_json language data
            lang_breakdown = results.get("master_json", {}).get("project_metadata", {}).get("language_breakdown", {})
            if lang_breakdown:
                langs = list(lang_breakdown.keys())
                counts = list(lang_breakdown.values())
                fig_lang = go.Figure(
                    go.Pie(
                        labels=langs,
                        values=counts,
                        hole=0.52,
                        marker=dict(colors=["#60a5fa","#34d399","#f472b6","#fbbf24","#a78bfa","#f87171"][:len(langs)],
                                    line=dict(color="#0d1b2a", width=2)),
                        textinfo="percent+label",
                        textfont=dict(size=13, color="#e2e8f0"),
                    )
                )
                fig_lang.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(font=dict(color="#94a3b8", size=12), bgcolor="rgba(0,0,0,0)"),
                    height=320,
                )
                st.plotly_chart(fig_lang, width="stretch")
            else:
                st.info("No language breakdown available.")

    # ── Stars vs Forks (Plotly grouped bar) ──────────────────────────────────
    with col_sf:
        st.subheader("⭐ Stars vs 🍴 Forks (Top Owner Repos)")
        repo_chart_data = insights.get("owner_repos_chart", [])
        if repo_chart_data:
            names  = [r["name"] for r in repo_chart_data]
            stars  = [r["stars"] for r in repo_chart_data]
            forks  = [r["forks"] for r in repo_chart_data]
            fig_sf = go.Figure()
            fig_sf.add_trace(go.Bar(
                name="Stars", x=names, y=stars,
                marker_color="#fbbf24",
                hovertemplate="%{x}<br>Stars: %{y:,}<extra></extra>",
            ))
            fig_sf.add_trace(go.Bar(
                name="Forks", x=names, y=forks,
                marker_color="#60a5fa",
                hovertemplate="%{x}<br>Forks: %{y:,}<extra></extra>",
            ))
            fig_sf.update_layout(
                barmode="group",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(13,27,42,0.6)",
                margin=dict(l=10, r=10, t=10, b=80),
                xaxis=dict(tickfont=dict(color="#94a3b8", size=11), tickangle=-35,
                           gridcolor="rgba(255,255,255,0.04)"),
                yaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="rgba(255,255,255,0.08)"),
                legend=dict(font=dict(color="#94a3b8"), bgcolor="rgba(0,0,0,0)"),
                height=320,
            )
            st.plotly_chart(fig_sf, width="stretch")
        else:
            # Fallback – just this repo
            repo_name = results.get("repo_data", {}).get("repo", "This Repo")
            fig_sf = go.Figure()
            fig_sf.add_trace(go.Bar(name="Stars", x=[repo_name], y=[insights.get("stars", 0)], marker_color="#fbbf24"))
            fig_sf.add_trace(go.Bar(name="Forks", x=[repo_name], y=[insights.get("forks", 0)], marker_color="#60a5fa"))
            fig_sf.update_layout(
                barmode="group",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(13,27,42,0.6)",
                margin=dict(l=10, r=10, t=10, b=30),
                legend=dict(font=dict(color="#94a3b8"), bgcolor="rgba(0,0,0,0)"),
                height=320,
            )
            st.plotly_chart(fig_sf, width="stretch")

    st.divider()

    # ── ROW 2 – Commits Over Time (full width Plotly) ─────────────────────────
    st.subheader("📅 Commits Over Time (Last 52 Weeks)")
    weekly_activity = insights.get("weekly_commit_activity", [])
    if weekly_activity:
        weeks = [
            datetime.fromtimestamp(w["week_ts"], tz=timezone.utc).strftime("%Y-%m-%d")
            for w in weekly_activity
        ]
        totals = [w["total"] for w in weekly_activity]

        fig_commits = go.Figure()
        fig_commits.add_trace(go.Bar(
            x=weeks, y=totals,
            name="Commits",
            marker=dict(
                color=totals,
                colorscale=[[0, "#1e3a5f"], [0.4, "#3b82f6"], [1.0, "#34d399"]],
                showscale=False,
            ),
            hovertemplate="Week: %{x}<br>Commits: %{y}<extra></extra>",
        ))
        fig_commits.add_trace(go.Scatter(
            x=weeks, y=totals,
            mode="lines",
            line=dict(color="rgba(96,165,250,0.55)", width=2, shape="spline"),
            fill="tozeroy",
            fillcolor="rgba(96,165,250,0.07)",
            showlegend=False,
            hoverinfo="skip",
        ))
        fig_commits.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(13,27,42,0.6)",
            margin=dict(l=10, r=10, t=10, b=40),
            xaxis=dict(
                tickfont=dict(color="#94a3b8", size=11),
                gridcolor="rgba(255,255,255,0.04)",
                nticks=13,
            ),
            yaxis=dict(
                tickfont=dict(color="#94a3b8"),
                gridcolor="rgba(255,255,255,0.08)",
                title=dict(text="Commits", font=dict(color="#64748b")),
            ),
            height=300,
        )
        st.plotly_chart(fig_commits, width="stretch")
    else:
        # Build a synthetic chart from the 30-day commits we already have
        st.caption("52-week stats not yet available from GitHub (may take a moment on first load). Showing 30-day estimate.")
        commits_30d = insights.get("commit_count_30d", 0)
        if commits_30d:
            # Synthetic weekly buckets
            weeks_approx = [f"Week {i}" for i in range(1, 5)]
            vals_approx = [round(commits_30d / 4)] * 4
            fig_est = go.Figure(go.Bar(x=weeks_approx, y=vals_approx, marker_color="#3b82f6"))
            fig_est.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(13,27,42,0.6)",
                margin=dict(l=10, r=10, t=10, b=30),
                xaxis=dict(tickfont=dict(color="#94a3b8")),
                yaxis=dict(tickfont=dict(color="#94a3b8")),
                height=220,
            )
            st.plotly_chart(fig_est, width="stretch")
        else:
            st.info("No commit activity data available.")

    st.divider()

    # ── ROW 3 – Activity Heatmap (Plotly) ─────────────────────────────────────
    st.subheader("🗓 Weekly Activity Heatmap (Last 26 Weeks)")
    DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    if weekly_activity:
        recent_26 = weekly_activity[-26:]
        weeks = [
            datetime.fromtimestamp(entry["week_ts"], tz=timezone.utc).strftime("%b %d")
            for entry in recent_26
        ]
        z_values = [entry["days"] for entry in recent_26]

        fig_heatmap = go.Figure(
            data=go.Heatmap(
                x=DAYS,
                y=weeks,
                z=z_values,
                colorscale=[
                    [0.0, "#0b1b2b"],
                    [0.25, "#1d4ed8"],
                    [0.5, "#2563eb"],
                    [0.75, "#38bdf8"],
                    [1.0, "#34d399"],
                ],
                hovertemplate="Week %{y}<br>%{x}: %{z} commits<extra></extra>",
                colorbar=dict(
                    title=dict(text="Commits", font=dict(color="#64748b")),
                    tickfont=dict(color="#94a3b8"),
                ),
            )
        )
        fig_heatmap.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(13,27,42,0.6)",
            margin=dict(l=10, r=10, t=10, b=20),
            xaxis=dict(tickfont=dict(color="#94a3b8"), title=None, side="top"),
            yaxis=dict(tickfont=dict(color="#94a3b8"), title=None, autorange="reversed"),
            height=360,
        )
        st.plotly_chart(fig_heatmap, width="stretch")
    else:
        st.info("Activity heatmap will appear after GitHub stats are computed (may need ~30 seconds on first load for new repositories).")

    st.divider()

    # ── ROW 4 – Owner Signals + Recent Commits ───────────────────────────────
    col_a, col_b = st.columns(2)
    most_starred = insights.get("most_starred_repo")
    most_active = insights.get("most_active_repo")
    with col_a:
        st.subheader("Most Starred Repo (Owner)")
        if most_starred:
            st.info(f"**{most_starred.get('name')}** · ⭐ {most_starred.get('stars', 0):,}")
        else:
            st.caption("No owner-level starred data available.")

    with col_b:
        st.subheader("Most Active Repo (Owner)")
        if most_active:
            st.info(f"**{most_active.get('name')}** · Last push: {most_active.get('pushed_at', 'n/a')}")
        else:
            st.caption("No owner-level activity data available.")

    recent_commits = insights.get("recent_commits", [])
    if recent_commits:
        st.subheader("🔖 Recent Commits")
        for commit in recent_commits:
            st.markdown(
                f"- `{commit.get('sha', '')}` &nbsp; {commit.get('message', '')} "
                f"<span style='color:#64748b;font-size:0.82rem;'>"
                f"({commit.get('author', 'Unknown')}, {commit.get('date', '')})</span>",
                unsafe_allow_html=True,
            )


# ──────────────────────────────────────────────
# UI Rendering
# ──────────────────────────────────────────────

def render_header():
    """Render application header."""
    model_status = get_model_status()
    provider_name = (model_status.get("provider") or "heuristic").upper()
    github_ready = "READY" if (_get_github_token() or _get_user_github_token()) else "LIMITED"
    st.markdown(
        f"""
        <div class="hero-shell">
            <div class="hero-grid">
                <div class="hero-panel">
                    <p class="main-header">Repo Intelligence Engine</p>
                    <p class="sub-header">A guided repository dashboard that explains structure, architecture, dependencies, and risk signals in plain language.</p>
                    <div class="signal-row">
                        <span class="signal-pill">GitHub Access: {github_ready}</span>
                        <span class="signal-pill">AI Provider: {provider_name}</span>
                        <span class="signal-pill">Outputs: Graphs • Summaries • PDF</span>
                    </div>
                </div>
                <div class="hero-panel">
                    <div class="hero-kpi-grid">
                        <div class="hero-kpi">
                            <div class="hero-kpi-label">For Beginners</div>
                            <div class="hero-kpi-value">Guided</div>
                        </div>
                        <div class="hero-kpi">
                            <div class="hero-kpi-label">Repository Modes</div>
                            <div class="hero-kpi-value">Public + Private</div>
                        </div>
                        <div class="hero-kpi">
                            <div class="hero-kpi-label">Auth Routing</div>
                            <div class="hero-kpi-value">Auto</div>
                        </div>
                        <div class="hero-kpi">
                            <div class="hero-kpi-label">Review Style</div>
                            <div class="hero-kpi-value">Dashboard</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _humanize_auth_mode(auth_mode: str) -> str:
    mapping = {
        "user-token-private": "Private repo via user session",
        "user-token-public": "Public repo via user session",
        "app-token-public": "Public repo via app credential",
        "unauthenticated-public": "Public repo without auth",
        "unknown": "Not yet analyzed",
    }
    return mapping.get(auth_mode, auth_mode.replace("-", " ").title())


def render_first_run_dashboard():
    """Render onboarding cards for first-time users."""
    st.markdown('<div class="section-note">Paste a GitHub URL, click Analyze, and the app will turn a codebase into a readable dashboard. If the repository is private, the app will prompt for GitHub sign-in automatically.</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            '''<div class="dashboard-card"><h4>1. Connect A Repository</h4><p>Use any GitHub repository URL. Public repositories work immediately. Private repositories trigger GitHub sign-in so the owner’s access stays in their own session.</p></div>''',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            '''<div class="dashboard-card"><h4>2. Read The Dashboard</h4><p>The app summarizes what the project is, what technologies it uses, how files connect, and where the main logic lives. You do not need to inspect source files first.</p></div>''',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            '''<div class="dashboard-card"><h4>3. Export Or Share</h4><p>Once the analysis is complete, export the PDF or JSON report. That gives non-technical users a compact view without exposing credentials or code secrets.</p></div>''',
            unsafe_allow_html=True,
        )


def render_analysis_command_center(results: dict):
    """Render a high-level dashboard summary for analyzed repositories."""
    meta = results["master_json"]["project_metadata"]
    frameworks = results["master_json"].get("frameworks", {})
    source_analysis = results.get("source_analysis", [])
    routes = sum(len(item.get("routes", [])) for item in source_analysis)
    components = sum(len(item.get("components", [])) for item in source_analysis)
    auth_mode = _humanize_auth_mode(meta.get("auth_mode", "unknown"))
    detected_frameworks = frameworks.get("frontend", []) + frameworks.get("backend", [])
    framework_text = ", ".join(detected_frameworks[:4]) if detected_frameworks else "General codebase"

    st.markdown("### Mission Control")
    st.markdown(
        '<div class="section-note">This dashboard condenses the repository into operational signals: what it is, how access worked, where the important code lives, and what to inspect first.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="mini-kpi-row">
            <div class="mini-kpi"><span>Repository</span><strong>{meta['owner']}/{meta['repo']}</strong></div>
            <div class="mini-kpi"><span>Access Route</span><strong>{auth_mode}</strong></div>
            <div class="mini-kpi"><span>Project Type</span><strong>{meta['project_type']}</strong></div>
            <div class="mini-kpi"><span>Primary Stack</span><strong>{meta['primary_language']}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f'''<div class="dashboard-card"><h4>What You Are Looking At</h4><p>This repository is classified as <strong>{meta['project_type']}</strong> and the engine detected <strong>{framework_text}</strong>. Use the Overview tab for the big picture before diving into files.</p></div>''',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'''<div class="dashboard-card"><h4>Where To Start</h4><p>There are <strong>{meta['source_files']}</strong> source files, <strong>{routes}</strong> API routes, and <strong>{components}</strong> detected UI components. Start with the Guidance and Files tabs to locate key modules quickly.</p></div>''',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            '''<div class="dashboard-card"><h4>How To Read Results</h4><ul><li><strong>Overview</strong> explains the shape of the project.</li><li><strong>Files</strong> shows important classes, functions, and components.</li><li><strong>Architecture</strong> visualizes dependency flow.</li></ul></div>''',
            unsafe_allow_html=True,
        )


def render_project_overview(results: dict):
    """Render project overview section."""
    st.header("📋 Project Overview")
    meta = results["master_json"]["project_metadata"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Files", meta["total_files"])
    col2.metric("Primary Language", meta["primary_language"])
    col3.metric("Source Files", meta["source_files"])
    col4.metric("Config Files", meta["config_files"])

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Documentation", meta["documentation_files"])
    col6.metric("Assets", meta["asset_files"])
    col7.metric("Frontend", "✅" if meta["frontend_detected"] else "❌")
    col8.metric("Backend", "✅" if meta["backend_detected"] else "❌")

    # Project type badges
    badges = []
    if meta.get("is_nextjs"):
        badges.append("Next.js")
    if meta.get("is_vite"):
        badges.append("Vite")

    pt = results["project_type"]
    for fw in pt.get("frameworks", []):
        badges.append(fw)

    if badges:
        st.markdown("**Detected Frameworks:** " + " · ".join(f"`{b}`" for b in badges))


def render_repo_read_guidance(results: dict):
    """Render top-level AI guidance: full repository read vs targeted read."""
    st.header("🧠 AI Repository Read Guidance")

    source_analysis = results.get("source_analysis", [])
    total_source_files = len(source_analysis)
    total_functions = sum(len(item.get("functions", [])) for item in source_analysis)
    total_classes = sum(
        len(item.get("classes", [])) + len(item.get("components", []))
        for item in source_analysis
    )

    files_by_function_count = sorted(
        source_analysis,
        key=lambda item: len(item.get("functions", [])),
        reverse=True
    )
    top_function_files = [
        item.get("file_path", "Unknown")
        for item in files_by_function_count
        if len(item.get("functions", [])) > 0
    ][:5]

    repo_info = {
        "total_source_files": total_source_files,
        "total_functions": total_functions,
        "total_classes": total_classes,
        "top_function_files": top_function_files,
    }

    summary_text = generate_repo_summary(repo_info)

    st.info(summary_text)

    if top_function_files:
        st.markdown("**Suggested files to start with:**")
        for file_path in top_function_files:
            st.markdown(f"- `{file_path}`")


def render_dependencies(results: dict):
    """Render dependencies section."""
    st.header("📦 Dependencies")
    config = results["config_data"]
    deps = results["master_json"]["dependencies"]
    frameworks = results["master_json"]["frameworks"]

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Frontend")
        if frameworks.get("frontend"):
            st.markdown("**Frameworks:** " + ", ".join(f"`{f}`" for f in frameworks["frontend"]))
        if deps.get("frontend"):
            with st.expander(f"Dependencies ({len(deps['frontend'])})", expanded=False):
                for dep in sorted(deps["frontend"]):
                    st.markdown(f"- `{dep}`")
        else:
            st.info("No frontend dependencies detected.")

    with col2:
        st.subheader("Backend")
        if frameworks.get("backend"):
            st.markdown("**Frameworks:** " + ", ".join(f"`{f}`" for f in frameworks["backend"]))
        if deps.get("backend"):
            with st.expander(f"Dependencies ({len(deps['backend'])})", expanded=False):
                for dep in sorted(deps["backend"]):
                    st.markdown(f"- `{dep}`")
        else:
            st.info("No backend dependencies detected.")

    # Scripts
    pkg = config.get("package_json")
    if pkg and pkg.get("scripts"):
        with st.expander("📜 npm Scripts", expanded=False):
            for name, cmd in pkg["scripts"].items():
                st.code(f"{name}: {cmd}", language="bash")


def render_file_breakdown(results: dict):
    """Render file breakdown with expandable details."""
    st.header("📁 File Breakdown")
    classification = results["classification"]
    source_analysis = results["source_analysis"]

    # Source files
    if classification["source"]:
        with st.expander(f"🔧 Source Files ({len(classification['source'])})", expanded=True):
            for analysis in source_analysis:
                fp = analysis["file_path"]
                lang = analysis.get("language", "")
                classes = analysis.get("classes", [])
                functions = analysis.get("functions", [])
                components = analysis.get("components", [])
                routes = analysis.get("routes", [])
                imports = analysis.get("imports", [])

                with st.expander(f"📄 {fp} [{lang}]", expanded=False):
                    # Generate file summary
                    summary = _generate_file_summary(analysis)
                    if summary:
                        st.info(f"**Summary:** {summary}")
                    
                    # Display static semantic description
                    semantic_desc = analysis.get("semantic_description", "")
                    if semantic_desc:
                        st.success(f"**🧠 Semantic Analysis:** {semantic_desc}")
                    
                    cols = st.columns(4)
                    cols[0].metric("Classes", len(classes))
                    cols[1].metric("Functions", len(functions))
                    cols[2].metric("Components", len(components))
                    cols[3].metric("Imports", len(imports))

                    if classes:
                        st.markdown("**Classes:**")
                        for c in classes:
                            name = c["name"] if isinstance(c, dict) else c
                            bases = c.get("bases", []) if isinstance(c, dict) else []
                            decorators = c.get("decorators", []) if isinstance(c, dict) else []
                            base_str = f" extends {', '.join(bases)}" if bases else ""
                            dec_str = f" @{', @'.join(decorators[:2])}" if decorators else ""
                            st.markdown(f"- `{name}`{base_str}{dec_str}")

                    if functions:
                        st.markdown("**Functions:**")
                        for f in functions[:30]:
                            if isinstance(f, dict):
                                name = f.get("name", "")
                                desc = f.get("description", "")
                                decorators = f.get("decorators", [])
                                dec_str = f" @{', @'.join(decorators[:2])}" if decorators else ""
                                if desc:
                                    st.markdown(f"- `{name}()`{dec_str} — {desc}")
                                else:
                                    st.markdown(f"- `{name}()`{dec_str}")
                            else:
                                st.markdown(f"- `{f}()`")

                    if components:
                        st.markdown("**React Components:**")
                        for comp in components:
                            st.markdown(f"- `<{comp}/>`")
                        
                        # Show hooks if present
                        hooks = analysis.get("react_hooks", [])
                        if hooks:
                            st.markdown(f"  **Hooks used:** {', '.join(f'`{h}`' for h in hooks)}")

                    if routes:
                        st.markdown("**Routes:**")
                        for r in routes:
                            method = r.get("method", "")
                            path = r.get("path", r.get("decorator", ""))
                            st.markdown(f"- `{method} {path}`")

    # Config files
    if classification["config"]:
        with st.expander(f"⚙️ Configuration Files ({len(classification['config'])})", expanded=False):
            for f in classification["config"]:
                st.markdown(f"- `{f['path']}` ({f['size']} bytes)")

    # Documentation
    if classification["documentation"]:
        with st.expander(f"📝 Documentation ({len(classification['documentation'])})", expanded=False):
            for f in classification["documentation"]:
                st.markdown(f"- `{f['path']}`")

    # Assets
    if classification["asset"]:
        with st.expander(f"🎨 Assets ({len(classification['asset'])})", expanded=False):
            for f in classification["asset"]:
                st.markdown(f"- `{f['path']}` ({f['size']} bytes)")


def render_infrastructure(results: dict):
    """Render infrastructure details."""
    st.header("🏗️ Infrastructure")
    infra = results["master_json"]["infrastructure"]
    config = results["config_data"]

    col1, col2 = st.columns(2)
    col1.metric("Docker", "✅ Used" if infra["docker_used"] else "❌ Not detected")
    col2.metric("CI/CD", "✅ Detected" if infra["ci_cd_detected"] else "❌ Not detected")

    # Dockerfile details
    if config.get("dockerfile"):
        df = config["dockerfile"]
        with st.expander("🐳 Dockerfile Details", expanded=True):
            st.markdown(f"**Base Image(s):** {', '.join(f'`{img}`' for img in df.get('base_images', []))}")
            if df.get("exposed_ports"):
                st.markdown(f"**Exposed Ports:** {', '.join(df['exposed_ports'])}")
            if df.get("cmd"):
                st.markdown(f"**CMD:** `{df['cmd']}`")
            if df.get("entrypoint"):
                st.markdown(f"**ENTRYPOINT:** `{df['entrypoint']}`")
            if df.get("is_multistage"):
                st.markdown(f"**Multi-stage Build:** ✅ ({df['stages']} stages)")

    # Docker Compose details
    if config.get("docker_compose"):
        dc = config["docker_compose"]
        with st.expander("🐙 Docker Compose Details", expanded=False):
            if dc.get("services"):
                st.markdown(f"**Services:** {', '.join(f'`{s}`' for s in dc['services'])}")
            st.markdown(f"**Volumes:** {'✅' if dc.get('has_volumes') else '❌'}")
            st.markdown(f"**Networks:** {'✅' if dc.get('has_networks') else '❌'}")


def render_architecture_diagrams(results: dict):
    """Render architecture diagrams."""
    st.header("📊 Architecture Diagrams")
    graphs = results["graphs"]

    has_any_diagram = False

    # Module Dependencies
    if graphs["module_dependency"]["png"]:
        has_any_diagram = True
        with st.expander("🔗 Module Dependency Graph", expanded=True):
            try:
                st.image(graphs["module_dependency"]["png"], width="stretch")
                st.caption("Visual representation of module imports and dependencies")
            except Exception as e:
                st.error(f"Could not render module dependency graph: {e}")
    elif graphs["module_dependency"]["adjacency"]:
        has_any_diagram = True
        with st.expander("🔗 Module Dependency Graph (Data)", expanded=True):
            st.caption("Graphviz not available. Showing adjacency list instead.")
            st.json(graphs["module_dependency"]["adjacency"])

    # API Routes
    if graphs["api_routes"]["png"]:
        has_any_diagram = True
        with st.expander("🛣️ API Route Flow", expanded=True):
            try:
                st.image(graphs["api_routes"]["png"], width="stretch")
                st.caption("API endpoints and their handler functions")
            except Exception as e:
                st.error(f"Could not render API route graph: {e}")
    elif graphs["api_routes"]["adjacency"]:
        has_any_diagram = True
        with st.expander("🛣️ API Route Flow (Data)", expanded=True):
            st.caption("Graphviz not available. Showing adjacency list instead.")
            st.json(graphs["api_routes"]["adjacency"])

    # Component Graph
    if graphs["component_graph"]["png"]:
        has_any_diagram = True
        with st.expander("⚛️ React Component Graph", expanded=True):
            try:
                st.image(graphs["component_graph"]["png"], width="stretch")
                st.caption("React component relationships and dependencies")
            except Exception as e:
                st.error(f"Could not render component graph: {e}")
    elif graphs["component_graph"]["adjacency"]:
        has_any_diagram = True
        with st.expander("⚛️ React Component Graph (Data)", expanded=True):
            st.caption("Graphviz not available. Showing adjacency list instead.")
            st.json(graphs["component_graph"]["adjacency"])

    if not has_any_diagram:
        st.info("No architecture diagrams were generated. This may happen for very small repositories or when Graphviz is not installed.")
        st.markdown("**Install Graphviz:**")
        st.code("Ubuntu/Debian: sudo apt install graphviz\nmacOS: brew install graphviz\nWindows: choco install graphviz OR download from graphviz.org", language="bash")


def render_ai_repo_analysis(results: dict):
    """Render the structured AI Repo Analysis panel: quality score, tech stack, complexity, improvements."""
    analysis = results.get("ai_analysis")
    if not analysis:
        return

    source = analysis.get("ai_generated", False)
    badge_color = "#22c55e" if source else "#94a3b8"
    badge_label = "AI-Generated" if source else "Heuristic"

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:0.8rem;margin-bottom:1.2rem;">
            <span style="font-size:1.55rem;font-weight:800;
                background:linear-gradient(90deg,#67e8f9,#818cf8);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                AI Repo Analysis
            </span>
            <span style="padding:3px 12px;border-radius:999px;font-size:0.75rem;font-weight:700;
                background:rgba(0,0,0,0.25);border:1px solid {badge_color};color:{badge_color};">
                {badge_label}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Purpose ───────────────────────────────────────────────────────────────
    purpose = analysis.get("purpose", "")
    summary = analysis.get("project_summary", "")
    if purpose:
        st.markdown(
            f"""<div class="dashboard-card">
                <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.08em;
                    color:#64748b;font-weight:700;margin-bottom:6px;">🎯 Project Purpose</div>
                <div style="font-size:1.05rem;color:#e2e8f0;">{purpose}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    if summary:
        st.info(f"**Project Summary:** {summary}")

    # ── Quality Score + Complexity ────────────────────────────────────────────
    col_score, col_cx = st.columns([3, 2])

    with col_score:
        score = analysis.get("code_quality_score", 0)
        if score >= 80:
            sc_color, sc_label = "#22c55e", "Excellent"
        elif score >= 65:
            sc_color, sc_label = "#4ade80", "Good"
        elif score >= 45:
            sc_color, sc_label = "#f59e0b", "Fair"
        else:
            sc_color, sc_label = "#ef4444", "Needs Attention"

        st.markdown(
            f"""
            <div class="dashboard-card">
                <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.08em;
                    color:#64748b;font-weight:700;margin-bottom:10px;">📊 Code Quality Score</div>
                <div style="display:flex;align-items:center;gap:1.2rem;">
                    <div style="font-size:3.4rem;font-weight:900;line-height:1;color:{sc_color};">{score}</div>
                    <div style="flex:1;">
                        <div style="color:{sc_color};font-weight:700;font-size:1.05rem;">{sc_label}</div>
                        <div style="background:rgba(255,255,255,0.08);border-radius:12px;height:10px;
                            width:100%;overflow:hidden;margin-top:8px;">
                            <div style="background:{sc_color};height:100%;width:{score}%;
                                border-radius:12px;transition:width 0.4s;"></div>
                        </div>
                        <div style="color:#64748b;font-size:0.78rem;margin-top:4px;">out of 100</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_cx:
        complexity = analysis.get("complexity", "Medium")
        cx_map = {
            "Low": ("#22c55e", "🟢"),
            "Medium": ("#f59e0b", "🟡"),
            "High": ("#f97316", "🟠"),
            "Very High": ("#ef4444", "🔴"),
        }
        cx_color, cx_icon = cx_map.get(complexity, ("#94a3b8", "⚪"))

        st.markdown(
            f"""
            <div class="dashboard-card" style="height:100%;">
                <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.08em;
                    color:#64748b;font-weight:700;margin-bottom:10px;">⚙️ Project Complexity</div>
                <div style="font-size:2.5rem;font-weight:900;color:{cx_color};line-height:1;">
                    {cx_icon} {complexity}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Tech Stack ────────────────────────────────────────────────────────────
    tech_stack = analysis.get("tech_stack", [])
    if tech_stack:
        st.markdown(
            """<div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.08em;
                color:#64748b;font-weight:700;margin:1.2rem 0 0.5rem 0;">🛠️ Tech Stack Detected</div>""",
            unsafe_allow_html=True,
        )
        pills = " ".join(
            f'<span style="display:inline-block;padding:5px 16px;border-radius:999px;'
            f'background:rgba(99,179,237,0.12);border:1px solid rgba(99,179,237,0.35);'
            f'color:#93c5fd;font-size:0.87rem;font-weight:600;margin:3px 4px 3px 0;">{t}</span>'
            for t in tech_stack
        )
        st.markdown(f'<div style="margin-bottom:1rem;">{pills}</div>', unsafe_allow_html=True)

    # ── Suggested Improvements ────────────────────────────────────────────────
    improvements = analysis.get("suggested_improvements", [])
    if improvements:
        st.markdown(
            """<div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.08em;
                color:#64748b;font-weight:700;margin:1rem 0 0.6rem 0;">💡 Suggested Improvements</div>""",
            unsafe_allow_html=True,
        )
        for i, tip in enumerate(improvements, 1):
            st.markdown(
                f"""<div style="padding:12px 16px;margin:6px 0;
                    border-left:3px solid #f59e0b;
                    background:rgba(245,158,11,0.07);
                    border-radius:0 10px 10px 0;">
                    <span style="color:#fbbf24;font-weight:700;">#{i}</span>&nbsp;&nbsp;{tip}
                </div>""",
                unsafe_allow_html=True,
            )

    st.divider()


def render_ai_review(results: dict):
    """Render AI architectural review section."""
    st.header("🤖 AI Architectural Review")
    status = get_model_status()

    if not status.get("available"):
        st.info("AI review is currently unavailable. Detailed static analysis is still available in other tabs.")
        return

    ai_result = results.get("ai_review")
    if ai_result and ai_result.get("success"):
        st.markdown(ai_result["review"])
    elif ai_result:
        st.info("AI review is currently unavailable. Detailed static analysis is still available in other tabs.")


def render_raw_json(results: dict):
    """Render downloadable raw JSON."""
    with st.expander("📋 Raw Analysis JSON", expanded=False):
        json_str = json.dumps(results["master_json"], indent=2, default=str)
        st.download_button(
            label="⬇️ Download Full Analysis JSON",
            data=json_str,
            file_name=f"{results['repo_data']['repo']}_analysis.json",
            mime="application/json",
        )
        st.json(results["master_json"])


def _generate_file_summary(analysis: dict) -> str:
    """Generate a brief human-readable summary of what a file does."""
    fp = analysis["file_path"]
    lang = analysis.get("language", "")
    classes = analysis.get("classes", [])
    functions = analysis.get("functions", [])
    components = analysis.get("components", [])
    routes = analysis.get("routes", [])
    
    summary_parts = []
    
    if components:
        summary_parts.append(f"Defines {len(components)} React component(s): {', '.join(components[:3])}")
    elif classes:
        class_names = [c["name"] if isinstance(c, dict) else c for c in classes[:3]]
        summary_parts.append(f"Defines {len(classes)} class(es): {', '.join(class_names)}")
    elif routes:
        route_methods = [r.get("method", "ROUTE") for r in routes[:3]]
        summary_parts.append(f"API endpoint file with {len(routes)} route(s): {', '.join(set(route_methods))}")
    elif functions and len(functions) > 0:
        func_names = [f["name"] if isinstance(f, dict) else f for f in functions[:3]]
        summary_parts.append(f"{lang} module with {len(functions)} function(s) including {', '.join(func_names)}")
    
    if "test" in fp.lower() or "spec" in fp.lower():
        summary_parts.append("Test file")
    
    return " • ".join(summary_parts) if summary_parts else f"{lang} source file"


# PDF generation is now handled by the dedicated pdf_generator module
# See pdf_generator.py for the comprehensive PDF generation implementation


def render_pdf_export(results: dict):
    """Render PDF export button."""
    st.header("📄 Export Report")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("📥 Generate PDF Report", type="primary", width="stretch"):
            with st.spinner("Generating comprehensive PDF report..."):
                try:
                    pdf_bytes = generate_comprehensive_pdf_report(results)
                    st.download_button(
                        label="⬇️ Download PDF Report",
                        data=pdf_bytes,
                        file_name=f"{results['repo_data']['repo']}_intelligence_report.pdf",
                        mime="application/pdf",
                        width="stretch",
                    )
                    st.success("PDF generated successfully!")
                except Exception as e:
                    st.error(f"Failed to generate PDF: {e}")


def _render_tab_persistence_script() -> None:
    """Persist and restore selected results tab across reruns."""
    st.markdown(
        """
        <script>
        (() => {
            const KEY = 'repo_intelligence_active_tab';

            function bindAndRestoreTabs() {
                const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
                if (!tabs.length) {
                    return;
                }

                // Restore previously selected tab index.
                const saved = window.sessionStorage.getItem(KEY);
                const idx = saved !== null ? parseInt(saved, 10) : NaN;
                if (!Number.isNaN(idx) && idx >= 0 && idx < tabs.length) {
                    tabs[idx].click();
                }

                // Save selected tab whenever user clicks.
                tabs.forEach((tab, i) => {
                    tab.addEventListener('click', () => {
                        window.sessionStorage.setItem(KEY, String(i));
                    }, { once: false });
                });
            }

            // Streamlit rerenders frequently, so bind after initial paint.
            setTimeout(bindAndRestoreTabs, 100);
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────

def render_sidebar():
    """Render sidebar with configuration."""
    with st.sidebar:
        st.markdown("### 📖 About")
        st.markdown(
            "Repo Intelligence Engine performs deep static analysis "
            "of public GitHub repositories and generates AI-powered "
            "architectural reviews.\n\n"
            "**Features:**\n"
            "- Multi-language source parsing\n"
            "- Dependency analysis\n"
            "- Architecture diagrams\n"
            "- React component detection\n"
            "- API route mapping\n"
            "- AI architectural review"
        )
        st.caption("Start with a repository URL. The app explains the structure in plain English before showing technical detail.")

        # Optional GitHub sign-in controls (public repos can still run without sign-in)
        st.divider()
        st.markdown("### 🔐 GitHub Access")
        st.caption("Optional for public repositories. Required for private repositories.")

        authorize_url = _build_github_oauth_authorize_url()
        oauth_user = st.session_state.get("github_oauth_user")
        oauth_token = st.session_state.get("github_oauth_token")
        if oauth_token:
            username = (oauth_user or {}).get("login", "GitHub user")
            st.success(f"🔑 Signed in as @{username}")
            if st.button("Sign out GitHub", key="github_oauth_signout", width="stretch"):
                _revoke_github_oauth_token(oauth_token)
                st.session_state.pop("github_oauth_token", None)
                st.session_state.pop("github_oauth_user", None)
                st.session_state.pop("github_oauth_last_code", None)
                st.session_state.pop("github_oauth_state", None)
                st.rerun()
        else:
            st.info("Not signed in. Public repositories will still work.")
            if authorize_url:
                st.link_button("Sign in with GitHub", authorize_url, width="stretch")
            else:
                st.caption("GitHub OAuth is not configured in secrets.")

        st.divider()
        st.markdown("### 👨‍💻 Developer")
        developers = [
            {
                "name": "Reddisekharyadav",
                "url": "https://github.com/Reddisekharyadav",
                "images": [
                    # "assets/images/reddisekharyadav1.jpg",
                    "assets/images/reddisekharyadav.jpg"
                ],
            },
            {
                "name": "kuruvamunirangadu",
                "url": "https://github.com/kuruvamunirangadu",
                "images": ["assets/images/kuruvamunirangadu.png"],
            },
        ]

        dev_cols = st.columns(2, gap="small")
        for idx, developer in enumerate(developers):
            with dev_cols[idx]:
                st.markdown('<div class="developer-card">', unsafe_allow_html=True)

                selected_image = None
                for rel_path in developer.get("images", []):
                    abs_path = Path(__file__).resolve().parent / rel_path
                    if abs_path.exists():
                        selected_image = str(abs_path)
                        break

                if selected_image:
                    st.markdown('<div class="developer-image-shell">', unsafe_allow_html=True)
                    st.image(selected_image, width="stretch")
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.info("Image not found")

                st.markdown(
                    f'<p class="developer-name">{developer["name"]}</p>',
                    unsafe_allow_html=True,
                )
                st.link_button(
                    f'🔗 View GitHub',
                    developer["url"],
                    width="stretch",
                )
                st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        st.caption("Built with Streamlit · Graphviz · AI Providers")


def render_private_repo_signin_prompt():
    """Render a small sign-in prompt for private repository access."""
    prompt = st.session_state.get("private_repo_signin_prompt")
    if not prompt:
        return

    authorize_url = prompt.get("authorize_url")
    message = prompt.get("message") or "Private repository detected. Sign in with GitHub to continue analysis."

    if hasattr(st, "dialog"):
        @st.dialog("GitHub Sign-In Required")
        def _private_repo_dialog():
            st.write(message)
            st.caption("Public repositories do not require sign-in. GitHub OAuth opens github.com for secure consent, then returns here and resumes analysis.")
            if authorize_url:
                st.link_button("Continue with GitHub Sign-In", authorize_url, width="stretch")
            if st.button("Close", width="stretch"):
                st.session_state.pop("private_repo_signin_prompt", None)
                st.rerun()

        _private_repo_dialog()
    else:
        st.warning(message)
        if authorize_url:
            st.link_button("Continue with GitHub Sign-In", authorize_url)


def render_feedback_section():
    """Render end-user feedback form at the bottom of the page."""
    st.markdown("---")
    st.markdown(
        """
        <div class="feedback-panel">
            <p class="feedback-title">Share Your Feedback</p>
            <p class="feedback-subtitle">Tell us what worked well and what should improve.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("user_feedback_form", clear_on_submit=True):
        rating = st.slider("Overall experience", min_value=1, max_value=5, value=4)
        feedback_text = st.text_area(
            "Your feedback",
            placeholder="Example: The dashboard is great. It would help to add a compare-branches view.",
            max_chars=1000,
        )
        contact = st.text_input("Email or GitHub (optional)", placeholder="you@example.com or github.com/yourname")
        submitted = st.form_submit_button("Submit Feedback", width="stretch")

    if submitted:
        clean_feedback = feedback_text.strip()
        if not clean_feedback:
            st.warning("Please add a short feedback message before submitting.")
            return

        payload = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rating": rating,
            "feedback": clean_feedback,
            "contact": contact.strip(),
        }
        if _append_feedback_entry(payload):
            st.success("Thanks for the feedback. Your response has been saved.")
        else:
            st.error("Unable to save feedback right now. Please try again.")

    recent_feedback = _load_feedback_entries()
    if recent_feedback:
        st.markdown("#### Recent Feedback")
        for item in reversed(recent_feedback):
            rating_value = int(item.get("rating", 0) or 0)
            rating_value = max(0, min(5, rating_value))
            stars = "★" * rating_value + "☆" * (5 - rating_value)

            created_at = item.get("created_at", "")
            try:
                created_display = datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
            except (TypeError, ValueError):
                created_display = "Unknown time"

            feedback_body = str(item.get("feedback", "")).strip()
            if len(feedback_body) > 220:
                feedback_body = f"{feedback_body[:220].rstrip()}..."

            contact_text = str(item.get("contact", "")).strip()
            contact_line = f" • by {contact_text}" if contact_text else ""

            st.markdown(
                f"""
                <div style="padding:0.75rem 0.85rem;margin:0.45rem 0;border:1px solid rgba(128,191,255,0.2);
                    border-radius:10px;background:rgba(255,255,255,0.02);">
                    <div style="font-weight:700;color:#d9eeff;font-size:0.92rem;">{stars}</div>
                    <div style="color:#afc4d8;font-size:0.82rem;margin:0.2rem 0 0.45rem 0;">{created_display}{contact_line}</div>
                    <div style="color:#e8f4ff;font-size:0.92rem;line-height:1.4;">{feedback_body}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _is_review_edit_mode() -> bool:
    """Return True when hidden feedback review/edit mode is requested."""
    raw = _get_query_param_value("review-edit")
    if raw is None:
        raw = _get_query_param_value("review_edit")
    if raw is None:
        return False

    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def render_feedback_review_editor():
    """Render hidden feedback editor page for review/edit operations."""
    st.title("Feedback Review Editor")
    st.caption("Hidden maintenance page for editing or deleting feedback entries.")

    entries = _load_feedback_entries()
    if not entries:
        st.info("No feedback entries found.")
        return

    st.markdown(f"Total entries: **{len(entries)}**")

    for reverse_index, item in enumerate(reversed(entries)):
        original_index = len(entries) - 1 - reverse_index
        created_at = str(item.get("created_at", "")).strip() or "Unknown time"
        feedback_preview = str(item.get("feedback", "")).strip() or "(empty feedback)"
        if len(feedback_preview) > 80:
            feedback_preview = f"{feedback_preview[:80].rstrip()}..."

        with st.expander(f"Entry {original_index + 1} | {created_at} | {feedback_preview}"):
            with st.form(f"review_edit_form_{original_index}"):
                rating_value = int(item.get("rating", 4) or 4)
                rating_value = max(1, min(5, rating_value))

                updated_rating = st.slider(
                    "Rating",
                    min_value=1,
                    max_value=5,
                    value=rating_value,
                    key=f"review_rating_{original_index}",
                )
                updated_feedback = st.text_area(
                    "Feedback",
                    value=str(item.get("feedback", "")),
                    max_chars=1000,
                    key=f"review_feedback_{original_index}",
                )
                updated_contact = st.text_input(
                    "Email or GitHub",
                    value=str(item.get("contact", "")),
                    key=f"review_contact_{original_index}",
                )

                save_clicked = st.form_submit_button("Save Changes", width="stretch")

            if save_clicked:
                clean_feedback = updated_feedback.strip()
                if not clean_feedback:
                    st.warning("Feedback cannot be empty.")
                else:
                    updated_entry = {
                        "created_at": str(item.get("created_at", "")),
                        "rating": updated_rating,
                        "feedback": clean_feedback,
                        "contact": updated_contact.strip(),
                    }
                    if _update_feedback_entry(original_index, updated_entry):
                        st.success("Entry updated.")
                        st.rerun()
                    else:
                        st.error("Unable to update entry.")

            if st.button("Delete Entry", key=f"review_delete_{original_index}", type="secondary"):
                if _delete_feedback_entry(original_index):
                    st.success("Entry deleted.")
                    st.rerun()
                else:
                    st.error("Unable to delete entry.")


# ──────────────────────────────────────────────
# Main Application
# ──────────────────────────────────────────────

def main():
    """Main application entry point."""
    oauth_notice = _handle_github_oauth_callback()

    # Log API token status to console
    github_token = _get_runtime_github_token()
    model_status = get_model_status()
    
    print("\n" + "="*60)
    print("[INFO] Repo Intelligence Engine - API Configuration")
    print("="*60)
    print(f"GitHub Token: {'✅ Configured' if github_token else '❌ Not Set (rate limited)'}")
    if model_status.get("available"):
        print(
            f"AI Provider: ✅ {model_status.get('provider')}"
            f" ({model_status.get('model')})"
        )
    else:
        print(f"AI Provider: ❌ Not Ready ({model_status.get('reason', 'not configured')})")
    print("="*60 + "\n")

    if oauth_notice:
        level, message = oauth_notice
        if level == "success":
            st.success(message)
        elif level == "error":
            st.error(message)
    
    render_header()
    render_sidebar()
    render_private_repo_signin_prompt()

    if _is_review_edit_mode():
        render_feedback_review_editor()
        return

    if "analysis_results" not in st.session_state:
        render_first_run_dashboard()

    # URL Input
    st.markdown("### Analyze A Repository")
    repo_url = st.text_input(
        "🔗 GitHub Repository URL",
        placeholder="https://github.com/owner/repo",
        help="Enter a public GitHub repository URL to analyze.",
        key="repo_url_input",
    )

    # If OAuth succeeded and a private repo was pending, resume automatically.
    if oauth_notice and oauth_notice[0] == "success":
        pending_repo_url = st.session_state.get("pending_repo_url")
        if pending_repo_url and "analysis_results" not in st.session_state:
            with st.spinner("Resuming private repository analysis after sign-in..."):
                try:
                    results = run_analysis(pending_repo_url)
                    st.session_state["analysis_results"] = results
                    st.session_state["repo_url_input"] = pending_repo_url
                    st.session_state.pop("pending_repo_url", None)
                    st.session_state.pop("private_repo_signin_prompt", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not resume analysis automatically: {e}")

    col1, col2, col3 = st.columns([1, 1, 4])
    analyze_btn = col1.button("🚀 Analyze", type="primary", width="stretch")
    clear_btn = col2.button("🗑️ Clear", width="stretch")

    if clear_btn:
        st.session_state.pop("analysis_results", None)
        st.rerun()

    # Run analysis
    if analyze_btn and repo_url:
        # Validate URL
        try:
            parse_github_url(repo_url)
        except ValueError as e:
            st.error(str(e))
            return

        try:
            results = run_analysis(repo_url)
            st.session_state["analysis_results"] = results
        except GitHubSignInRequired as e:
            st.session_state["pending_repo_url"] = repo_url
            st.session_state["private_repo_signin_prompt"] = {
                "message": str(e),
                "authorize_url": e.authorize_url,
            }
            st.rerun()
        except ValueError as e:
            error_text = str(e)
            st.error(f"❌ {error_text}")
            if (
                "Repository not found or access denied" in error_text
                and not _get_user_github_token()
            ):
                authorize_url = _build_github_oauth_authorize_url()
                if authorize_url:
                    st.info("If this repository is private, sign in with GitHub and retry the analysis.")
                    st.link_button("Sign in with GitHub", authorize_url)
            return
        except RuntimeError as e:
            st.error(f"❌ {str(e)}")
            return
        except Exception as e:
            st.error(f"❌ An unexpected error occurred: {str(e)}")
            return

    elif analyze_btn and not repo_url:
        st.warning("Please enter a GitHub repository URL.")
        return

    # Render results
    if "analysis_results" in st.session_state:
        results = st.session_state["analysis_results"]

        render_analysis_command_center(results)

        # AI Repo Analysis — always runs (heuristic fallback when no AI key)
        if "ai_analysis" not in results:
            with st.spinner("🔍 Running AI repository analysis..."):
                results["ai_analysis"] = get_ai_repo_analysis(results["master_json"])

        # AI Architectural Review — only when AI provider is live
        model_status = get_model_status()
        if model_status.get("available") and "ai_review" not in results:
            with st.spinner("🧠 Generating AI architectural review..."):
                ai_result = get_ai_review(results["master_json"])
                results["ai_review"] = ai_result

        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "Guidance",
            "Overview",
            "Insights",
            "Files",
            "Architecture",
            "🤖 AI Analysis",
            "Export",
        ])

        _render_tab_persistence_script()

        with tab1:
            render_repo_read_guidance(results)
            render_dependencies(results)

        with tab2:
            render_project_overview(results)
            render_infrastructure(results)

        with tab3:
            render_repository_insights(results)

        with tab4:
            render_file_breakdown(results)

        with tab5:
            render_architecture_diagrams(results)

        with tab6:
            render_ai_repo_analysis(results)
            render_ai_review(results)

        with tab7:
            render_pdf_export(results)
            render_raw_json(results)

    render_feedback_section()


if __name__ == "__main__":
    main()

