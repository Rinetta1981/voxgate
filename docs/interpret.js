/*
 * Experimental, browser-only explanation layer, NOT WaitWise V4.
 * Shows spans and uncertainty; not a semantic language model, action selector,
 * or authorization mechanism. No network or storage.
 */
(function (root) {
  "use strict";
  const VERBS = [
    "send", "email", "mail", "forward", "share", "transfer", "upload", "download",
    "publish", "post", "submit", "delete", "remove", "erase", "keep", "save",
    "archive", "move", "copy", "rename", "change", "replace", "update", "edit",
    "book", "reserve", "schedule", "reschedule", "cancel", "invite", "uninvite",
    "call", "text", "message", "notify", "tell", "ask", "open", "close", "turn",
    "switch", "lock", "unlock", "print", "hold", "release", "approve", "reject",
    "set", "create", "add", "assign", "make", "stop", "start", "run", "execute",
    "install", "uninstall", "play", "pause", "skip", "mute", "unmute", "order",
    "buy", "return", "refund", "pay", "withdraw", "deposit", "show", "hide",
    "do", "don't", "ignore", "leave", "put", "give", "get", "take", "use", "check"
  ];
  const VERB_RX = new RegExp("^(?:" + VERBS.join("|") + ")\\b", "i");
  const CUE_RX = /\b(on second thought|scratch that|never mind|nevermind|forget that|cancel that|i mean|change that|make that|actually|instead|rather|wait|sorry|no|but)\b/ig;
  const SOFT_PREFIX = /^(?:(?:okay|ok|hey|please|well|so|then|just|now|and)\b[\s,.:;!-]*)*/i;
  const REQUEST_PREFIX = /^(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|i\s+(?:want|need)\s+you\s+to\s+|i\s+would\s+like\s+you\s+to\s+)/i;
  const CANCEL_RX = /^(?:don't|do not|stop|cancel|forget|ignore|leave|never mind|nevermind|scratch that)\b/i;
  const QUESTION_RX = /^(?:is|are|was|were|who|what|when|why|how|where|whether|which|can you tell|do you know)\b/i;

  const trim = (s) => s.replace(/^[\s,;:.!?—-]+|[\s]+$/g, "").trim();
  function commandLike(s) {
    let q = trim(s).replace(SOFT_PREFIX, "").replace(REQUEST_PREFIX, "").replace(SOFT_PREFIX, "");
    if (VERB_RX.test(q) || CANCEL_RX.test(q)) return true;
    // Accept a recent imperative after a sentence preface, without pretending
    // that this constitutes full syntactic parsing.
    q = q.replace(/^(?:at|on)\s+[^,]{1,45},\s*/i, "");
    return VERB_RX.test(q);
  }
  function findCue(text) {
    CUE_RX.lastIndex = 0;
    for (const match of text.matchAll(CUE_RX)) {
      const cue = match[0].toLowerCase();
      const beginning = trim(text.slice(0, match.index));
      const following = trim(text.slice(match.index + match[0].length));
      if (!beginning || !following && !/^(scratch that|never mind|nevermind|forget that|cancel that)$/.test(cue)) continue;
      if (cue === "instead" && /^of\b/i.test(following)) continue;
      if (cue === "no" && !/^[,;.!?\s]/.test(text.slice(match.index + match[0].length, match.index + match[0].length + 1))) continue;
      if (cue === "but" && !/^(?:change|make|cancel|do not|don't|stop|send|move|keep|delete|switch|turn|use|book|email|instead)\b/i.test(following)) continue;
      if (!commandLike(beginning)) continue;
      return {cue:match[0], before:beginning, after:following};
    }
    return null;
  }
  function analyze(text) {
    if (typeof text !== "string") throw new TypeError("Expected text");
    const source = text.trim();
    if (source.length > 2000) return {status:"unsupported", original:"", cue:"", followup:"", heading:"Input too long", explanation:"Please use 2,000 characters or fewer.", review:"Not evaluated"};
    if (!source) return {status:"empty", original:"", cue:"", followup:"", heading:"Enter an instruction", explanation:"Type a fictional instruction to see an evidence-based analysis.", review:"Not evaluated"};
    const matched = findCue(source);
    if (matched) {
      const {cue,before,after} = matched;
      const cancelled = /^(scratch that|never mind|nevermind|forget that|cancel that)$/i.test(cue) && !after;
      if (cancelled || (CANCEL_RX.test(after) && !QUESTION_RX.test(after))) return {
        status:"candidate", original:before, cue, followup:after || "Cancellation phrase (no replacement given)",
        heading:"Possible cancellation or reversal", explanation:"The words after the cue appear to retract or negate an earlier request. This is a candidate, not a verified final intent.", review:"Review recommended"
      };
      if (commandLike(after)) return {
        status:"candidate", original:before, cue, followup:after,
        heading:"Possible replacement instruction", explanation:"The text has an instruction, then a correction cue followed by another command-like phrase. This supports a candidate revision; it does not prove what should be executed.", review:"Review recommended"
      };
      if (QUESTION_RX.test(after)) return {
        status:"uncertain", original:before, cue, followup:after,
        heading:"Question following an instruction", explanation:"The later text is phrased as a question, not an explicit replacement command. It may signal uncertainty; the original request should not be treated as automatically authorized.", review:"Clarification may be needed"
      };
      if (/(?:^|\s)(?:to|for|at|on)\s+\w+/i.test(after) && after.split(/\s+/).length < 8 || /^not\b/i.test(after)) return {
        status:"uncertain", original:before, cue, followup:after,
        heading:"Possible shortened correction", explanation:"The later phrase may modify a recipient, time, or other detail, but the missing parts of the instruction cannot be safely reconstructed here.", review:"Clarification recommended"
      };
      return {
        status:"uncertain", original:before, cue, followup:after,
        heading:"Cue found; replacement unconfirmed", explanation:"The follow-up includes a discourse cue but no supported replacement directive. It may be an unrelated comment. This rule-based system cannot resolve its intention.", review:"Review if consequential"
      };
    }
    const splits = source.split(/[.!?;]+/).map(trim).filter(Boolean);
    if (splits.length >= 2 && commandLike(splits[0]) && commandLike(splits[1])) return {
      status:"uncertain", original:splits[0], cue:"No explicit cue", followup:splits[1],
      heading:"Two commands; relationship unclear", explanation:"The text has multiple command-like phrases but no explicit correction marker. These could be two tasks or one revised task.", review:"Clarification recommended"
    };
    if (commandLike(source)) return {
      status:"none", original:source, cue:"None found", followup:"No explicit follow-up found",
      heading:"No explicit correction found", explanation:"An opening command is recognizable, but there is no clear repair pattern. This is not a safety or authorization judgment.", review:"Not triggered by the rule"
    };
    return {
      status:"unsupported", original:source, cue:"None recognized", followup:"No supported replacement detected",
      heading:"Cannot interpret this wording reliably", explanation:"This is a narrow English linguistic heuristic, not an AI language model. It cannot reliably analyze arbitrary questions, complex sentences or unsupported grammatical constructions.", review:"Uncertain"
    };
  }
  const api = Object.freeze({analyze, commandLike});
  root.VOXGATE_EXPLAIN = api;
  if (typeof module === "object" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
