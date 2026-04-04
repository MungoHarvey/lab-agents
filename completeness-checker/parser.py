"""ProseMirror document parsing and section extraction for Labstep experiments."""

HEADING_MAP = {
    "introduction": "introduction",
    "introdcution": "introduction",
    "intro": "introduction",
    "aims": "aims",
    "aim": "aims",
    "methods": "methods",
    "method": "methods",
    "results": "results",
    "result": "results",
    "discussion": "discussion",
}

BLOCK_TYPES = ("paragraph", "heading", "blockquote", "list_item", "hard_break")


def extract_text(node):
    """Recursively extract plain text from a ProseMirror node."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        text = node.get("text", "")
        if text:
            return text
        children = node.get("content", [])
        result = "".join(extract_text(c) for c in children)
        if node.get("type") in BLOCK_TYPES:
            result += "\n"
        return result
    if isinstance(node, list):
        return "".join(extract_text(n) for n in node)
    return ""


def normalize_heading(text):
    """Normalize a heading string to a canonical section name, or None."""
    key = text.lower().strip().rstrip(":").strip()
    return HEADING_MAP.get(key)


def extract_sections(pm_state):
    """Parse ProseMirror doc into {section_name: text} dict."""
    sections = {}
    current_section = None

    if not isinstance(pm_state, dict):
        return sections

    for node in pm_state.get("content", []):
        if not isinstance(node, dict):
            continue

        if node.get("type") == "heading":
            heading_text = extract_text(node).strip()
            canonical = normalize_heading(heading_text)
            if canonical:
                current_section = canonical
                if current_section not in sections:
                    sections[current_section] = ""
            else:
                current_section = None
        elif current_section is not None:
            sections[current_section] = sections.get(current_section, "") + extract_text(node)

    return sections
