# 🔍 Repo Intelligence Engine

Advanced repository intelligence analysis and AI architectural review for GitHub repositories, with support for OpenAI, Google Gemini, and Hugging Face.

## Features

- **Multi-Language Parsing** — Python (AST), JavaScript/TypeScript (regex), JSX/TSX (React component detection), Java, Go, C#, C++, PHP
- **Dependency Analysis** — `package.json`, `requirements.txt`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`
- **Architecture Diagrams** — Module dependency graph, API route flow, React component relationship graph (Graphviz)
- **Framework Detection** — Next.js, Vite, Express, FastAPI, Django, Flask, Angular, Vue, and more
- **Infrastructure Detection** — Docker, CI/CD pipelines
- **AI Architectural Review** — Powered by OpenAI, Google Gemini, or Hugging Face
- **GitHub Authentication Options** — Session token entry or GitHub OAuth sign-in

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** You also need [Graphviz](https://graphviz.org/download/) installed on your system for architecture diagrams. On Ubuntu: `sudo apt install graphviz`. On macOS: `brew install graphviz`. On Windows: download from the Graphviz website and add to PATH.

### 2. Run the App

```bash
streamlit run app.py
```

### 3. Open in Browser

Navigate to `http://localhost:8501`

## Configuration

### GitHub Access (Optional, Recommended)

Without a token, GitHub API is limited to 60 requests/hour. With a token, the limit is 5,000/hour.

Set via environment variable:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Or add to `.streamlit/secrets.toml`:

```toml
GITHUB_TOKEN = "ghp_your_token_here"
```

The app also supports:

- Session-only GitHub token entry from the sidebar
- GitHub OAuth sign-in for per-user access without asking users to paste a PAT manually

### AI Provider Configuration

Set one of the following providers:

#### OpenAI

```bash
export AI_PROVIDER=openai
export OPENAI_API_KEY=sk_your_key_here
export OPENAI_MODEL=gpt-4o-mini
```

#### Google Gemini

```bash
export AI_PROVIDER=gemini
export GEMINI_API_KEY=your_gemini_key_here
export GEMINI_MODEL=gemini-1.5-pro
```

#### Hugging Face

Get a free token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

Set via environment variable:

```bash
export HF_API_TOKEN=hf_your_token_here
```

Or add to `.streamlit/secrets.toml`:

```toml
HF_API_TOKEN = "hf_your_token_here"
```

If `AI_PROVIDER` is not set, the app will auto-select the first configured provider in this order:

1. OpenAI
2. Gemini
3. Hugging Face

### GitHub OAuth Configuration

If you want users to sign in with GitHub instead of pasting a token, configure a GitHub OAuth App and set:

```toml
GITHUB_OAUTH_CLIENT_ID = "your_client_id"
GITHUB_OAUTH_CLIENT_SECRET = "your_client_secret"
GITHUB_OAUTH_REDIRECT_URI = "http://localhost:8501"
GITHUB_OAUTH_SCOPE = "public_repo"
```

Notes:

- Tokens from GitHub OAuth are used only for the current app session.
- Sign out clears the session token and attempts a best-effort revoke.
- For private repository access, the signed-in GitHub user must already have permission to the target repository.

## Deploy to Streamlit Community Cloud

1. Push this project to a GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io/).
3. Click **"New app"** and select your repository.
4. Set the main file path to `app.py`.
5. Go to **Advanced settings > Secrets** and add the secrets you need:

```toml
GITHUB_TOKEN = "ghp_your_token_here"
AI_PROVIDER = "openai"
OPENAI_API_KEY = "sk_your_openai_key"
OPENAI_MODEL = "gpt-4o-mini"
```

Optional OAuth setup for end-user GitHub sign-in:

```toml
GITHUB_OAUTH_CLIENT_ID = "your_client_id"
GITHUB_OAUTH_CLIENT_SECRET = "your_client_secret"
GITHUB_OAUTH_REDIRECT_URI = "https://your-app-name.streamlit.app"
GITHUB_OAUTH_SCOPE = "public_repo"
```

6. Click **Deploy**.

## Project Structure

```
repo_intelligence/
├── app.py               # Streamlit web application
├── github_fetcher.py    # GitHub REST API integration
├── file_classifier.py   # File type classification engine
├── static_parser.py     # Multi-language static code analysis
├── config_parser.py     # Configuration file parser
├── graph_builder.py     # Graphviz architecture diagram generator
├── ai_interpreter.py    # Provider-agnostic AI interpretation layer
├── local_inference.py   # OpenAI/Gemini/Hugging Face inference engine
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## How It Works

1. **Fetch** — Recursively fetches the repository tree via GitHub REST API (`GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1`)
2. **Classify** — Categorizes files into source, config, documentation, and assets
3. **Parse** — Extracts classes, functions, components, imports, routes, and dependencies
4. **Graph** — Builds architecture diagrams using Graphviz
5. **Analyze** — Sends structured metadata (never raw code) to the configured AI provider for architectural review

## Security Notes

- Never commit API keys or OAuth secrets to the repository.
- Keep `.streamlit/secrets.toml` local or use your deployment platform secret store.
- GitHub OAuth does not expose the user's password to this app.
- If publishing this app, prefer OAuth or session-only user tokens over sharing a single personal token with all users.

## Limits

| Limit | Value |
|-------|-------|
| Max files processed | 100 |
| Max file size | 200 KB |
| Skipped directories | `node_modules`, `.git`, `dist`, `build`, `.next`, `coverage`, `__pycache__`, `venv` |

## License

MIT
