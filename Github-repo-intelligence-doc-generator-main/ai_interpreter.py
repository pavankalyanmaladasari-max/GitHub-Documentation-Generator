"""
AI Interpretation Layer.
Uses the configured provider from local_inference to generate architectural analysis.
Falls back gracefully to static semantic analysis if AI is unavailable.
"""

import json
from typing import Optional, List, Dict

from local_inference import get_inference_engine

MAX_INPUT_CHARS = 6000


def _build_prompt(structured_json: dict) -> str:
    """Build a simplified prompt for Flan-T5 model."""
    # Create a very condensed summary for Flan-T5's limited context
    summary = _condense_json(structured_json)
    
    # Extract key information
    meta = summary.get("project_metadata", {})
    lang = meta.get("primary_language", "Unknown")
    total_files = meta.get("total_files", 0)
    frontend = meta.get("frontend_detected", False)
    backend = meta.get("backend_detected", False)
    
    # Flan-T5 works best with clear instruction format
    project_type = []
    if frontend:
        project_type.append("frontend")
    if backend:
        project_type.append("backend")
    
    type_str = " and ".join(project_type) if project_type else "software"
    
    # Use summarization task which T5 models are designed for
    prompt = f"Summarize: This is a {lang} {type_str} project. Describe its architecture."
    
    return prompt


def _condense_json(data: dict) -> dict:
    """
    Condense the full analysis JSON to essential information only.
    This ensures we never send raw code — only structured metadata.
    """
    condensed = {}

    # Project metadata
    if "project_metadata" in data:
        condensed["project_metadata"] = data["project_metadata"]

    # Source analysis — only summaries, no code
    if "source_analysis" in data:
        source_summary = []
        for item in data["source_analysis"][:30]:  # Limit files
            entry = {
                "file_path": item.get("file_path", ""),
                "language": item.get("language", ""),
                "classes": [c.get("name", "") if isinstance(c, dict) else c
                           for c in item.get("classes", [])[:10]],
                "functions": [f.get("name", "") if isinstance(f, dict) else f
                             for f in item.get("functions", [])[:15]],
                "components": item.get("components", [])[:10],
                "routes": item.get("routes", [])[:10],
                "import_count": len(item.get("imports", [])),
            }
            source_summary.append(entry)
        condensed["source_analysis"] = source_summary

    # Dependencies
    if "dependencies" in data:
        condensed["dependencies"] = data["dependencies"]

    # Infrastructure
    if "infrastructure" in data:
        condensed["infrastructure"] = data["infrastructure"]

    # Frameworks
    if "frameworks" in data:
        condensed["frameworks"] = data["frameworks"]

    return condensed


def get_ai_review(
    structured_json: dict,
    hf_token: Optional[str] = None,
) -> dict:
    """
    Generate architectural review using the configured AI provider.

    Returns:
        dict with 'success' bool, 'review' text, and 'error' message if unavailable.
    """
    del hf_token

    engine = get_inference_engine()
    if not engine.is_available():
        return {
            "success": False,
            "review": None,
            "error": engine.reason or "No AI provider configured.",
        }

    summary = _condense_json(structured_json)
    prompt = (
        "You are reviewing a software repository summary. "
        "Provide a concise markdown architecture review with these sections: "
        "Overview, Key Components, Risks, Recommended Improvements. "
        "Keep it practical and specific to the provided metadata.\n\n"
        f"Repository summary:\n{json.dumps(summary, indent=2)[:MAX_INPUT_CHARS]}"
    )

    review = engine._query(prompt, max_length=700)
    if review:
        return {
            "success": True,
            "review": review,
            "error": None,
        }

    return {
        "success": False,
        "review": None,
        "error": engine.reason or "AI provider did not return a response.",
    }


def get_ai_repo_analysis(structured_json: dict) -> dict:
    """
    Run a structured AI analysis of the repository.

    Returns a dict with:
        project_summary (str), code_quality_score (int 0-100),
        tech_stack (list[str]), complexity (str), purpose (str),
        suggested_improvements (list[str]), ai_generated (bool)
    """
    heuristic = _heuristic_repo_analysis(structured_json)

    engine = get_inference_engine()
    if not engine.is_available():
        return heuristic

    summary = _condense_json(structured_json)
    prompt = (
        "You are an expert software engineer performing a structured repository review. "
        "Analyze the repository metadata below and respond ONLY with a single valid JSON object "
        "(no markdown fences, no extra text) that has exactly these fields:\n"
        "{\n"
        '  "project_summary": "<2-3 sentences describing the project>",\n'
        '  "purpose": "<1-2 sentences on what the project does>",\n'
        '  "code_quality_score": <integer 0-100>,\n'
        '  "tech_stack": ["<tech1>", "<tech2>"],\n'
        '  "complexity": "<Low|Medium|High|Very High>",\n'
        '  "suggested_improvements": ["<improvement1>", "<improvement2>", "<improvement3>"]\n'
        "}\n\n"
        "Code quality scoring guide (start at 60):\n"
        "  +12 if test files present, -12 if none\n"
        "  +8 if CI/CD config detected, -5 if absent\n"
        "  +7 if documentation files present\n"
        "  +5 if type annotations used\n"
        "  -8 if files are too large (god files)\n\n"
        f"Repository metadata:\n{json.dumps(summary, indent=2)[:MAX_INPUT_CHARS]}"
    )

    raw = engine._query(prompt, max_length=700)
    if raw:
        try:
            clean = raw.strip()
            # Strip optional markdown code fences
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) >= 2 else clean
                if clean.lower().startswith("json"):
                    clean = clean[4:]
            result = json.loads(clean.strip())
            result["code_quality_score"] = max(0, min(100, int(result.get("code_quality_score", heuristic["code_quality_score"]))))
            result.setdefault("tech_stack", heuristic["tech_stack"])
            result.setdefault("complexity", heuristic["complexity"])
            result.setdefault("project_summary", heuristic["project_summary"])
            result.setdefault("purpose", heuristic["purpose"])
            result.setdefault("suggested_improvements", heuristic["suggested_improvements"])
            result["ai_generated"] = True
            return result
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            pass

    heuristic["ai_generated"] = False
    return heuristic


def _heuristic_repo_analysis(structured_json: dict) -> dict:
    """Compute a heuristic structured analysis when AI is unavailable or as baseline."""
    meta = structured_json.get("project_metadata", {})
    source = structured_json.get("source_analysis", [])
    deps = structured_json.get("dependencies", {})
    infra = structured_json.get("infrastructure", {})
    frameworks = structured_json.get("frameworks", {})

    primary_lang = meta.get("primary_language", "Unknown")
    total_files = meta.get("total_files", 0)
    source_files = meta.get("source_files", 0)
    doc_files = meta.get("documentation_files", 0)
    project_type = meta.get("project_type", "Software Project")
    owner = meta.get("owner", "Unknown")
    repo_name = meta.get("repo", "Unknown")

    # ── Tech Stack ────────────────────────────────────────────────────────────
    tech_stack: List[str] = []
    if primary_lang:
        tech_stack.append(primary_lang)

    all_frameworks = (frameworks.get("frontend") or []) + (frameworks.get("backend") or [])
    all_deps = (deps.get("frontend") or []) + (deps.get("backend") or [])

    KNOWN_TECH = {
        "react", "vue", "angular", "svelte", "nextjs", "next", "nuxt",
        "express", "fastapi", "flask", "django", "spring", "rails", "gin",
        "postgresql", "mongodb", "redis", "mysql", "sqlite", "supabase",
        "docker", "kubernetes", "terraform", "aws", "gcp", "azure",
        "graphql", "tailwind", "bootstrap", "material-ui", "chakra",
        "jest", "pytest", "mocha", "cypress", "vitest",
        "streamlit", "gradio", "dash", "fasthtml",
    }

    seen = {t.lower() for t in tech_stack}
    for item in all_frameworks + all_deps[:25]:
        normalized = item.lower().replace("-", "").replace("_", "")
        for tech in KNOWN_TECH:
            if tech.replace("-", "") in normalized:
                display = item.split("/")[-1].split("@")[0].strip()
                if display.lower() not in seen:
                    tech_stack.append(display)
                    seen.add(display.lower())
                break

    if infra.get("docker_used") and "Docker" not in tech_stack:
        tech_stack.append("Docker")
    if infra.get("ci_cd_detected") and "CI/CD" not in tech_stack:
        tech_stack.append("CI/CD")

    tech_stack = tech_stack[:10]

    # ── Code Quality Score ────────────────────────────────────────────────────
    score = 55
    has_tests = any(
        "test" in (item.get("file_path") or "").lower()
        or "spec" in (item.get("file_path") or "").lower()
        for item in source
    )
    if has_tests:
        score += 12
    else:
        score -= 10

    if infra.get("ci_cd_detected"):
        score += 8
    else:
        score -= 5

    if doc_files > 0:
        score += 7

    if infra.get("docker_used"):
        score += 5

    if primary_lang == "Python":
        typed = sum(
            1 for item in source
            if any(
                "->" in (fn.get("signature") or "")
                for fn in item.get("functions", [])
                if isinstance(fn, dict)
            )
        )
        if typed > 0:
            score += 5

    if source:
        total_fns = sum(len(item.get("functions", [])) for item in source)
        avg_fns = total_fns / len(source)
        if avg_fns > 20:
            score -= 8
        elif 3 <= avg_fns <= 12:
            score += 5

    score = max(10, min(100, score))

    # ── Complexity ────────────────────────────────────────────────────────────
    total_fns = sum(len(item.get("functions", [])) for item in source)
    total_classes = sum(len(item.get("classes", [])) for item in source)
    cx = source_files + total_fns * 0.5 + total_classes * 2 + len(all_deps) * 0.3

    if cx < 50:
        complexity = "Low"
    elif cx < 200:
        complexity = "Medium"
    elif cx < 500:
        complexity = "High"
    else:
        complexity = "Very High"

    # ── Summaries ─────────────────────────────────────────────────────────────
    stack_str = ", ".join(tech_stack[:4]) or primary_lang
    purpose = (
        f"A {project_type} by {owner}. "
        f"Contains {total_files} files primarily written in {primary_lang}."
    )
    project_summary = (
        f"{repo_name} is a {project_type} built with {stack_str}. "
        f"It has {source_files} source files, {total_fns} functions, and {total_classes} classes. "
        f"Complexity is rated {complexity}."
    )

    # ── Improvements ──────────────────────────────────────────────────────────
    improvements: List[str] = []
    if not has_tests:
        improvements.append("Add automated tests (unit/integration) to increase reliability — no test files were detected.")
    if not infra.get("ci_cd_detected"):
        improvements.append("Set up a CI/CD pipeline (GitHub Actions, CircleCI) to automate testing and deployment.")
    if doc_files == 0:
        improvements.append("Add documentation files (README, CONTRIBUTING, API docs) for better developer onboarding.")
    if not infra.get("docker_used"):
        improvements.append("Containerize with Docker for consistent development and production environments.")
    if score < 60:
        improvements.append("Refactor overly large files — consider splitting god-modules into smaller, focused units.")
    if not improvements:
        improvements.append("Good overall structure. Consider running a security dependency audit (e.g., Dependabot).")
        improvements.append("Add end-to-end tests to cover critical user flows.")

    return {
        "project_summary": project_summary,
        "purpose": purpose,
        "code_quality_score": score,
        "tech_stack": tech_stack,
        "complexity": complexity,
        "suggested_improvements": improvements[:5],
        "ai_generated": False,
    }


def generate_function_descriptions(functions: List[Dict], file_path: str, language: str, hf_token: str) -> List[Dict]:
    """
    Use AI to generate descriptions for functions that don't have docstrings.
    Returns the functions list with added 'description' fields.
    """
    if not functions:
        return functions
    
    # Only process functions without descriptions
    functions_to_describe = [f for f in functions if isinstance(f, dict) and not f.get('description', '').strip()]
    
    # Deprecated: This function is now handled by semantic_inference.py
    # which provides more reliable rule-based descriptions without AI
    return functions
