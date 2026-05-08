"""
Configuration File Parser
Extracts structured data from config files: package.json, requirements.txt, Dockerfile, etc.
"""

import json
import re
from typing import Optional


FRONTEND_FRAMEWORK_MARKERS = {
    "react": "React",
    "react-dom": "React",
    "next": "Next.js",
    "vue": "Vue.js",
    "@angular/core": "Angular",
    "svelte": "Svelte",
    "solid-js": "SolidJS",
    "preact": "Preact",
    "gatsby": "Gatsby",
    "nuxt": "Nuxt.js",
    "@remix-run/react": "Remix",
}

BACKEND_FRAMEWORK_MARKERS = {
    "express": "Express.js",
    "fastify": "Fastify",
    "@nestjs/core": "NestJS",
    "koa": "Koa",
    "hapi": "Hapi",
    "restify": "Restify",
    "socket.io": "Socket.IO",
    "apollo-server": "Apollo GraphQL",
    "@apollo/server": "Apollo GraphQL",
}


def parse_package_json(content: str) -> Optional[dict]:
    """Parse package.json and extract dependencies, scripts, frameworks."""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None

    dependencies = data.get("dependencies", {})
    dev_dependencies = data.get("devDependencies", {})
    scripts = data.get("scripts", {})

    all_deps = {**dependencies, **dev_dependencies}

    # Detect frameworks
    frontend_frameworks = []
    backend_frameworks = []

    for pkg, framework in FRONTEND_FRAMEWORK_MARKERS.items():
        if pkg in all_deps:
            frontend_frameworks.append(framework)

    for pkg, framework in BACKEND_FRAMEWORK_MARKERS.items():
        if pkg in all_deps:
            backend_frameworks.append(framework)

    return {
        "name": data.get("name", ""),
        "version": data.get("version", ""),
        "description": data.get("description", ""),
        "dependencies": list(dependencies.keys()),
        "dev_dependencies": list(dev_dependencies.keys()),
        "scripts": scripts,
        "frontend_frameworks": list(set(frontend_frameworks)),
        "backend_frameworks": list(set(backend_frameworks)),
        "has_typescript": "typescript" in all_deps,
        "has_testing": any(
            pkg in all_deps
            for pkg in ("jest", "mocha", "vitest", "cypress", "@testing-library/react", "playwright")
        ),
    }


def parse_requirements_txt(content: str) -> Optional[dict]:
    """Parse requirements.txt and extract Python libraries."""
    libraries = []
    for line in content.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle version specifiers
        pkg = re.split(r'[><=!~\[]', line)[0].strip()
        if pkg:
            libraries.append(pkg)

    # Detect Python frameworks
    framework_markers = {
        "django": "Django",
        "flask": "Flask",
        "fastapi": "FastAPI",
        "tornado": "Tornado",
        "sanic": "Sanic",
        "starlette": "Starlette",
        "aiohttp": "aiohttp",
        "bottle": "Bottle",
        "pyramid": "Pyramid",
        "celery": "Celery",
        "streamlit": "Streamlit",
    }

    detected_frameworks = []
    lib_lower = {lib.lower() for lib in libraries}
    for marker, name in framework_markers.items():
        if marker in lib_lower:
            detected_frameworks.append(name)

    return {
        "libraries": libraries,
        "frameworks": detected_frameworks,
        "count": len(libraries),
    }


def parse_dockerfile(content: str) -> Optional[dict]:
    """Parse Dockerfile and extract base image, ports, CMD."""
    result = {
        "base_images": [],
        "exposed_ports": [],
        "cmd": None,
        "entrypoint": None,
        "env_vars": [],
        "stages": 0,
    }

    for line in content.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        upper = line.upper()

        # FROM
        if upper.startswith("FROM "):
            image = line[5:].strip().split(" AS ")[0].split(" as ")[0].strip()
            result["base_images"].append(image)
            result["stages"] += 1

        # EXPOSE
        elif upper.startswith("EXPOSE "):
            ports = re.findall(r'\d+', line)
            result["exposed_ports"].extend(ports)

        # CMD
        elif upper.startswith("CMD "):
            result["cmd"] = line[4:].strip()

        # ENTRYPOINT
        elif upper.startswith("ENTRYPOINT "):
            result["entrypoint"] = line[11:].strip()

        # ENV
        elif upper.startswith("ENV "):
            parts = line[4:].strip().split("=", 1)
            if len(parts) == 2:
                result["env_vars"].append(parts[0].strip())
            else:
                parts2 = line[4:].strip().split(None, 1)
                if parts2:
                    result["env_vars"].append(parts2[0])

    result["is_multistage"] = result["stages"] > 1
    return result


def parse_docker_compose(content: str) -> Optional[dict]:
    """Parse docker-compose.yml for service information."""
    result = {
        "services": [],
        "has_volumes": False,
        "has_networks": False,
    }

    # Simple YAML parsing without external dependency
    current_service = None
    indent_level = 0

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        leading_spaces = len(line) - len(line.lstrip())

        if stripped.startswith("services:"):
            indent_level = leading_spaces
            continue

        if stripped.startswith("volumes:") and leading_spaces == 0:
            result["has_volumes"] = True
            continue

        if stripped.startswith("networks:") and leading_spaces == 0:
            result["has_networks"] = True
            continue

        # Service names are at indent level + 2
        if leading_spaces == indent_level + 2 and stripped.endswith(":"):
            current_service = stripped[:-1].strip()
            result["services"].append(current_service)

    return result


def parse_pyproject_toml(content: str) -> Optional[dict]:
    """Basic pyproject.toml parsing for project metadata."""
    result = {
        "name": "",
        "dependencies": [],
        "build_system": "",
    }

    # Extract project name
    name_match = re.search(r'name\s*=\s*"([^"]+)"', content)
    if name_match:
        result["name"] = name_match.group(1)

    # Extract dependencies list
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies") and "=" in stripped:
            in_deps = True
            continue
        if in_deps:
            if stripped.startswith("]"):
                in_deps = False
                continue
            pkg = stripped.strip('", ')
            if pkg and not pkg.startswith("#"):
                clean_pkg = re.split(r'[><=!~\[]', pkg)[0].strip()
                if clean_pkg:
                    result["dependencies"].append(clean_pkg)

    # Build system
    build_match = re.search(r'requires\s*=\s*\[([^\]]+)\]', content)
    if build_match:
        result["build_system"] = build_match.group(1).strip()

    return result


def parse_all_configs(files: list[dict]) -> dict:
    """
    Parse all configuration files and return structured data.
    """
    result = {
        "package_json": None,
        "requirements_txt": None,
        "dockerfile": None,
        "docker_compose": None,
        "pyproject_toml": None,
        "other_configs": [],
        "frontend_dependencies": [],
        "backend_dependencies": [],
        "frontend_frameworks": [],
        "backend_frameworks": [],
        "docker_used": False,
    }

    for f in files:
        filename = f["path"].rsplit("/", 1)[-1].lower()
        content = f.get("content")
        if not content:
            continue

        if filename == "package.json" and result["package_json"] is None:
            parsed = parse_package_json(content)
            if parsed:
                result["package_json"] = parsed
                result["frontend_dependencies"] = parsed["dependencies"]
                result["frontend_frameworks"].extend(parsed["frontend_frameworks"])
                result["backend_frameworks"].extend(parsed["backend_frameworks"])

        elif filename == "requirements.txt" and result["requirements_txt"] is None:
            parsed = parse_requirements_txt(content)
            if parsed:
                result["requirements_txt"] = parsed
                result["backend_dependencies"] = parsed["libraries"]
                result["backend_frameworks"].extend(parsed["frameworks"])

        elif filename == "dockerfile":
            parsed = parse_dockerfile(content)
            if parsed:
                result["dockerfile"] = parsed
                result["docker_used"] = True

        elif filename in ("docker-compose.yml", "docker-compose.yaml"):
            parsed = parse_docker_compose(content)
            if parsed:
                result["docker_compose"] = parsed
                result["docker_used"] = True

        elif filename == "pyproject.toml":
            parsed = parse_pyproject_toml(content)
            if parsed:
                result["pyproject_toml"] = parsed

        else:
            result["other_configs"].append(filename)

    result["frontend_frameworks"] = list(set(result["frontend_frameworks"]))
    result["backend_frameworks"] = list(set(result["backend_frameworks"]))

    return result
