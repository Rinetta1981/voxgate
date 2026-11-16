/*
 * VOXGATE WaitWise V4 browser port.
 * Mirrors core/analysis_v4.py at Git commit 53283b0.
 * Candidate revision classification ONLY. No authorization or action execution.
 * No network activity, telemetry, storage, or server-side processing.
 */
(function (root) {
  "use strict";
  const INITIAL_VERBS = [
    "send", "book", "email", "move", "delete", "share", "transfer",
    "put", "keep", "forward", "cancel", "hold", "reschedule"
  ];
  const CORRECTION_VERBS = [
    ...INITIAL_VERBS, "do not", "don't", "make it", "make that", "change that", "stop"
  ];
  const MARKERS = ["on second thought", "actually", "sorry", "wait", "no", "instead", "rather"];
  const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const alternation = (phrases) => "(?:" + [...phrases]
    .sort((a, b) => b.length - a.length)
    .map(escapeRegex).join("|") + ")";
  const start = new RegExp(
    "^\\s*(?:(?:at|on)\\s+[^,]{1,50},\\s*|tomorrow(?:\\s+(?:morning|afternoon|evening))?,\\s*)?" +
    "(?:please\\s+)?" + alternation(INITIAL_VERBS) + "\\b", "i");
  const cueReplacement = new RegExp(
    "\\b" + alternation(MARKERS) + "\\b[\\s,;:.!?—-]+" +
    "(?:(?:" + alternation(MARKERS) + ")\\b[\\s,;:.!?—-]+){0,2}" +
    "(?:please\\s+)?" + alternation(CORRECTION_VERBS) + "\\b", "i");
  const butChange = /\bbut\s+(?:please\s+)?(?:change that|make it|make that|cancel|do not)\b/i;

  function evaluate(transcript) {
    if (typeof transcript !== "string") throw new TypeError("Transcript must be text");
    const chars = transcript.length;
    if (!transcript.trim() || chars > 4000) {
      return { candidate: false, recognizedOpening: false, revisionPattern: false, valid: chars <= 4000, reason: chars > 4000 ? "too_long" : "empty" };
    }
    const text = transcript.toLocaleLowerCase("en").replace(/\be[\s-]?mail\b/g, "email");
    const initial = start.exec(text);
    if (!initial) return { candidate: false, recognizedOpening: false, revisionPattern: false, valid: true, reason: "opening_not_recognized" };
    const rest = text.slice(initial[0].length);
    const revisionPattern = cueReplacement.test(rest) || butChange.test(rest);
    return {
      candidate: revisionPattern,
      recognizedOpening: true,
      revisionPattern,
      valid: true,
      reason: revisionPattern ? "candidate_revision" : "no_pattern_recognized"
    };
  }

  const API = Object.freeze({ evaluate, revisionDetected: (t) => evaluate(t).candidate });
  root.VOXGATE_DETECT = API;
  if (typeof module === "object" && module.exports) module.exports = API;
})(typeof window !== "undefined" ? window : globalThis);
