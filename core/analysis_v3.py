import re
from .analysis_v2 import ACTION_VERBS

def starts_with_instruction(transcript):
    """Recognize an initial command, including one with a time preface."""
    text = transcript.lower().strip()
    text = re.sub(r"^(?:at [^,]+|on [^,]+|tomorrow(?: morning| afternoon| evening)?)\s*,\s*", "", text)
    verbs = "|".join(re.escape(verb) for verb in ACTION_VERBS)
    return bool(re.match(r"^(?:please\s+)?(?:" + verbs + r")\b", text))

def split_instruction_and_followup(transcript):
    """Separate the initial statement from a possible follow-up."""
    parts = re.split(r"\.{2,}|[.!?;]|\bbut\b|—", transcript, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 1:
        return transcript.strip(), ""
    return parts[0].strip(" ,"), parts[1].strip()

def followup_revises_instruction(followup):
    """Detect explicit correction patterns in a follow-up."""
    text = followup.lower().strip()
    cue = r"^(?:(?:actually|wait|sorry|no|instead|on second thought)\b[\s,.;:!?]+)+"
    action = r"(?:send|book|email|move|delete|share|transfer|keep|make it|change that|do not)\b"
    return bool(re.match(cue + action, text) or re.match(r"^change that\b", text))

def detect_instruction_revision_v3(transcript):
    """Identify a possible revision of an initial instruction."""
    initial, followup = split_instruction_and_followup(transcript)
    return starts_with_instruction(initial) and followup_revises_instruction(followup)
