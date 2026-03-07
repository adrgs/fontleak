#!/usr/bin/env python3
from jinja2 import Template


def generate(
    id: str,
    idx_max: int,
    step_map: list[int],
    template: Template,
    font_path: str,
    alphabet_size: int,
    host: str,
    host_leak: str,
    leak_selector: str,
    browser: str,
    parent: str = "body",
) -> str:
    """Generate static CSS for font leak attacks"""
    # Calculate width containers for leak detection
    html_width = alphabet_size + 2
    width_containers = []
    for width in range(1, alphabet_size + 2):
        char_idx = html_width - width - 1
        width_containers.append({"width": width, "char_idx": char_idx, "host": host})

    # Generate step characters
    step_chars = [f"\\{code:x}" for code in step_map]

    # Prepare context for template rendering
    context = {
        "id": id,
        "idx_max": idx_max,
        "step_chars": step_chars,
        "step_char": step_chars[0] if step_chars else "\\100",
        "html_width": html_width,
        "font_path": font_path,
        "width_containers": width_containers,
        "leak_selector": leak_selector,
        "host": host,
        "host_leak": host_leak,
        "browser": browser,
        "parent": parent,
    }

    # Render CSS template
    return template.render(**context)
