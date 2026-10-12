import re


def _has_word(text, word):
    """Whole-word match, so 'AI' does not match 'main'."""
    pattern = r"(?<!\w)" + re.escape(word.lower()) + r"(?!\w)"
    return re.search(pattern, text) is not None


def title_ok(job, profile):
    """Reject jobs whose title contains an excluded word (substring match,
    so 'Werkstudent' also catches 'Werkstudentin')."""
    title = job["title"].lower()
    return not any(w.lower() in title for w in profile.get("exclude_keywords", []))


def description_ok(job, profile):
    words = profile.get("relevance_keywords") or (
        profile.get("must_have_keywords", []) + profile.get("nice_to_have", [])
    )
    text = (job["title"] + " " + job["description"]).lower()
    return any(_has_word(text, w) for w in words)