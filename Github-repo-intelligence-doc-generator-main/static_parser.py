"""
Static Code Parser
Extracts structural information from source code files using AST and regex parsing.
"""

import ast
import re
from typing import Optional


# ──────────────────────────────────────────────
# Python Parser (AST-based)
# ──────────────────────────────────────────────

def parse_python(content: str, file_path: str) -> dict:
    """Parse Python source file using the ast module."""
    result = {
        "file_path": file_path,
        "language": "Python",
        "classes": [],
        "functions": [],
        "components": [],
        "imports": [],
        "routes": [],
        "decorators": [],
    }

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        # Classes
        if isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(ast.dump(base))
            decorators = []
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name):
                    decorators.append(dec.id)
                elif isinstance(dec, ast.Attribute):
                    decorators.append(ast.dump(dec))
                elif isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Name):
                        decorators.append(dec.func.id)
                    elif isinstance(dec.func, ast.Attribute):
                        decorators.append(ast.dump(dec.func))

            result["classes"].append({
                "name": node.name,
                "bases": bases,
                "decorators": decorators,
                "line": node.lineno,
            })

        # Functions (top-level and methods)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            decorators = []
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name):
                    decorators.append(dec.id)
                elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec, ast.Attribute):
                    dec_str = _get_decorator_string(dec)
                    decorators.append(dec_str)
                elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    dec_str = _get_decorator_string(dec.func)
                    decorators.append(dec_str)

            # Extract docstring
            docstring = ast.get_docstring(node)
            if docstring:
                # Get first line of docstring as description
                docstring = docstring.strip().split('\n')[0][:200]
            
            result["functions"].append({
                "name": node.name,
                "decorators": decorators,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "line": node.lineno,
                "description": docstring or "",
            })
            result["decorators"].extend(decorators)

            # Detect Flask/FastAPI routes
            for dec_str in decorators:
                if any(method in dec_str.lower() for method in
                       (".get", ".post", ".put", ".delete", ".patch", ".route")):
                    result["routes"].append({
                        "function": node.name,
                        "decorator": dec_str,
                        "line": node.lineno,
                    })

        # Imports
        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                result["imports"].append(f"{module}.{alias.name}")

    result["decorators"] = list(set(result["decorators"]))
    return result


def _get_decorator_string(node) -> str:
    """Recursively build decorator string from AST Attribute node."""
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


# ──────────────────────────────────────────────
# JavaScript / TypeScript Parser (Regex-based)
# ──────────────────────────────────────────────

def parse_javascript(content: str, file_path: str) -> dict:
    """Parse JavaScript/TypeScript files using structured regex."""
    lang = "TypeScript" if file_path.endswith((".ts", ".tsx")) else "JavaScript"
    result = {
        "file_path": file_path,
        "language": lang,
        "classes": [],
        "functions": [],
        "components": [],
        "imports": [],
        "routes": [],
        "exports": [],
    }

    # Import statements
    import_patterns = [
        r'import\s+(?:{[^}]+}|\*\s+as\s+\w+|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
        r'import\s+[\'"]([^\'"]+)[\'"]',
        r'const\s+\w+\s*=\s*require\([\'"]([^\'"]+)[\'"]\)',
        r'import\s+(\w+)\s*,?\s*(?:{[^}]+})?\s*from\s+[\'"]([^\'"]+)[\'"]',
    ]
    for pattern in import_patterns:
        for match in re.finditer(pattern, content):
            result["imports"].append(match.group(match.lastindex))
    result["imports"] = list(set(result["imports"]))

    # Function declarations with JSDoc/comments
    func_patterns = [
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(',
        r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
        r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?function',
        r'(?:export\s+)?(?:async\s+)?function\*?\s+(\w+)',
    ]
    
    # Extract JSDoc comments (/** ... */)
    jsdoc_pattern = r'/\*\*\s*\n?\s*\*?\s*([^\n*]+)'
    jsdoc_map = {}
    for match in re.finditer(jsdoc_pattern, content):
        desc = match.group(1).strip()
        # Find the next function after this comment
        next_func_match = re.search(r'(?:function|const)\s+(\w+)', content[match.end():match.end()+200])
        if next_func_match:
            jsdoc_map[next_func_match.group(1)] = desc
    
    seen_functions = set()
    for pattern in func_patterns:
        for match in re.finditer(pattern, content):
            name = match.group(1)
            if name not in seen_functions:
                seen_functions.add(name)
                result["functions"].append({
                    "name": name,
                    "description": jsdoc_map.get(name, "")
                })

    # Class declarations
    class_pattern = r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?'
    for match in re.finditer(class_pattern, content):
        entry = {"name": match.group(1)}
        if match.group(2):
            entry["extends"] = match.group(2)
        result["classes"].append(entry)

    # Export statements
    export_patterns = [
        r'export\s+default\s+(?:class|function|const)?\s*(\w+)',
        r'export\s+(?:const|let|var|function|class|async\s+function)\s+(\w+)',
        r'module\.exports\s*=\s*(\w+)',
    ]
    for pattern in export_patterns:
        for match in re.finditer(pattern, content):
            result["exports"].append(match.group(1))
    result["exports"] = list(set(result["exports"]))

    # Express / Fastify routes
    route_pattern = r'(?:app|router|server)\.(get|post|put|delete|patch|use|all)\s*\(\s*[\'"]([^\'"]+)[\'"]'
    for match in re.finditer(route_pattern, content):
        result["routes"].append({
            "method": match.group(1).upper(),
            "path": match.group(2),
        })

    return result


# ──────────────────────────────────────────────
# TSX / JSX Parser (React Component Detection)
# ──────────────────────────────────────────────

def parse_react(content: str, file_path: str) -> dict:
    """Parse TSX/JSX files for React component detection."""
    base = parse_javascript(content, file_path)

    components = []

    # Function component: function ComponentName()
    func_comp = re.finditer(
        r'(?:export\s+(?:default\s+)?)?function\s+([A-Z]\w+)\s*\(', content
    )
    for match in func_comp:
        components.append(match.group(1))

    # Arrow function component: const ComponentName = () =>
    arrow_comp = re.finditer(
        r'(?:export\s+(?:default\s+)?)?const\s+([A-Z]\w+)\s*=\s*(?:\([^)]*\)|[^=])\s*=>', content
    )
    for match in arrow_comp:
        components.append(match.group(1))

    # React.forwardRef / React.memo
    hoc_comp = re.finditer(
        r'(?:export\s+(?:default\s+)?)?const\s+([A-Z]\w+)\s*=\s*(?:React\.)?(?:forwardRef|memo)\s*\(', content
    )
    for match in hoc_comp:
        components.append(match.group(1))

    base["components"] = list(set(components))

    # Detect hooks
    hooks_pattern = r'\b(use[A-Z]\w+)\s*\('
    hooks = list(set(re.findall(hooks_pattern, content)))
    base["hooks"] = hooks

    # Detect imported libraries specifically
    imported_hooks = [h for h in hooks if h in {
        "useState", "useEffect", "useContext", "useReducer",
        "useCallback", "useMemo", "useRef", "useLayoutEffect",
        "useImperativeHandle", "useDebugValue", "useId",
        "useTransition", "useDeferredValue", "useSyncExternalStore",
    }]
    base["react_hooks"] = imported_hooks

    return base


# ──────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────

def parse_source_file(file_path: str, content: Optional[str]) -> Optional[dict]:
    """
    Route file to appropriate parser based on extension.
    Returns parsed analysis dict or None if not parseable.
    """
    if content is None:
        return None

    if file_path.endswith(".py"):
        return parse_python(content, file_path)
    elif file_path.endswith((".tsx", ".jsx")):
        return parse_react(content, file_path)
    elif file_path.endswith((".js", ".ts")):
        return parse_javascript(content, file_path)
    elif file_path.endswith((".java", ".cpp", ".go", ".cs", ".php")):
        return _parse_generic(content, file_path)

    return None


def _parse_generic(content: str, file_path: str) -> dict:
    """Basic regex parsing for Java, C++, Go, C#, PHP."""
    ext = file_path.rsplit(".", 1)[-1].lower()
    lang_map = {
        "java": "Java", "cpp": "C++", "go": "Go",
        "cs": "C#", "php": "PHP",
    }
    language = lang_map.get(ext, ext.upper())

    result = {
        "file_path": file_path,
        "language": language,
        "classes": [],
        "functions": [],
        "components": [],
        "imports": [],
        "routes": [],
    }

    # Generic class detection
    class_pattern = r'(?:public\s+)?class\s+(\w+)'
    for match in re.finditer(class_pattern, content):
        result["classes"].append({"name": match.group(1)})

    # Generic function/method detection
    if ext == "go":
        func_pattern = r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\('
    elif ext == "java" or ext == "cs":
        func_pattern = r'(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\('
    elif ext == "php":
        func_pattern = r'(?:public|private|protected|static)?\s*function\s+(\w+)\s*\('
    else:
        func_pattern = r'(?:\w+\s+)+(\w+)\s*\('

    seen = set()
    for match in re.finditer(func_pattern, content):
        name = match.group(1)
        if name not in seen and name not in {"if", "for", "while", "switch", "catch", "return"}:
            seen.add(name)
            result["functions"].append({"name": name})

    # Generic import detection
    if ext == "java":
        for match in re.finditer(r'import\s+([\w.]+);', content):
            result["imports"].append(match.group(1))
    elif ext == "go":
        for match in re.finditer(r'"([\w./\-]+)"', content):
            result["imports"].append(match.group(1))
    elif ext == "cs":
        for match in re.finditer(r'using\s+([\w.]+);', content):
            result["imports"].append(match.group(1))
    elif ext == "php":
        for match in re.finditer(r'use\s+([\w\\]+);', content):
            result["imports"].append(match.group(1))

    return result


def analyze_all_sources(files: list[dict]) -> list[dict]:
    """
    Parse all source files and return list of analysis results.
    """
    results = []
    source_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".go", ".cs", ".php"}

    for f in files:
        ext = ""
        if "." in f["path"].rsplit("/", 1)[-1]:
            ext = "." + f["path"].rsplit(".", 1)[-1].lower()

        if ext in source_extensions and f.get("content"):
            parsed = parse_source_file(f["path"], f["content"])
            if parsed:
                results.append(parsed)

    return results
