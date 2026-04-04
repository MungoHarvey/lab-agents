from parser import extract_text, normalize_heading, extract_sections


def test_extract_text_from_simple_paragraph():
    node = {
        "type": "paragraph",
        "content": [{"type": "text", "text": "Hello world"}],
    }
    assert extract_text(node) == "Hello world\n"


def test_extract_text_from_nested_content():
    node = {
        "type": "paragraph",
        "content": [
            {"type": "text", "text": "Hello "},
            {"type": "text", "marks": [{"type": "bold"}], "text": "bold"},
        ],
    }
    assert extract_text(node) == "Hello bold\n"


def test_extract_text_from_string():
    assert extract_text("plain") == "plain"


def test_extract_text_from_list():
    nodes = [
        {"type": "text", "text": "a"},
        {"type": "text", "text": "b"},
    ]
    assert extract_text(nodes) == "ab"


def test_extract_text_returns_empty_for_non_dict_non_str():
    assert extract_text(42) == ""


def test_normalize_heading_canonical():
    assert normalize_heading("Introduction") == "introduction"
    assert normalize_heading("METHODS") == "methods"
    assert normalize_heading("Results:") == "results"


def test_normalize_heading_typo():
    assert normalize_heading("Introdcution") == "introduction"


def test_normalize_heading_unknown():
    assert normalize_heading("Appendix") is None


def test_extract_sections_full_doc():
    doc = {
        "type": "doc",
        "content": [
            {"type": "heading", "content": [{"type": "text", "text": "Introduction"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "This is the intro with enough words to count properly in our system"}]},
            {"type": "heading", "content": [{"type": "text", "text": "Methods"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "We did things"}]},
        ],
    }
    sections = extract_sections(doc)
    assert "introduction" in sections
    assert "methods" in sections
    assert "intro" in sections["introduction"].lower()
    assert "did things" in sections["methods"]


def test_extract_sections_empty_doc():
    assert extract_sections({}) == {}
    assert extract_sections(None) == {}


def test_extract_sections_unknown_heading_stops_accumulation():
    doc = {
        "type": "doc",
        "content": [
            {"type": "heading", "content": [{"type": "text", "text": "Introduction"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Intro text"}]},
            {"type": "heading", "content": [{"type": "text", "text": "Appendix"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Should not appear in intro"}]},
        ],
    }
    sections = extract_sections(doc)
    assert "should not appear" not in sections.get("introduction", "").lower()
