from scorer import score_section, score_experiment, SECTION_THRESHOLDS


def test_score_section_green():
    assert score_section("introduction", 60) == "green"


def test_score_section_amber():
    assert score_section("introduction", 25) == "amber"


def test_score_section_red():
    assert score_section("introduction", 5) == "red"


def test_score_section_boundary_green():
    # > 50 is green
    assert score_section("methods", 51) == "green"
    assert score_section("methods", 50) == "amber"


def test_score_section_boundary_amber():
    # >= 10 is amber
    assert score_section("results", 10) == "amber"
    assert score_section("results", 9) == "red"


def test_score_experiment_all_green():
    sections = {
        "introduction": " ".join(["word"] * 60),
        "aims": " ".join(["word"] * 60),
        "methods": " ".join(["word"] * 60),
        "results": " ".join(["word"] * 60),
        "discussion": " ".join(["word"] * 60),
    }
    result = score_experiment(sections, protocol_count=1)
    assert result["overall"] == "green"
    assert result["flags"] == []


def test_score_experiment_missing_section():
    sections = {
        "introduction": " ".join(["word"] * 60),
        "aims": " ".join(["word"] * 60),
        "methods": " ".join(["word"] * 60),
        # results and discussion missing
    }
    result = score_experiment(sections, protocol_count=1)
    assert result["overall"] == "red"
    assert any(f["section"] == "results" for f in result["flags"])
    assert any(f["section"] == "discussion" for f in result["flags"])


def test_score_experiment_no_protocol():
    sections = {
        "introduction": " ".join(["word"] * 60),
        "aims": " ".join(["word"] * 60),
        "methods": " ".join(["word"] * 60),
        "results": " ".join(["word"] * 60),
        "discussion": " ".join(["word"] * 60),
    }
    result = score_experiment(sections, protocol_count=0)
    assert result["overall"] == "red"
    assert any(f["section"] == "protocol" for f in result["flags"])
