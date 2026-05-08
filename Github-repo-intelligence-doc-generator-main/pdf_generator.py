"""
Advanced PDF Report Generator
Generates comprehensive, well-structured PDF reports with detailed code analysis.
"""

import io
from datetime import datetime
from typing import Dict, List, Any, Optional

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, 
    Table, TableStyle, KeepTogether, Image, Flowable
)
from reportlab.lib import colors


# ──────────────────────────────────────────────
# Custom Styles
# ──────────────────────────────────────────────

def create_custom_styles():
    """Create custom paragraph styles for the PDF."""
    styles = getSampleStyleSheet()
    
    # Cover page title
    styles.add(ParagraphStyle(
        name='CoverTitle',
        parent=styles['Title'],
        fontSize=32,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))
    
    # Cover subtitle
    styles.add(ParagraphStyle(
        name='CoverSubtitle',
        parent=styles['Normal'],
        fontSize=18,
        textColor=colors.HexColor('#4e8cff'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica'
    ))
    
    # Section headers
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=16,
        spaceBefore=20,
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderColor=colors.HexColor('#4e8cff'),
        borderPadding=8,
        backColor=colors.HexColor('#f0f5ff')
    ))
    
    # Sub-section headers
    styles.add(ParagraphStyle(
        name='SubHeader',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=10,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    ))
    
    # File path style
    styles.add(ParagraphStyle(
        name='FilePath',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#2980b9'),
        fontName='Courier-Bold',
        backColor=colors.HexColor('#ecf0f1'),
        borderPadding=4,
        spaceAfter=6
    ))
    
    # Code style
    styles.add(ParagraphStyle(
        name='CodeBlock',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Courier',
        textColor=colors.HexColor('#2c3e50'),
        backColor=colors.HexColor('#f8f9fa'),
        leftIndent=20,
        rightIndent=20,
        spaceAfter=4
    ))
    
    # Description style
    styles.add(ParagraphStyle(
        name='Description',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#555555'),
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        leftIndent=10
    ))
    
    # Metadata style
    styles.add(ParagraphStyle(
        name='Metadata',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=4
    ))
    
    # List item style
    styles.add(ParagraphStyle(
        name='ListItem',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        bulletIndent=10,
        spaceAfter=4
    ))
    
    return styles


# ──────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────

def create_table_style():
    """Create reusable table style."""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4e8cff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ])


def sanitize_text(text: str) -> str:
    """Sanitize text for PDF (escape special characters)."""
    if not text:
        return ""
    # Replace problematic characters
    text = str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return text


def _as_dict(value: Any) -> Dict[str, Any]:
    """Normalize parsed analysis values so PDF rendering can safely access keys."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return {"name": value}
    return {}


# ──────────────────────────────────────────────
# Section Generators
# ──────────────────────────────────────────────

def add_cover_page(story: List, results: Dict, styles: Dict):
    """Add cover page to the report."""
    meta = results["master_json"]["project_metadata"]
    
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("📊 REPOSITORY INTELLIGENCE REPORT", styles['CoverTitle']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph(f"{meta['owner']}/{meta['repo']}", styles['CoverSubtitle']))
    story.append(Spacer(1, 0.5*inch))
    
    # Info box
    info_data = [
        ["Primary Language", sanitize_text(meta['primary_language'])],
        ["Project Type", sanitize_text(meta['project_type'])],
        ["Total Files", str(meta['total_files'])],
        ["Generated", datetime.now().strftime('%B %d, %Y at %H:%M:%S')],
    ]
    
    t = Table(info_data, colWidths=[2*inch, 3.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
    ]))
    story.append(t)
    
    story.append(PageBreak())


def add_table_of_contents(story: List, results: Dict, styles: Dict):
    """DEPRECATED: Table of contents removed for more compact format."""
    pass


# ──────────────────────────────────────────────
# Page-Based Section Functions (Optimized Layout)
# ──────────────────────────────────────────────


def add_executive_summary_page(story: List, results: Dict, styles: Dict):
    """Executive summary page - optimized for page layout."""
    story.append(Paragraph("1. EXECUTIVE SUMMARY", styles['SectionHeader']))
    story.append(Spacer(1, 0.1*inch))
    
    meta = results["master_json"]["project_metadata"]
    source_analysis = results.get("source_analysis", [])
    
    # Calculate statistics
    total_classes = sum(len(a.get("classes", [])) for a in source_analysis)
    total_functions = sum(len(a.get("functions", [])) for a in source_analysis)
    total_components = sum(len(a.get("components", [])) for a in source_analysis)
    total_routes = sum(len(a.get("routes", [])) for a in source_analysis)
    
    summary_text = f"""
    This repository contains a <b>{sanitize_text(meta['project_type'])}</b> project primarily written in 
    <b>{sanitize_text(meta['primary_language'])}</b>. The codebase consists of <b>{meta['total_files']}</b> total files, 
    including <b>{meta['source_files']}</b> source code files, <b>{meta['config_files']}</b> configuration files, 
    and <b>{meta['documentation_files']}</b> documentation files.
    """
    
    story.append(Paragraph(summary_text, styles['Description']))
    story.append(Spacer(1, 0.15*inch))
    
    # Key metrics table
    metrics_data = [
        ["Metric", "Count"],
        ["Total Classes", str(total_classes)],
        ["Total Functions/Methods", str(total_functions)],
        ["React Components", str(total_components)],
        ["API Routes", str(total_routes)],
        ["Frontend Detected", "Yes" if meta['frontend_detected'] else "No"],
        ["Backend Detected", "Yes" if meta['backend_detected'] else "No"],
    ]
    
    t = Table(metrics_data, colWidths=[3*inch, 2*inch])
    t.setStyle(create_table_style())
    story.append(t)
    story.append(Spacer(1, 0.2*inch))


def add_project_overview_page(story: List, results: Dict, styles: Dict):
    """Project overview page with language distribution."""
    story.append(Paragraph("2. PROJECT OVERVIEW", styles['SectionHeader']))
    story.append(Spacer(1, 0.1*inch))
    
    meta = results["master_json"]["project_metadata"]
    
    # Language breakdown
    story.append(Paragraph("2.1 Language Distribution", styles['SubHeader']))
    
    lang_breakdown = meta.get("language_breakdown", {})
    if lang_breakdown:
        lang_data = [["Language", "Files"]]
        for lang, count in sorted(lang_breakdown.items(), key=lambda x: x[1], reverse=True):
            lang_data.append([sanitize_text(lang), str(count)])
        
        t = Table(lang_data, colWidths=[3*inch, 2*inch])
        t.setStyle(create_table_style())
        story.append(t)
    else:
        story.append(Paragraph("No detailed language breakdown available.", styles['Description']))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Project type
    story.append(Paragraph("2.2 Project Type Classification", styles['SubHeader']))
    story.append(Paragraph(f"Detected Type: <b>{sanitize_text(meta['project_type'])}</b>", styles['Description']))
    story.append(Spacer(1, 0.2*inch))
    
    # File counts
    story.append(Paragraph("2.3 File Statistics", styles['SubHeader']))
    file_stats_data = [
        ["Category", "Count"],
        ["Total Files", str(meta['total_files'])],
        ["Source Files", str(meta['source_files'])],
        ["Configuration Files", str(meta['config_files'])],
        ["Documentation Files", str(meta['documentation_files'])],
        ["Test Files", str(meta.get('test_files', 0))],
    ]
    
    t = Table(file_stats_data, colWidths=[3*inch, 2*inch])
    t.setStyle(create_table_style())
    story.append(t)
    story.append(Spacer(1, 0.15*inch))


def add_dependencies_infrastructure_page(story: List, results: Dict, styles: Dict):
    """Add dependencies, frameworks, and infrastructure on one optimized page."""
    story.append(Paragraph("3. DEPENDENCIES, FRAMEWORKS & INFRASTRUCTURE", styles['SectionHeader']))
    story.append(Spacer(1, 0.1*inch))
    
    frameworks = results["master_json"].get("frameworks", {})
    deps = results["master_json"].get("dependencies", {})
    infrastructure = results["master_json"].get("infrastructure", {})
    
    # Frameworks
    story.append(Paragraph("3.1 Detected Frameworks", styles['SubHeader']))
    
    if frameworks.get("frontend"):
        story.append(Paragraph("<b>Frontend:</b>", styles['Normal']))
        for fw in frameworks["frontend"]:
            story.append(Paragraph(f"• {sanitize_text(fw)}", styles['ListItem']))
        story.append(Spacer(1, 0.05*inch))
    
    if frameworks.get("backend"):
        story.append(Paragraph("<b>Backend:</b>", styles['Normal']))
        for fw in frameworks["backend"]:
            story.append(Paragraph(f"• {sanitize_text(fw)}", styles['ListItem']))
        story.append(Spacer(1, 0.05*inch))
    
    if not frameworks.get("frontend") and not frameworks.get("backend"):
        story.append(Paragraph("No major frameworks detected.", styles['Description']))
    
    story.append(Spacer(1, 0.12*inch))
    
    # Dependencies
    story.append(Paragraph("3.2 Package Dependencies", styles['SubHeader']))
    
    if deps.get("frontend"):
        story.append(Paragraph(f"<b>Frontend ({len(deps['frontend'])}):</b>", styles['Normal']))
        dep_list = ", ".join([sanitize_text(d) for d in sorted(deps["frontend"][:20])])
        story.append(Paragraph(dep_list, styles['Description']))
        if len(deps['frontend']) > 20:
            story.append(Paragraph(f"... +{len(deps['frontend']) - 20} more", styles['Metadata']))
        story.append(Spacer(1, 0.08*inch))
    
    if deps.get("backend"):
        story.append(Paragraph(f"<b>Backend ({len(deps['backend'])}):</b>", styles['Normal']))
        dep_list = ", ".join([sanitize_text(d) for d in sorted(deps["backend"][:20])])
        story.append(Paragraph(dep_list, styles['Description']))
        if len(deps['backend']) > 20:
            story.append(Paragraph(f"... +{len(deps['backend']) - 20} more", styles['Metadata']))
    
    # Infrastructure section
    story.append(Spacer(1, 0.12*inch))
    story.append(Paragraph("3.3 Infrastructure & Build", styles['SubHeader']))
    
    infra = results["master_json"].get("infrastructure", {})
    
    infra_data = [
        ["Component", "Status"],
        ["Docker", "✓" if infra.get('docker_used') else "✗"],
        ["CI/CD", "✓" if infra.get('ci_cd_detected') else "✗"],
    ]
    
    t = Table(infra_data, colWidths=[3*inch, 1.5*inch])
    t.setStyle(create_table_style())
    story.append(t)
    story.append(Spacer(1, 0.15*inch))


def add_file_structure_page(story: List, results: Dict, styles: Dict):
    """Add file structure and classification page."""
    story.append(Paragraph("4. FILE STRUCTURE & CLASSIFICATION", styles['SectionHeader']))
    story.append(Spacer(1, 0.1*inch))
    
    classification = results.get("classification", {})
    
    # Group files by category
    categories = {
        'Frontend': [],
        'Backend': [],
        'Configuration': [],
        'Documentation': [],
        'Tests': [],
        'Build & CI/CD': [],
        'Other': []
    }
    
    for file_info in classification.get('files', []):
        path = file_info.get('path', '')
        category = file_info.get('category', 'Other')
        
        if 'frontend' in category.lower() or 'ui' in category.lower():
            categories['Frontend'].append(path)
        elif 'backend' in category.lower() or 'api' in category.lower():
            categories['Backend'].append(path)
        elif 'config' in category.lower():
            categories['Configuration'].append(path)
        elif 'doc' in category.lower() or 'readme' in path.lower():
            categories['Documentation'].append(path)
        elif 'test' in category.lower() or 'spec' in path.lower():
            categories['Tests'].append(path)
        elif 'ci' in category.lower() or 'build' in category.lower():
            categories['Build & CI/CD'].append(path)
        else:
            categories['Other'].append(path)
    
    for cat_name, files in categories.items():
        if files:
            story.append(Paragraph(f"4.{list(categories.keys()).index(cat_name) + 1} {cat_name} ({len(files)} files)", styles['SubHeader']))
            for file_path in sorted(files)[:20]:  # Limit to 20 files per category
                story.append(Paragraph(f"• {sanitize_text(file_path)}", styles['CodeBlock']))
            if len(files) > 20:
                story.append(Paragraph(f"... and {len(files) - 20} more files", styles['Metadata']))
            story.append(Spacer(1, 0.1*inch))


def add_detailed_source_analysis_pages(story: List, results: Dict, styles: Dict):
    """Add detailed source code analysis across multiple pages."""
    story.append(Paragraph("5. DETAILED SOURCE CODE ANALYSIS", styles['SectionHeader']))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph(
        "Comprehensive analysis of each source file with all classes, methods, functions, components, and routes.",
        styles['Description']
    ))
    story.append(Spacer(1, 0.2*inch))
    
    source_analysis = results.get("source_analysis", [])

    # Repository-level quick summary for decision making
    total_source_files = len(source_analysis)
    total_functions = sum(len(item.get("functions", [])) for item in source_analysis)
    total_classes = sum(len(item.get("classes", [])) for item in source_analysis)

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

    if total_source_files <= 10 and total_functions <= 40:
        scan_recommendation = "This repository appears compact enough for a full code review."
    elif total_functions <= 120:
        scan_recommendation = "Start with high-function files first, then review the rest as needed."
    else:
        scan_recommendation = "Use a targeted review strategy; full end-to-end reading may be time-intensive."

    repo_summary_text = (
        f"<b>Repository Quick Summary:</b> {total_source_files} analyzed source files, "
        f"{total_functions} functions/methods, and {total_classes} classes/components. "
        f"{sanitize_text(scan_recommendation)}"
    )
    story.append(Paragraph(repo_summary_text, styles['Description']))

    if top_function_files:
        story.append(Paragraph("<b>Suggested files to read first:</b>", styles['Normal']))
        for file_path in top_function_files:
            story.append(Paragraph(f"• {sanitize_text(file_path)}", styles['ListItem']))

    story.append(Spacer(1, 0.1*inch))
    
    for idx, file_analysis in enumerate(source_analysis, 1):
        file_path = file_analysis.get("file_path", "Unknown")
        language = file_analysis.get("language", "Unknown")
        
        # File header
        story.append(Paragraph(f"5.{idx} {sanitize_text(file_path)}", styles['SubHeader']))
        story.append(Paragraph(f"Language: <b>{sanitize_text(language)}</b>", styles['Metadata']))
        story.append(Spacer(1, 0.05*inch))
        
        # Docstring/Summary
        docstring = file_analysis.get("docstring", "")
        if docstring:
            story.append(Paragraph("<b>File Description:</b>", styles['Normal']))
            story.append(Paragraph(sanitize_text(docstring[:500]), styles['Description']))
            story.append(Spacer(1, 0.05*inch))
        
        # Semantic description
        semantic_desc = file_analysis.get("semantic_description", "")
        if semantic_desc:
            story.append(Paragraph("<b>🧠 Semantic Analysis:</b>", styles['Normal']))
            story.append(Paragraph(sanitize_text(semantic_desc), styles['Description']))
            story.append(Spacer(1, 0.05*inch))
        
        # Classes
        classes = file_analysis.get("classes", [])
        if classes:
            story.append(Paragraph(f"<b>Classes ({len(classes)}):</b>", styles['Normal']))
            for cls in classes:
                cls_obj = _as_dict(cls)
                cls_name = cls_obj.get("name", "Unknown")
                cls_desc = cls_obj.get("description", "")
                methods = cls_obj.get("methods", [])
                
                story.append(Paragraph(f"  • <b>{sanitize_text(cls_name)}</b>", styles['CodeBlock']))
                if cls_desc:
                    story.append(Paragraph(f"    {sanitize_text(cls_desc[:200])}", styles['Description']))
                
                if methods:
                    story.append(Paragraph(f"    Methods: {len(methods)}", styles['Metadata']))
                    for method in methods[:10]:  # Limit to 10 methods
                        method_obj = _as_dict(method)
                        method_name = method_obj.get("name", "")
                        params = method_obj.get("parameters", [])
                        method_desc = method_obj.get("description", "")
                        
                        param_str = ", ".join([sanitize_text(str(p)) for p in params])
                        story.append(Paragraph(
                            f"      - {sanitize_text(method_name)}({param_str})",
                            styles['CodeBlock']
                        ))
                        if method_desc:
                            story.append(Paragraph(f"        {sanitize_text(method_desc[:150])}", styles['Description']))
                    
                    if len(methods) > 10:
                        story.append(Paragraph(f"      ... and {len(methods) - 10} more methods", styles['Metadata']))
                
                story.append(Spacer(1, 0.05*inch))
        
        # Functions - ENHANCED with detailed descriptions
        functions = file_analysis.get("functions", [])
        if functions:
            story.append(Paragraph(f"<b>Functions ({len(functions)}):</b>", styles['Normal']))
            story.append(Spacer(1, 0.07*inch))
            
            for func_idx, func in enumerate(functions, 1):  # Show ALL functions
                func_obj = _as_dict(func)
                func_name = func_obj.get("name", "Unknown")
                params = func_obj.get("parameters", [])
                func_desc = func_obj.get("description", "")
                decorators = func_obj.get("decorators", [])
                returns = func_obj.get("returns", "")
                docstring = func_obj.get("docstring", "")
                is_async = func_obj.get("is_async", False)
                
                param_str = ", ".join([sanitize_text(str(p)) for p in params])
                
                # Decorators
                if decorators:
                    dec_str = " ".join([f"@{sanitize_text(d)}" for d in decorators])
                    story.append(Paragraph(f"  {dec_str}", styles['CodeBlock']))
                
                # Function signature
                async_prefix = "async " if is_async else ""
                story.append(Paragraph(
                    f"  {func_idx}. <b>{async_prefix}{sanitize_text(func_name)}</b>({param_str})",
                    styles['CodeBlock']
                ))
                
                # Return type
                if returns:
                    story.append(Paragraph(f"     Returns: {sanitize_text(returns)}", styles['Metadata']))
                
                # Main description
                if func_desc:
                    story.append(Paragraph(f"     📝 {sanitize_text(func_desc[:300])}", styles['Description']))
                
                # Additional docstring
                if docstring and docstring != func_desc:
                    story.append(Paragraph(f"     📄 {sanitize_text(docstring[:250])}", styles['Description']))
                
                # Parameters with descriptions if available
                if params and len(params) > 0:
                    param_info = func_obj.get("param_descriptions", {})
                    story.append(Paragraph(f"     Parameters: {len(params)}", styles['Metadata']))
                    for param in params[:8]:  # Limit params shown
                        param_desc = param_info.get(str(param), "") if param_info else ""
                        if param_desc:
                            story.append(Paragraph(
                                f"       • <b>{sanitize_text(str(param))}</b>: {sanitize_text(param_desc[:150])}",
                                styles['Description']
                            ))
                        else:
                            story.append(Paragraph(
                                f"       • {sanitize_text(str(param))}",
                                styles['Metadata']
                            ))
                
                story.append(Spacer(1, 0.08*inch))
                
                # Page break every 8 functions to manage page space
                if func_idx % 8 == 0 and func_idx < len(functions):
                    story.append(PageBreak())
        
        # React Components
        components = file_analysis.get("components", [])
        if components:
            story.append(Paragraph(f"<b>React Components ({len(components)}):</b>", styles['Normal']))
            for comp in components:
                comp_obj = _as_dict(comp)
                comp_name = comp_obj.get("name", "Unknown")
                comp_type = comp_obj.get("type", "")
                props = comp_obj.get("props", [])
                hooks = comp_obj.get("hooks", [])
                comp_desc = comp_obj.get("description", "")
                
                story.append(Paragraph(
                    f"  • <b>{sanitize_text(comp_name)}</b> ({sanitize_text(comp_type)})",
                    styles['CodeBlock']
                ))
                
                if props:
                    story.append(Paragraph(f"    Props: {', '.join([sanitize_text(p) for p in props[:5]])}", styles['Metadata']))
                
                if hooks:
                    story.append(Paragraph(f"    Hooks: {', '.join([sanitize_text(h) for h in hooks])}", styles['Metadata']))
                
                if comp_desc:
                    story.append(Paragraph(f"    {sanitize_text(comp_desc[:150])}", styles['Description']))
                
                story.append(Spacer(1, 0.03*inch))
        
        # API Routes
        routes = file_analysis.get("routes", [])
        if routes:
            story.append(Paragraph(f"<b>API Routes ({len(routes)}):</b>", styles['Normal']))
            for route in routes:
                route_obj = _as_dict(route)
                method = route_obj.get("method", "GET")
                path = route_obj.get("path", "")
                handler = route_obj.get("handler", "")
                route_desc = route_obj.get("description", "")
                
                story.append(Paragraph(
                    f"  • <b>{sanitize_text(method)}</b> {sanitize_text(path)}",
                    styles['CodeBlock']
                ))
                
                if handler:
                    story.append(Paragraph(f"    Handler: {sanitize_text(handler)}", styles['Metadata']))
                
                if route_desc:
                    story.append(Paragraph(f"    {sanitize_text(route_desc[:150])}", styles['Description']))
                
                story.append(Spacer(1, 0.03*inch))
        
        story.append(Spacer(1, 0.15*inch))
        
        # Page break after every 5 files for readability
        if idx % 5 == 0 and idx < len(source_analysis):
            story.append(PageBreak())


def add_config_analysis_page(story: List, results: Dict, styles: Dict):
    """Add configuration files analysis page."""
    story.append(Paragraph("6. CONFIGURATION FILES ANALYSIS", styles['SectionHeader']))
    story.append(Spacer(1, 0.1*inch))
    config_data = results.get("config_data", {})

    if not config_data:
        story.append(Paragraph("No configuration files analyzed.", styles['Description']))
        return

    idx = 1

    package_json = config_data.get("package_json")
    if package_json:
        story.append(Paragraph(f"6.{idx} package.json", styles['SubHeader']))
        story.append(Paragraph("Type: <b>Node Package Configuration</b>", styles['Metadata']))
        story.append(Spacer(1, 0.05*inch))

        scripts = package_json.get("scripts", {})
        if scripts:
            story.append(Paragraph("<b>Scripts:</b>", styles['Normal']))
            for script_name, script_cmd in list(scripts.items())[:12]:
                story.append(Paragraph(
                    f"  • {sanitize_text(script_name)}: {sanitize_text(script_cmd)}",
                    styles['CodeBlock']
                ))
            if len(scripts) > 12:
                story.append(Paragraph(f"... and {len(scripts) - 12} more scripts", styles['Metadata']))

        idx += 1
        story.append(Spacer(1, 0.12*inch))

    requirements_txt = config_data.get("requirements_txt")
    if requirements_txt:
        story.append(Paragraph(f"6.{idx} requirements.txt", styles['SubHeader']))
        story.append(Paragraph("Type: <b>Python Dependencies</b>", styles['Metadata']))
        story.append(Spacer(1, 0.05*inch))

        libraries = requirements_txt.get("libraries", [])
        if libraries:
            story.append(Paragraph(f"<b>Libraries ({len(libraries)}):</b>", styles['Normal']))
            for lib in libraries[:25]:
                story.append(Paragraph(f"  • {sanitize_text(lib)}", styles['CodeBlock']))
            if len(libraries) > 25:
                story.append(Paragraph(f"... and {len(libraries) - 25} more libraries", styles['Metadata']))

        idx += 1
        story.append(Spacer(1, 0.12*inch))

    dockerfile = config_data.get("dockerfile")
    if dockerfile:
        story.append(Paragraph(f"6.{idx} Dockerfile", styles['SubHeader']))
        story.append(Paragraph("Type: <b>Container Build Configuration</b>", styles['Metadata']))
        story.append(Spacer(1, 0.05*inch))

        base_images = dockerfile.get("base_images", [])
        if base_images:
            story.append(Paragraph("<b>Base Images:</b>", styles['Normal']))
            for image in base_images:
                story.append(Paragraph(f"  • {sanitize_text(image)}", styles['CodeBlock']))

        exposed_ports = dockerfile.get("exposed_ports", [])
        if exposed_ports:
            story.append(Paragraph(f"<b>Exposed Ports:</b> {', '.join(exposed_ports)}", styles['Description']))

        if dockerfile.get("cmd"):
            story.append(Paragraph(f"<b>CMD:</b> {sanitize_text(dockerfile.get('cmd'))}", styles['Description']))

        idx += 1
        story.append(Spacer(1, 0.12*inch))

    docker_compose = config_data.get("docker_compose")
    if docker_compose:
        story.append(Paragraph(f"6.{idx} docker-compose", styles['SubHeader']))
        story.append(Paragraph("Type: <b>Container Orchestration</b>", styles['Metadata']))
        services = docker_compose.get("services", [])
        if services:
            story.append(Paragraph(f"<b>Services ({len(services)}):</b>", styles['Normal']))
            for svc in services[:20]:
                story.append(Paragraph(f"  • {sanitize_text(svc)}", styles['CodeBlock']))
        story.append(Spacer(1, 0.12*inch))


def add_repository_insights_page(story: List, results: Dict, styles: Dict):
    """Add repository insights section so export includes dashboard metrics."""
    story.append(Paragraph("7. REPOSITORY INSIGHTS", styles['SectionHeader']))
    story.append(Spacer(1, 0.1*inch))

    insights = results.get("insights", {})
    if not insights:
        story.append(Paragraph("Repository insights were not available for this analysis run.", styles['Description']))
        return

    summary_data = [
        ["Metric", "Value"],
        ["Stars", str(insights.get("stars", 0))],
        ["Forks", str(insights.get("forks", 0))],
        ["Open Issues", str(insights.get("open_issues", 0))],
        ["Open Pull Requests", str(insights.get("open_pull_requests", 0))],
        ["Commits (Last 30 Days)", str(insights.get("commit_count_30d", 0))],
        ["Weekly Commit Frequency", str(insights.get("commit_frequency_weekly", 0.0))],
    ]
    t = Table(summary_data, colWidths=[3.5*inch, 1.8*inch])
    t.setStyle(create_table_style())
    story.append(t)
    story.append(Spacer(1, 0.12*inch))

    top_languages = insights.get("top_languages", [])
    if top_languages:
        story.append(Paragraph("7.1 Top Languages", styles['SubHeader']))
        for row in top_languages[:10]:
            story.append(Paragraph(
                f"• {sanitize_text(row.get('language', 'Unknown'))}: {row.get('share_pct', 0)}%",
                styles['ListItem']
            ))
        story.append(Spacer(1, 0.08*inch))

    owner_chart = insights.get("owner_repos_chart", [])
    if owner_chart:
        story.append(Paragraph("7.2 Stars vs Forks (Top Owner Repos)", styles['SubHeader']))
        chart_data = [["Repository", "Stars", "Forks"]]
        for row in owner_chart[:10]:
            chart_data.append([
                sanitize_text(row.get("name", "")),
                str(row.get("stars", 0)),
                str(row.get("forks", 0)),
            ])
        ct = Table(chart_data, colWidths=[2.9*inch, 1.2*inch, 1.2*inch])
        ct.setStyle(create_table_style())
        story.append(ct)
        story.append(Spacer(1, 0.08*inch))

    weekly_activity = insights.get("weekly_commit_activity", [])
    if weekly_activity:
        story.append(Paragraph("7.3 Commits Over Time (Recent Weeks)", styles['SubHeader']))
        for wk in weekly_activity[-12:]:
            week_date = datetime.fromtimestamp(int(wk.get("week_ts", 0))).strftime("%Y-%m-%d")
            story.append(Paragraph(
                f"• Week {sanitize_text(week_date)}: {wk.get('total', 0)} commits",
                styles['ListItem']
            ))
        story.append(Spacer(1, 0.08*inch))

    recent_commits = insights.get("recent_commits", [])
    if recent_commits:
        story.append(Paragraph("7.4 Recent Commits", styles['SubHeader']))
        for commit in recent_commits[:10]:
            line = (
                f"• {sanitize_text(commit.get('sha', ''))} — "
                f"{sanitize_text(commit.get('message', ''))} "
                f"({sanitize_text(commit.get('author', 'Unknown'))}, {sanitize_text(commit.get('date', ''))})"
            )
            story.append(Paragraph(line, styles['ListItem']))


def add_ai_outputs_page(story: List, results: Dict, styles: Dict):
    """Add AI Repo Analysis + AI Review into exported PDF."""
    story.append(Paragraph("8. AI REPOSITORY ANALYSIS", styles['SectionHeader']))
    story.append(Spacer(1, 0.1*inch))

    ai_analysis = results.get("ai_analysis")
    if ai_analysis:
        story.append(Paragraph("8.1 Structured AI Summary", styles['SubHeader']))
        story.append(Paragraph(
            f"<b>Purpose:</b> {sanitize_text(ai_analysis.get('purpose', 'N/A'))}",
            styles['Description']
        ))
        story.append(Paragraph(
            f"<b>Project Summary:</b> {sanitize_text(ai_analysis.get('project_summary', 'N/A'))}",
            styles['Description']
        ))

        quality_data = [
            ["Field", "Value"],
            ["Code Quality Score", str(ai_analysis.get("code_quality_score", "N/A"))],
            ["Complexity", sanitize_text(ai_analysis.get("complexity", "N/A"))],
            ["Generated By", "AI" if ai_analysis.get("ai_generated") else "Heuristic"],
        ]
        qt = Table(quality_data, colWidths=[2.8*inch, 2.5*inch])
        qt.setStyle(create_table_style())
        story.append(qt)
        story.append(Spacer(1, 0.08*inch))

        tech_stack = ai_analysis.get("tech_stack", [])
        if tech_stack:
            story.append(Paragraph("<b>Tech Stack Detected:</b>", styles['Normal']))
            story.append(Paragraph(", ".join([sanitize_text(t) for t in tech_stack[:15]]), styles['Description']))

        improvements = ai_analysis.get("suggested_improvements", [])
        if improvements:
            story.append(Paragraph("<b>Suggested Improvements:</b>", styles['Normal']))
            for tip in improvements[:10]:
                story.append(Paragraph(f"• {sanitize_text(tip)}", styles['ListItem']))
    else:
        story.append(Paragraph("Structured AI repository analysis was not generated in this run.", styles['Description']))

    story.append(Spacer(1, 0.12*inch))

    ai_review = results.get("ai_review")
    story.append(Paragraph("8.2 AI Architectural Review", styles['SubHeader']))
    if ai_review and ai_review.get("success"):
        review_text = sanitize_text(ai_review.get("review", ""))
        story.append(Paragraph(review_text[:6000], styles['Description']))
    elif ai_review and ai_review.get("error"):
        story.append(Paragraph(f"AI review unavailable: {sanitize_text(ai_review.get('error'))}", styles['Description']))
    else:
        story.append(Paragraph("AI architectural review was not generated for this run.", styles['Description']))


def add_architecture_insights_page(story: List, results: Dict, styles: Dict):
    """Add architecture insights page."""
    story.append(Paragraph("9. ARCHITECTURE INSIGHTS", styles['SectionHeader']))
    story.append(Spacer(1, 0.1*inch))
    
    graphs = results.get("graphs", {})
    
    if graphs.get("dependency_graph"):
        story.append(Paragraph("9.1 Dependency Graph", styles['SubHeader']))
        story.append(Paragraph(
            "A dependency graph has been generated showing the relationships between modules and components.",
            styles['Description']
        ))
        story.append(Spacer(1, 0.1*inch))
    
    if graphs.get("call_graph"):
        story.append(Paragraph("9.2 Call Graph", styles['SubHeader']))
        story.append(Paragraph(
            "A call graph has been generated showing function call relationships.",
            styles['Description']
        ))
        story.append(Spacer(1, 0.1*inch))
    
    # Architecture patterns detected
    story.append(Paragraph("9.3 Detected Patterns", styles['SubHeader']))
    
    meta = results["master_json"]["project_metadata"]
    patterns = []
    
    if meta.get('frontend_detected') and meta.get('backend_detected'):
        patterns.append("Full-Stack Application (Frontend + Backend)")
    elif meta.get('frontend_detected'):
        patterns.append("Frontend-Only Application")
    elif meta.get('backend_detected'):
        patterns.append("Backend-Only Application")
    
    if patterns:
        for pattern in patterns:
            story.append(Paragraph(f"• {pattern}", styles['ListItem']))
    else:
        story.append(Paragraph("No specific architectural patterns detected.", styles['Description']))
    
    story.append(Spacer(1, 0.15*inch))


def add_appendix_page(story: List, results: Dict, styles: Dict):
    """Add appendix with additional information."""
    story.append(Paragraph("10. APPENDIX", styles['SectionHeader']))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("10.1 Report Generation Details", styles['SubHeader']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}", styles['Normal']))
    story.append(Paragraph("Tool: Repository Intelligence Engine v1.0", styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("10.2 Analysis Methodology", styles['SubHeader']))
    methodology = """
    This report was generated through a multi-stage analysis pipeline:
    1. Repository fetching via GitHub API
    2. File classification and categorization
    3. Static code parsing using AST (Abstract Syntax Tree) analysis
    4. Configuration file parsing
    5. Dependency graph construction
    6. Semantic pattern analysis using rule-based inference
    7. Optional AI architectural review
    """
    story.append(Paragraph(methodology, styles['Description']))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("10.3 Disclaimer", styles['SubHeader']))
    disclaimer = """
    This automated analysis provides insights based on static code analysis and pattern recognition.
    While comprehensive, it may not capture all architectural nuances or context-specific design decisions.
    Human review and validation are recommended for critical architectural decisions.
    """
    story.append(Paragraph(disclaimer, styles['Description']))


# ──────────────────────────────────────────────
# Main PDF Generation Function
# ──────────────────────────────────────────────

def generate_comprehensive_pdf_report(results: Dict) -> bytes:
    """
    Generate a comprehensive, well-structured PDF report with detailed analysis.
    Uses page-based formatting to optimize content distribution.
    Automatically manages page breaks based on available space.
    
    Args:
        results: Analysis results dictionary containing all data
        
    Returns:
        bytes: PDF file as bytes
    """
    buffer = io.BytesIO()
    
    # Use letter size, professional margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )
    
    story = []
    styles = create_custom_styles()
    
    # Build the report sections with page management
    # NOTE: TOC removed for more compact format
    add_cover_page(story, results, styles)
    add_executive_summary_page(story, results, styles)
    add_project_overview_page(story, results, styles)
    add_dependencies_infrastructure_page(story, results, styles)
    add_file_structure_page(story, results, styles)
    add_detailed_source_analysis_pages(story, results, styles)
    add_config_analysis_page(story, results, styles)
    add_repository_insights_page(story, results, styles)
    add_ai_outputs_page(story, results, styles)
    add_architecture_insights_page(story, results, styles)
    add_appendix_page(story, results, styles)
    
    # Build the PDF
    doc.build(story)
    
    buffer.seek(0)
    return buffer.getvalue()
