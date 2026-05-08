"""
Graph Builder
Generates architecture diagrams using Graphviz:
  - Module dependency graph
  - API route flow graph
  - Frontend component relationship graph
Also maintains adjacency lists in JSON.
"""

import os
import re
import tempfile
from typing import Optional

import graphviz


def build_module_dependency_graph(source_analysis: list[dict]) -> tuple[Optional[str], dict]:
    """
    Build a module dependency graph from import analysis.
    Returns (path_to_png, adjacency_list).
    """
    adjacency = {}
    nodes = set()
    edges = []

    # Build a map of module names from file paths
    module_names = {}
    for analysis in source_analysis:
        fp = analysis["file_path"]
        # Convert path to module-like name
        module = _path_to_module(fp)
        module_names[module] = fp
        nodes.add(module)

    # Build edges from imports
    for analysis in source_analysis:
        fp = analysis["file_path"]
        source_module = _path_to_module(fp)
        adjacency[source_module] = []

        for imp in analysis.get("imports", []):
            imp_base = imp.split(".")[0] if "." in imp else imp
            imp_base = imp_base.replace("/", ".").replace("\\", ".")

            # Check if it's an internal module
            for mod_name in module_names:
                mod_base = mod_name.split(".")[-1] if "." in mod_name else mod_name
                if imp_base == mod_base or imp_base in mod_name:
                    if mod_name != source_module:
                        edges.append((source_module, mod_name))
                        adjacency[source_module].append(mod_name)
                    break

    if not nodes:
        return None, {}

    # Build graphviz diagram
    dot = graphviz.Digraph(
        "Module Dependencies",
        format="png",
        graph_attr={
            "rankdir": "LR",
            "bgcolor": "#0e1117",
            "fontcolor": "#fafafa",
            "pad": "0.5",
            "dpi": "150",
        },
        node_attr={
            "style": "filled",
            "fillcolor": "#262730",
            "fontcolor": "#fafafa",
            "color": "#4e8cff",
            "fontsize": "10",
            "shape": "box",
            "fontname": "Helvetica",
        },
        edge_attr={
            "color": "#4e8cff",
            "fontcolor": "#fafafa",
            "fontsize": "8",
        },
    )

    # Limit to manageable size
    display_nodes = list(nodes)[:40]
    for node in display_nodes:
        label = _shorten_label(node)
        dot.node(node, label=label)

    seen_edges = set()
    for src, dst in edges:
        if src in display_nodes and dst in display_nodes:
            key = (src, dst)
            if key not in seen_edges:
                seen_edges.add(key)
                dot.edge(src, dst)

    png_path = _render_graph(dot, "module_dependencies")
    return png_path, adjacency


def build_route_flow_graph(source_analysis: list[dict]) -> tuple[Optional[str], dict]:
    """
    Build API route flow graph.
    Returns (path_to_png, adjacency_list).
    """
    routes = []
    for analysis in source_analysis:
        for route in analysis.get("routes", []):
            routes.append({
                "file": _path_to_module(analysis["file_path"]),
                **route,
            })

    if not routes:
        return None, {}

    adjacency = {"API_Gateway": []}

    dot = graphviz.Digraph(
        "API Routes",
        format="png",
        graph_attr={
            "rankdir": "TB",
            "bgcolor": "#0e1117",
            "fontcolor": "#fafafa",
            "pad": "0.5",
            "dpi": "150",
        },
        node_attr={
            "style": "filled",
            "fontcolor": "#fafafa",
            "fontsize": "10",
            "fontname": "Helvetica",
        },
        edge_attr={
            "color": "#4e8cff",
            "fontcolor": "#fafafa",
            "fontsize": "8",
        },
    )

    # API Gateway node
    dot.node("API_Gateway", label="API Gateway", shape="ellipse",
             fillcolor="#1a5276", color="#4e8cff")

    method_colors = {
        "GET": "#27ae60",
        "POST": "#e67e22",
        "PUT": "#2980b9",
        "DELETE": "#c0392b",
        "PATCH": "#8e44ad",
        "USE": "#7f8c8d",
        "ALL": "#95a5a6",
    }

    for i, route in enumerate(routes[:30]):  # Limit display
        method = route.get("method", "")
        path = route.get("path", route.get("decorator", ""))
        func = route.get("function", "")
        file_mod = route.get("file", "")

        node_id = f"route_{i}"
        label = f"{method} {path}" if method else path
        color = method_colors.get(method, "#4e8cff")

        dot.node(node_id, label=label, shape="box",
                 fillcolor="#262730", color=color)

        if func:
            handler_id = f"handler_{i}"
            dot.node(handler_id, label=f"{func}()\n{file_mod}",
                     shape="component", fillcolor="#1c2833", color="#5dade2")
            dot.edge(node_id, handler_id)

        dot.edge("API_Gateway", node_id, color=color)
        adjacency["API_Gateway"].append(label)

    png_path = _render_graph(dot, "api_routes")
    return png_path, adjacency


def build_component_graph(source_analysis: list[dict]) -> tuple[Optional[str], dict]:
    """
    Build frontend component relationship graph (for React/TSX/JSX).
    Returns (path_to_png, adjacency_list).
    """
    components = {}
    adjacency = {}

    for analysis in source_analysis:
        for comp in analysis.get("components", []):
            file_mod = _path_to_module(analysis["file_path"])
            components[comp] = {
                "file": file_mod,
                "hooks": analysis.get("react_hooks", []),
                "imports": analysis.get("imports", []),
            }
            adjacency[comp] = []

    if not components:
        return None, {}

    # Detect component relationships via imports
    comp_names = set(components.keys())
    for comp_name, comp_data in components.items():
        for imp in comp_data["imports"]:
            imp_base = imp.rsplit("/", 1)[-1] if "/" in imp else imp
            for other_comp in comp_names:
                if other_comp != comp_name and other_comp.lower() == imp_base.lower():
                    adjacency[comp_name].append(other_comp)

    dot = graphviz.Digraph(
        "React Components",
        format="png",
        graph_attr={
            "rankdir": "TB",
            "bgcolor": "#0e1117",
            "fontcolor": "#fafafa",
            "pad": "0.5",
            "dpi": "150",
        },
        node_attr={
            "style": "filled",
            "fillcolor": "#262730",
            "fontcolor": "#fafafa",
            "color": "#61dafb",  # React blue
            "fontsize": "10",
            "shape": "component",
            "fontname": "Helvetica",
        },
        edge_attr={
            "color": "#61dafb",
            "fontcolor": "#fafafa",
            "fontsize": "8",
        },
    )

    display_comps = list(components.keys())[:30]
    for comp_name in display_comps:
        comp = components[comp_name]
        hooks_str = ", ".join(comp["hooks"][:3])
        label = f"<{comp_name}/>"
        if hooks_str:
            label += f"\n[{hooks_str}]"
        dot.node(comp_name, label=label)

    seen_edges = set()
    for comp_name in display_comps:
        for child in adjacency.get(comp_name, []):
            if child in display_comps:
                key = (comp_name, child)
                if key not in seen_edges:
                    seen_edges.add(key)
                    dot.edge(comp_name, child)

    png_path = _render_graph(dot, "component_graph")
    return png_path, adjacency


def build_all_graphs(source_analysis: list[dict]) -> dict:
    """
    Build all architecture graphs and return paths and adjacency data.
    """
    result = {
        "module_dependency": {"png": None, "adjacency": {}},
        "api_routes": {"png": None, "adjacency": {}},
        "component_graph": {"png": None, "adjacency": {}},
    }

    try:
        png, adj = build_module_dependency_graph(source_analysis)
        result["module_dependency"] = {"png": png, "adjacency": adj}
    except Exception:
        pass

    try:
        png, adj = build_route_flow_graph(source_analysis)
        result["api_routes"] = {"png": png, "adjacency": adj}
    except Exception:
        pass

    try:
        png, adj = build_component_graph(source_analysis)
        result["component_graph"] = {"png": png, "adjacency": adj}
    except Exception:
        pass

    return result


# ──────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────

def _path_to_module(path: str) -> str:
    """Convert file path to a module-style name."""
    name = path.replace("/", ".").replace("\\", ".")
    # Remove extension
    for ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".cs", ".php", ".cpp"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    return name


def _shorten_label(name: str, max_len: int = 25) -> str:
    """Shorten a label for graph display."""
    if len(name) <= max_len:
        return name
    parts = name.split(".")
    if len(parts) > 2:
        return f"...{'.'.join(parts[-2:])}"
    return name[:max_len - 3] + "..."


def _render_graph(dot: graphviz.Digraph, name: str) -> Optional[str]:
    """Render graph to a temporary PNG file."""
    try:
        tmp_dir = tempfile.mkdtemp(prefix="repo_intel_")
        filepath = os.path.join(tmp_dir, name)
        dot.render(filepath, cleanup=True)
        png_path = filepath + ".png"
        if os.path.exists(png_path):
            return png_path
    except Exception:
        # Graphviz binary may not be installed
        pass
    return None
