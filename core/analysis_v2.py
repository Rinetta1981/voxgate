import re

ACTION_VERBS = ("send", "book", "email", "move", "delete", "share", "transfer")
REVISION_CUES = ("actually", "wait", "sorry", "instead", "i mean", "no")

def detect_instruction_revision(transcript):
    """Check for an initial command followed by a possible correction."""
    text = transcript.lower()
    actions = "|".join(ACTION_VERBS)
    cues = "|".join(re.escape(cue) for cue in REVISION_CUES)
    if not re.search(r"^\s*(?:please\s+)?(" + actions + r")\b", text):
        return False
    boundary = r"(?:\.{2,}|[.!?;,]|\u2014)\s*"
    return bool(re.search(boundary + r"(?:" + cues + r")\b", text))
