"""
File Type Classifier
Classifies repository files into categories: source, config, documentation, assets.
"""

import mimetypes
from typing import Optional

SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".cpp", ".go", ".cs", ".php",
}

CONFIG_FILES = {
    "package.json", "requirements.txt", "dockerfile", "docker-compose.yml",
    "docker-compose.yaml", "tsconfig.json", "next.config.js", "next.config.mjs",
    "vite.config.ts", "vite.config.js", ".env", ".env.local", ".env.production",
    "pom.xml", "build.gradle", "setup.py", "setup.cfg", "pyproject.toml",
    "cargo.toml", "go.mod", "go.sum", "gemfile", "composer.json",
    "webpack.config.js", "babel.config.js", ".babelrc", ".eslintrc",
    ".eslintrc.js", ".eslintrc.json", ".prettierrc", "jest.config.js",
    "jest.config.ts", "tailwind.config.js", "tailwind.config.ts",
    "postcss.config.js", "nginx.conf", "makefile", "procfile",
}

CONFIG_EXTENSIONS = {
    ".yml", ".yaml", ".toml", ".ini", ".cfg",
}

DOCUMENTATION_EXTENSIONS = {
    ".md", ".rst", ".txt",
}

ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".svg", ".gif",
    ".pdf", ".mp4", ".zip", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".mp3",
    ".wav", ".avi", ".mov", ".tar", ".gz",
}

CI_CD_PATTERNS = {
    ".github/workflows", "jenkinsfile", ".travis.yml",
    ".circleci", "azure-pipelines.yml", ".gitlab-ci.yml",
    "bitbucket-pipelines.yml", "cloudbuild.yaml",
}

LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".jsx": "JavaScript (React)",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".go": "Go",
    ".cs": "C#",
    ".php": "PHP",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".r": "R",
}


def get_file_extension(path: str) -> str:
    """Get lowercase file extension from path."""
    if "." in path.rsplit("/", 1)[-1]:
        return "." + path.rsplit(".", 1)[-1].lower()
    return ""


def get_filename(path: str) -> str:
    """Get lowercase filename from path."""
    return path.rsplit("/", 1)[-1].lower()


def classify_file(path: str) -> str:
    """
    Classify a file into a category.
    Returns: 'source', 'config', 'documentation', 'asset', or 'other'
    """
    ext = get_file_extension(path)
    filename = get_filename(path)

    if ext in SOURCE_EXTENSIONS:
        return "source"
    if filename in CONFIG_FILES or ext in CONFIG_EXTENSIONS:
        return "config"
    if ext in DOCUMENTATION_EXTENSIONS:
        return "documentation"
    if ext in ASSET_EXTENSIONS:
        return "asset"

    # Check by mimetype
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type:
        if mime_type.startswith("image/") or mime_type.startswith("video/"):
            return "asset"
        if mime_type.startswith("text/"):
            return "other"

    return "other"


def detect_language(path: str) -> Optional[str]:
    """Detect programming language from file extension."""
    ext = get_file_extension(path)
    return LANGUAGE_MAP.get(ext)


def is_ci_cd_file(path: str) -> bool:
    """Check if a file is part of CI/CD configuration."""
    path_lower = path.lower()
    for pattern in CI_CD_PATTERNS:
        if pattern in path_lower:
            return True
    return False


def classify_all_files(files: list[dict]) -> dict:
    """
    Classify all files and return structured breakdown.
    """
    result = {
        "source": [],
        "config": [],
        "documentation": [],
        "asset": [],
        "other": [],
        "ci_cd_detected": False,
    }

    for f in files:
        path = f["path"]
        category = classify_file(path)
        language = detect_language(path)

        entry = {
            "path": path,
            "category": category,
            "language": language,
            "size": f.get("size", 0),
            "has_content": f.get("content") is not None,
        }

        result[category].append(entry)

        if is_ci_cd_file(path):
            result["ci_cd_detected"] = True

    return result


def detect_primary_language(files: list[dict]) -> str:
    """Determine the primary programming language of the repository."""
    lang_count: dict[str, int] = {}
    for f in files:
        lang = detect_language(f["path"])
        if lang:
            base_lang = lang.split(" ")[0]  # Normalize "TypeScript (React)" -> "TypeScript"
            lang_count[base_lang] = lang_count.get(base_lang, 0) + 1

    if not lang_count:
        return "Unknown"
    return max(lang_count, key=lambda lang: lang_count[lang])


def detect_project_type(files: list[dict]) -> dict:
    """
    Detect project characteristics: frontend/backend frameworks, Next.js, Vite, etc.
    """
    paths = {f["path"].lower() for f in files}
    filenames = {f["path"].rsplit("/", 1)[-1].lower() for f in files}

    result = {
        "frontend_detected": False,
        "backend_detected": False,
        "is_nextjs": False,
        "is_vite": False,
        "is_docker": False,
        "frameworks": [],
    }

    # Next.js detection
    has_next_config = any(
        n in filenames for n in ("next.config.js", "next.config.mjs", "next.config.ts")
    )
    has_pages = any(p.startswith("pages/") or "/pages/" in p for p in paths)
    has_app_dir = any(p.startswith("app/") or "/app/" in p for p in paths)
    if has_next_config or (has_pages and has_app_dir):
        result["is_nextjs"] = True
        result["frontend_detected"] = True
        result["frameworks"].append("Next.js")

    # Vite detection
    if any(n in filenames for n in ("vite.config.ts", "vite.config.js")):
        result["is_vite"] = True
        result["frontend_detected"] = True
        result["frameworks"].append("Vite")

    # Docker detection
    if "dockerfile" in filenames or "docker-compose.yml" in filenames:
        result["is_docker"] = True

    # TSX/JSX → frontend
    if any(f["path"].endswith((".tsx", ".jsx")) for f in files):
        result["frontend_detected"] = True

    # Python backend indicators
    py_files = [f for f in files if f["path"].endswith(".py")]
    if py_files:
        result["backend_detected"] = True

    # JS/TS server indicators
    if any(f["path"].endswith((".js", ".ts")) for f in files):
        for f in files:
            content = f.get("content", "") or ""
            if any(kw in content for kw in ("express(", "fastify", "@nestjs", "from fastapi", "from flask")):
                result["backend_detected"] = True
                break

    return result
