"""Score experiment completeness based on section word counts and protocol attachment."""

SECTION_THRESHOLDS = {
    "introduction": (50, 10),  # (green_threshold, amber_threshold)
    "aims": (50, 10),
    "methods": (50, 10),
    "results": (50, 10),
    "discussion": (50, 10),
}

SECTIONS = list(SECTION_THRESHOLDS.keys())


def word_count(text):
    return len(text.split()) if text else 0


def score_section(section_name, wc):
    """Return 'green', 'amber', or 'red' for a section based on word count."""
    green_thresh, amber_thresh = SECTION_THRESHOLDS[section_name]
    if wc > green_thresh:
        return "green"
    elif wc >= amber_thresh:
        return "amber"
    return "red"


def score_experiment(sections, protocol_count):
    """Score an experiment's completeness. Returns dict with overall score and flags."""
    flags = []
    scores = {}
    has_red = False
    has_amber = False

    for section_name in SECTIONS:
        text = sections.get(section_name, "")
        wc = word_count(text)
        score = score_section(section_name, wc)
        scores[section_name] = {"score": score, "word_count": wc}
        if score == "red":
            has_red = True
            flags.append({"section": section_name, "score": "red", "word_count": wc})
        elif score == "amber":
            has_amber = True

    # Protocol check
    protocol_score = "green" if protocol_count >= 1 else "red"
    scores["protocol"] = {"score": protocol_score, "count": protocol_count}
    if protocol_score == "red":
        has_red = True
        flags.append({"section": "protocol", "score": "red", "word_count": 0})

    if has_red:
        overall = "red"
    elif has_amber:
        overall = "amber"
    else:
        overall = "green"

    return {"overall": overall, "flags": flags, "scores": scores}
