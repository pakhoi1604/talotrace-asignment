"""Deterministic prompt-injection pre-scan.

`clean_text` is also what the model receives and what snippets quote, so HR
and the model see the same text. A hit routes the answer to needs_person —
tested against known attacks, not a guarantee (see docs/architecture.md).
"""

import re
import unicodedata

# Tag characters (U+E0000–E007F) and bidi overrides/isolates are invisible
# formatting that can hide instructions from a human reader. Any one is a hit.
_HIDDEN_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069\U000e0000-\U000e007f]")

PATTERNS = [
    r"\b(ignore|disregard|forget|override)\s+"
    r"(all\s+|any\s+|the\s+|your\s+|previous\s+|prior\s+|above\s+)*"
    r"(instructions|rules|prompt|scoring guide|grading guide|rubric)\b",
    r"\b(give|award|assign|score|rate|grade|mark)\s+"
    r"(me|this answer|my answer)\s+(a\s+|an\s+)?(4|four)\b",
    r"\b(4|four)\s*(/|out of)\s*(4|four)\b",
    r"\b(reveal|print|show|repeat)\s+(your|the)\s+system\s+prompt\b",
    r"\byou\s+are\s+now\s+(an?\s+|the\s+)?(ai|grader|scorer|evaluator|language model)\b",
    r"\b(dear|attention|note to the)\s+(ai|grader|scorer|evaluator|language model)\b",
    r"</?\s*(system|instructions?|answer[-\w]*)\s*>",
]
_PATTERNS_RE = [re.compile(p) for p in PATTERNS]

MAX_SNIPPET = 120


def clean_text(text: str) -> str:
    """NFKC, then drop every format (Cf) char: zero-width, joiners, bidi, tags."""
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Cf")


def detect_scorer_instructions(text: str) -> str | None:
    """Return the matched snippet (from cleaned text, ≤120 chars) or None."""
    if _HIDDEN_RE.search(text):
        return "[hidden formatting characters]"
    cleaned = " ".join(clean_text(text).casefold().split())
    for pattern in _PATTERNS_RE:
        if match := pattern.search(cleaned):
            return match.group(0)[:MAX_SNIPPET]
    return None
