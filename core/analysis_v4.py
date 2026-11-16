"""Experimental punctuation-tolerant WaitWise text repair detector.

Designed for ASR output that may omit, move, or alter punctuation.
This module flags *possible* explicit instruction revisions only; it does not
infer consent, authorize actions, or make safe release decisions.

V3 is intentionally unchanged for controlled comparisons.
"""

from __future__ import annotations

import re

# Limited initial command inventory; intentionally do NOT map ASR homophones
# (e.g., 'weight' to 'wait' or 'center' to 'send'). Such mappings would assert
# semantic content not actually present in the recognized transcript.
INITIAL_VERBS = (
    "send", "book", "email", "move", "delete", "share", "transfer",
    "put", "keep", "forward", "cancel", "hold", "reschedule",
)

CORRECTION_VERBS = INITIAL_VERBS + (
    "do not", "don't", "make it", "make that", "change that", "stop",
)

# Require a correction marker followed by a *replacement directive*.
# Markers alone are insufficient ("Sorry about yesterday", "Wait, what time...?").
MARKERS = ("on second thought", "actually", "sorry", "wait", "no", "instead", "rather")


def _alternation(phrases: tuple[str, ...]) -> str:
    return "(?:" + "|".join(re.escape(s) for s in sorted(phrases, key=len, reverse=True)) + ")"


INITIAL = re.compile(
    r"^\s*(?:(?:at|on)\s+[^,]{1,50},\s*|tomorrow(?:\s+(?:morning|afternoon|evening))?,\s*)?"
    r"(?:please\s+)?" + _alternation(INITIAL_VERBS) + r"\b", re.IGNORECASE,
)

CUE_AND_REPLACEMENT = re.compile(
    r"\b" + _alternation(MARKERS)
    + r"\b[\s,;:.!?—-]+"
    + r"(?:(?:" + _alternation(MARKERS) + r")\b[\s,;:.!?—-]+){0,2}"
    + r"(?:please\s+)?" + _alternation(CORRECTION_VERBS) + r"\b",
    re.IGNORECASE,
)

BUT_CHANGE = re.compile(r"\bbut\s+(?:please\s+)?(?:change that|make it|make that|cancel|do not)\b", re.IGNORECASE)


def detect_instruction_revision_v4(transcript: str) -> bool:
    """Flag an explicit replacement command after an initial imperative.

    This is a *candidate* revision, not a validated user authorization.
    It is resilient to punctuation changes but still limited by ASR errors,
    imperative vocabulary, and the lack of semantic reference resolution.
    """
    if not isinstance(transcript, str):
        raise TypeError("transcript must be a string")
    if not transcript.strip() or len(transcript) > 4000:
        return False
    # Orthographic spellings, not phonetic/homophone repair.
    text = re.sub(r"\be[\s-]?mail\b", "email", transcript.casefold())
    initial = INITIAL.match(text)
    if not initial:
        return False
    rest = text[initial.end():]
    return bool(CUE_AND_REPLACEMENT.search(rest) or BUT_CHANGE.search(rest))
