#!/usr/bin/env python3
from jinja2 import Template


def generate(
    id: str,
    step: int,
    step_map: list[int],
    template: Template,
    alphabet_size: int,
    font_path: str,
    host: str,
    host_leak: str,
    leak_selector: str,
    browser: str,
    parent: str = "body",
) -> str:
    if step > len(step_map):
        raise ValueError(
            f"Step {step} is greater than the number of steps in the step map."
        )

    # Simplified HTML width - just needs to fit the alphabet
    html_width = alphabet_size + 2

    width_containers = []
    for width in range(1, alphabet_size + 2):
        char_idx = html_width - width - 1
        width_containers.append({"width": width, "char_idx": char_idx, "host": host})

    step_char = f"\\{step_map[step]:x}"

    # Render template with context
    context = {
        "id": id,
        "step": step,
        "step_char": step_char,
        "html_width": html_width,
        "font_path": font_path,
        "width_containers": width_containers,
        "leak_selector": leak_selector,
        "host": host,
        "host_leak": host_leak,
        "browser": browser,
        "parent": parent,
    }

    return template.render(**context)


def generate_staging(
    id: str,
    step: int,
    host: str,
    template: Template,
    browser: str,
) -> str:
    context = {
        "id": id,
        "step": step,
        "host": host,
        "browser": browser,
    }

    return template.render(**context)


def generate_sfc(
    id: str,
    step: int,
    idx_max: int,
    template: Template,
    alphabet_size: int,
    host: str,
    host_leak: str,
    leak_selector: str,
    browser: str,
    length: int,
    parent: str = "body",
) -> str:
    html_width = length * (alphabet_size + 1) + 1

    width_containers = []
    for width in range(1, html_width):
        char_idx = (html_width - width - 1) % (alphabet_size + 1)
        step = (html_width - width - 1) // (alphabet_size + 1)
        width_containers.append(
            {"width": width, "char_idx": char_idx, "host": host, "step": step}
        )

    context = {
        "id": id,
        "step": step,
        "idx_max": idx_max,
        "width_containers": width_containers,
        "html_width": html_width,
        "host": host,
        "host_leak": host_leak,
        "leak_selector": leak_selector,
        "browser": browser,
        "parent": parent,
    }

    return template.render(**context)


def generate_anim(
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
    if idx_max > len(step_map):
        raise ValueError(
            f"Idx max {idx_max} is greater than the number of steps in the step map."
        )

    # Simplified HTML width - just needs to fit the alphabet
    html_width = alphabet_size + 2

    width_containers = []
    for width in range(1, alphabet_size + 2):
        char_idx = html_width - width - 1
        width_containers.append({"width": width, "char_idx": char_idx, "host": host})

    step_chars = [f"\\{step_map[i]:x}" for i in range(len(step_map))]
    # Render template with context
    context = {
        "id": id,
        "idx_max": idx_max,
        "step_chars": step_chars,
        "html_width": html_width,
        "font_path": font_path,
        "width_containers": width_containers,
        "leak_selector": leak_selector,
        "host": host,
        "host_leak": host_leak,
        "browser": browser,
        "parent": parent,
    }

    return template.render(**context)
