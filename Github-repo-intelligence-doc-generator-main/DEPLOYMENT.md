# Deployment Guide

## Deploy to Streamlit Cloud

### Prerequisites
- GitHub account
- Optional GitHub Personal Access Token for app-level fallback access
- Optional OpenAI, Gemini, or Hugging Face API key for AI review
- Optional GitHub OAuth App if users should sign in with GitHub

### Steps

#### 1. Create GitHub Repository

```bash
# Option A: Using GitHub CLI (if installed)
gh auth login
gh repo create repo-intelligence --public --source=. --remote=origin --push

# Option B: Manually
# 1. Go to https://github.com/new
# 2. Create a new repository named "repo-intelligence"
# 3. Don't initialize with README (we already have files)
# 4. Copy the repository URL
```

#### 2. Push Code to GitHub

If you created the repo manually:

```bash
git remote add origin https://github.com/YOUR_USERNAME/repo-intelligence.git
git branch -M main
git push -u origin main
```

#### 3. Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io/
2. Sign in with your GitHub account
3. Click "New app"
4. Select your repository: `YOUR_USERNAME/repo-intelligence`
5. Set main file path: `app.py`
6. Click "Deploy"

#### 4. Add Secrets in Streamlit Cloud

1. In your deployed app dashboard, click "Settings" → "Secrets"
2. Add the secrets you need.

Minimum example with GitHub fallback token and OpenAI:

```toml
GITHUB_TOKEN = "ghp_your_token_here"
AI_PROVIDER = "openai"
OPENAI_API_KEY = "sk_your_openai_key"
OPENAI_MODEL = "gpt-4o-mini"
```

3. Save and the app will restart automatically

### Alternative AI Providers

#### Google Gemini

```toml
AI_PROVIDER = "gemini"
GEMINI_API_KEY = "your_gemini_key"
GEMINI_MODEL = "gemini-1.5-pro"
```

#### Hugging Face

```toml
AI_PROVIDER = "huggingface"
HF_API_TOKEN = "hf_your_huggingface_token"
```

### GitHub OAuth Setup For End Users

If you want users to click "Sign in with GitHub" instead of pasting a PAT, create a GitHub OAuth App and add:

```toml
GITHUB_OAUTH_CLIENT_ID = "your_client_id"
GITHUB_OAUTH_CLIENT_SECRET = "your_client_secret"
GITHUB_OAUTH_REDIRECT_URI = "https://your-app-name.streamlit.app"
GITHUB_OAUTH_SCOPE = "public_repo"
```

Important:

- The callback URL in the GitHub OAuth App must exactly match `GITHUB_OAUTH_REDIRECT_URI`.
- For local development, use `http://localhost:8501`.
- For deployed apps, use your exact Streamlit app URL.
- OAuth tokens are stored only for the current Streamlit session.

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.streamlit/secrets.toml`:
```toml
GITHUB_TOKEN = "your_token_here"
AI_PROVIDER = "openai"
OPENAI_API_KEY = "your_openai_key_here"
```

Optional local OAuth config:

```toml
GITHUB_OAUTH_CLIENT_ID = "your_client_id"
GITHUB_OAUTH_CLIENT_SECRET = "your_client_secret"
GITHUB_OAUTH_REDIRECT_URI = "http://localhost:8501"
GITHUB_OAUTH_SCOPE = "public_repo"
```

3. Run the app:
```bash
streamlit run app.py
```

## Environment Variables

The app supports these configurations:

- `GITHUB_TOKEN` - Optional app-level GitHub PAT fallback
- `AI_PROVIDER` - Optional explicit provider: `openai`, `gemini`, or `huggingface`
- `OPENAI_API_KEY` - Optional OpenAI key
- `OPENAI_MODEL` - Optional OpenAI model override
- `GEMINI_API_KEY` - Optional Google Gemini key
- `GEMINI_MODEL` - Optional Gemini model override
- `HF_API_TOKEN` - Optional Hugging Face token
- `GITHUB_OAUTH_CLIENT_ID` - Optional GitHub OAuth client id
- `GITHUB_OAUTH_CLIENT_SECRET` - Optional GitHub OAuth client secret
- `GITHUB_OAUTH_REDIRECT_URI` - Optional GitHub OAuth redirect URI
- `GITHUB_OAUTH_SCOPE` - Optional GitHub OAuth scope, defaults to `public_repo`

## Troubleshooting

### GitHub API Rate Limits
- Without authentication: 60 requests/hour
- With authentication: 5,000 requests/hour
- Best end-user experience: GitHub OAuth or session-only user PAT

### Streamlit Cloud Issues
- Check deployment logs in Streamlit Cloud dashboard
- Verify secrets are properly configured
- Ensure requirements.txt is up to date

### AI Features Not Working
- Verify the correct provider key is configured
- Verify `AI_PROVIDER` matches the available secret, or leave it unset for auto-detection
- The app falls back to static semantic analysis when no AI provider is available

### OAuth Issues
- Confirm the OAuth callback URL matches exactly
- Confirm `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, and `GITHUB_OAUTH_REDIRECT_URI` are set
- Confirm the signed-in GitHub user has access to the repository being analyzed
