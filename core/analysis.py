import re

REPAIR_CUES = ("actually", "wait", "i mean", "sorry", "instead")

def detect_repair_cues(transcript):
    """Find potential repair cues after punctuation boundaries."""
    text = transcript.lower()
    pattern = r"(?:\.{2,}|[.!?;,])\s*(" + "|".join(re.escape(cue) for cue in REPAIR_CUES) + r")\b"
    return list(dict.fromkeys(match.group(1) for match in re.finditer(pattern, text)))
