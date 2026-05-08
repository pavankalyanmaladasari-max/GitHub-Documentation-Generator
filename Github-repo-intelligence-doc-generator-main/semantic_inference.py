"""
Semantic Inference Engine
Generates intelligent function and component descriptions using rule-based heuristics
and local pre-trained models when available.
Works offline using static code analysis patterns and transformers library.
"""

import re
from typing import Dict, List

try:
    from local_inference import generate_function_description as gen_func_desc
    HAS_LOCAL_inference = True
except ImportError:
    HAS_LOCAL_inference = False


def generate_description(file_analysis: dict) -> str:
    """
    Generate a semantic description for a file based on its analysis.
    Uses rule-based heuristics to understand what the file does.
    """
    file_path = file_analysis.get("file_path", "")
    language = file_analysis.get("language", "")
    components = file_analysis.get("components", [])
    functions = file_analysis.get("functions", [])
    imports = file_analysis.get("imports", [])
    hooks = file_analysis.get("react_hooks", [])
    routes = file_analysis.get("routes", [])
    
    descriptions = []
    
    # React Component Analysis
    if components and len(components) > 0:
        comp_name = components[0]
        desc = f"This React functional component named '{comp_name}' is responsible for rendering UI for the related feature."
        
        # Check for state management
        if "useState" in hooks:
            desc += " It uses React Hooks for state management."
        
        # Check for lifecycle effects
        if "useEffect" in hooks:
            desc += " It uses lifecycle side effects through useEffect."
        
        # Check for API calls
        if any(imp in str(imports).lower() for imp in ["axios", "fetch"]):
            desc += " It interacts with backend APIs using HTTP requests."
        
        # Check for data rendering patterns
        if "map" in str(functions + components).lower():
            desc += " It dynamically renders UI elements using array mapping."
        
        descriptions.append(desc)
    
    # Backend Function Analysis (Node.js/TypeScript)
    elif language in ["JavaScript", "TypeScript"] and functions:
        func_descriptions = []
        
        for func in functions[:3]:  # Analyze first 3 functions
            func_name = func.get("name", "") if isinstance(func, dict) else func
            
            # Check for async patterns
            if isinstance(func, dict) and func.get("is_async"):
                func_desc = f"This asynchronous backend function '{func_name}' likely handles business logic or request processing."
            else:
                func_desc = f"This backend function '{func_name}' handles specific application logic."
            
            func_descriptions.append(func_desc)
        
        if func_descriptions:
            descriptions.append(" ".join(func_descriptions[:2]))  # Limit to 2 descriptions
        
        # Check for Express routes
        if routes and len(routes) > 0:
            route_methods = list(set([r.get("method", "").upper() for r in routes[:3]]))
            if route_methods:
                descriptions.append(f"This file defines API endpoints using Express routing with {', '.join(route_methods)} methods.")
    
    # Python Function Analysis
    elif language == "Python" and functions:
        func_descriptions = []
        
        for func in functions[:3]:
            func_name = func.get("name", "") if isinstance(func, dict) else func
            decorators = func.get("decorators", []) if isinstance(func, dict) else []
            
            func_desc = f"This Python function '{func_name}' performs backend data processing logic."
            
            # Check for API decorators
            if any(dec in str(decorators) for dec in ["route", "get", "post", "put", "delete"]):
                func_desc += " It is exposed as an API endpoint."
            
            func_descriptions.append(func_desc)
        
        if func_descriptions:
            descriptions.append(" ".join(func_descriptions[:2]))
        
        # Check for route definitions
        if routes and len(routes) > 0:
            descriptions.append(f"This module defines {len(routes)} API route(s) for handling HTTP requests.")
    
    # Generic file description based on type
    if not descriptions:
        if language in ["JavaScript", "TypeScript"]:
            descriptions.append(f"This {language} module contains utility functions and helper methods.")
        elif language == "Python":
            descriptions.append(f"This Python module provides core functionality for the application.")
        else:
            descriptions.append(f"This {language} file contains application logic.")
    
    return " ".join(descriptions)


def enhance_function_descriptions(
    functions: List[Dict],
    file_path: str,
    language: str,
    file_content: str = "",
    max_model_calls: int | None = None,
) -> List[Dict]:
    """
    Enhance function objects with semantic descriptions using local inference or heuristics.
    Uses Flan-T5 model when available, falls back to pattern matching.
    """
    del file_path, file_content, max_model_calls

    if not functions:
        return functions
    
    for func in functions:
        if not isinstance(func, dict):
            continue
        
        func_name = func.get("name", "")
        
        # Skip if already has description
        if func.get("description", "").strip():
            continue
        
        # Try local model first if available
        description = None
        if HAS_LOCAL_inference:
            try:
                # Prepare function info for the model
                func_info = {
                    "name": func_name,
                    "params": func.get("params", {}),
                    "returns": func.get("returns", ""),
                    "docstring": func.get("docstring", ""),
                    "language": language,
                }
                description = gen_func_desc(func_info)
            except Exception as e:
                print(f"Local inference error: {e}, falling back to heuristics")
        
        # Fall back to heuristic analysis
        if not description:
            description = _infer_function_purpose(func_name, language, func.get("decorators", []))
        
        if description:
            func["description"] = description
    
    return functions


def _infer_function_purpose(func_name: str, language: str, decorators: List[str]) -> str:
    """
    Infer what a function does based on its name and context.
    Uses common naming conventions and patterns.
    """
    name_lower = func_name.lower()
    
    # React Hooks
    if func_name.startswith("use") and language in ["JavaScript", "TypeScript"]:
        return f"Custom React hook for managing {func_name[3:]} state or behavior"
    
    # CRUD Operations
    if name_lower.startswith("get") or name_lower.startswith("fetch"):
        return f"Retrieves or fetches data"
    
    if name_lower.startswith("create") or name_lower.startswith("add"):
        return f"Creates or adds new data"
    
    if name_lower.startswith("update") or name_lower.startswith("edit"):
        return f"Updates or modifies existing data"
    
    if name_lower.startswith("delete") or name_lower.startswith("remove"):
        return f"Deletes or removes data"
    
    # Handler patterns
    if name_lower.startswith("handle"):
        event = func_name[6:]  # Remove "handle" prefix
        return f"Handles {event} event or action"
    
    if name_lower.startswith("on"):
        event = func_name[2:]  # Remove "on" prefix
        return f"Event handler for {event}"
    
    # Validation and processing
    if "validate" in name_lower:
        return f"Validates data or input"
    
    if "process" in name_lower or "parse" in name_lower:
        return f"Processes or transforms data"
    
    if "render" in name_lower:
        return f"Renders UI component or view"
    
    if "init" in name_lower or "setup" in name_lower:
        return f"Initializes or sets up the application or module"
    
    # Authentication/Authorization
    if "login" in name_lower or "auth" in name_lower:
        return f"Handles authentication or authorization"
    
    if "logout" in name_lower:
        return f"Handles user logout"
    
    # API/Network
    if "api" in name_lower or "request" in name_lower:
        return f"Makes API request or handles network communication"
    
    # Database
    if "save" in name_lower or "store" in name_lower:
        return f"Saves or stores data"
    
    if "load" in name_lower:
        return f"Loads data from storage"
    
    # Format/Transform
    if "format" in name_lower or "transform" in name_lower:
        return f"Formats or transforms data"
    
    if "convert" in name_lower:
        return f"Converts data from one format to another"
    
    # Calculation/Computation
    if "calculate" in name_lower or "compute" in name_lower:
        return f"Performs calculations or computations"
    
    # Search/Filter
    if "search" in name_lower or "find" in name_lower:
        return f"Searches or finds specific data"
    
    if "filter" in name_lower:
        return f"Filters data based on criteria"
    
    # Route decorators
    if decorators:
        route_decorators = [d for d in decorators if any(x in d.lower() for x in ["route", "get", "post", "put", "delete", "patch"])]
        if route_decorators:
            return f"API endpoint handler function"
    
    # Generic based on language
    if language in ["JavaScript", "TypeScript"]:
        return f"JavaScript/TypeScript utility function"
    elif language == "Python":
        return f"Python helper function"
    
    return ""


def analyze_code_patterns(file_content: str, language: str) -> Dict[str, bool]:
    """
    Detect common code patterns in the file content.
    Returns a dictionary of detected patterns.
    """
    patterns = {
        "has_async": False,
        "has_api_calls": False,
        "has_state_management": False,
        "has_routing": False,
        "has_database": False,
        "has_validation": False,
    }
    
    if not file_content:
        return patterns
    
    content_lower = file_content.lower()
    
    # Async patterns
    if "async" in content_lower or "await" in content_lower:
        patterns["has_async"] = True
    
    # API calls
    if any(x in content_lower for x in ["axios", "fetch(", "http.get", "http.post", "requests.get", "requests.post"]):
        patterns["has_api_calls"] = True
    
    # State management
    if any(x in content_lower for x in ["usestate", "setstate", "redux", "vuex", "mobx"]):
        patterns["has_state_management"] = True
    
    # Routing
    if any(x in content_lower for x in ["router", "route", "@app.route", "express()"]):
        patterns["has_routing"] = True
    
    # Database
    if any(x in content_lower for x in ["mongoose", "sequelize", "prisma", "sqlalchemy", "query", "database"]):
        patterns["has_database"] = True
    
    # Validation
    if any(x in content_lower for x in ["validate", "yup", "joi", "validator", "schema"]):
        patterns["has_validation"] = True
    
    return patterns
