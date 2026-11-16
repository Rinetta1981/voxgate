"use strict";
/* Single-file, cache-versioned browser analyzer: no remote requests or real actions. */
try {

/* ---- detector.js ---- */
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

/* ---- interpret.js ---- */
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

/* ---- site.js ---- */
"use strict";
/* Public UI: compare fixed V4 output with a separate exploratory explanation.
 * No remote calls, model inference, or external actions.
 */
(function () {
  const form = document.getElementById("revision-form");
  const input = document.getElementById("instruction");
  const charCount = document.getElementById("char-count");
  const panel = document.getElementById("result-panel");
  const icon = document.getElementById("result-icon");
  const title = document.getElementById("result-title");
  const description = document.getElementById("result-description");
  const details = document.getElementById("result-details");
  const opening = document.getElementById("result-opening");
  const revision = document.getElementById("result-revision");
  const review = document.getElementById("result-review");
  const submitButton = document.getElementById("analyze-button");
  const feedback = document.getElementById("analysis-feedback");
  const examples = {
    correction: "Send the report to Alice. Actually, send it to Bob instead.",
    comment: "Forward the contract to Legal. Actually, the office is closed.",
    asr: "sent the calendar invitation now, but change that to tomorrow."
  };
  const evidence = document.createElement("section");
  evidence.id = "repair-evidence";
  evidence.className = "repair-evidence";
  const slots = {};
  const heading = document.createElement("h4");
  heading.textContent = "What the text shows";
  evidence.appendChild(heading);
  for (const [key, label] of [["original", "Before the cue"], ["cue", "Potential correction cue"], ["followup", "After the cue"]]) {
    const item = document.createElement("div");
    item.className = "repair-evidence-item";
    const prompt = document.createElement("small");
    prompt.textContent = label;
    const value = document.createElement("p");
    value.textContent = "—";
    item.append(prompt, value);
    evidence.appendChild(item);
    slots[key] = value;
  }
  const note = document.createElement("p");
  note.className = "repair-disclosure";
  note.textContent = "The explanation is an experimental heuristic, separate from frozen WaitWise V4. It does not identify an authorized final action.";
  evidence.appendChild(note);
  details.insertAdjacentElement("afterend", evidence);

  function render() {
    charCount.textContent = input.value.length + " / 2000 characters";
    const text = input.value;
    if (!text.trim()) {
      panel.dataset.state = "empty";
      icon.className = "result-icon result-neutral";
      icon.textContent = "?";
      title.textContent = "Enter an instruction";
      description.textContent = "Enter a fictional instruction. The demo will identify what it can see and explain its uncertainty.";
      details.hidden = true;
      evidence.hidden = true;
      feedback.textContent = "Enter an instruction to begin.";
      return;
    }
    if (!window.VOXGATE_DETECT || !window.VOXGATE_EXPLAIN) {
      panel.dataset.state = "empty";
      title.textContent = "Analyzer did not load";
      description.textContent = "Reload the page. Nothing was processed remotely.";
      feedback.textContent = "Analyzer not available. Reload this page.";
      details.hidden = true;
      evidence.hidden = true;
      return;
    }
    try {
      const v4 = window.VOXGATE_DETECT.evaluate(text);
      const explanation = window.VOXGATE_EXPLAIN.analyze(text);
      const flagged = v4.candidate || explanation.status === "candidate";
      panel.dataset.state = flagged ? "flagged" : "not-flagged";
      icon.className = "result-icon " + (flagged ? "result-flagged" : "result-neutral");
      icon.textContent = flagged ? "↶" : "?";
      title.textContent = explanation.heading;
      description.textContent = explanation.explanation;
      details.hidden = false;
      opening.textContent = v4.recognizedOpening ? "Yes" : "No / unsupported";
      revision.textContent = v4.candidate ? "Flagged by V4" : explanation.status === "candidate" ? "Exploratory flag only" : "Not confirmed";
      review.textContent = explanation.review;
      evidence.hidden = false;
      slots.original.textContent = explanation.original || "—";
      slots.cue.textContent = explanation.cue || "—";
      slots.followup.textContent = explanation.followup || "—";
      feedback.textContent = "Analysis complete: " + explanation.heading + ". See the findings below.";
    } catch (error) {
      title.textContent = "Could not inspect this text";
      description.textContent = "This input is outside the supported format. No action was taken.";
      feedback.textContent = "Could not analyze this input. Try a shorter instruction.";
      details.hidden = true;
      evidence.hidden = true;
    }
  }
  submitButton.addEventListener("click", () => {
    render();
    panel.scrollIntoView({behavior:"smooth",block:"start"});
  });
  form.addEventListener("submit", (event) => {event.preventDefault();render();});
  input.addEventListener("input", render);
  document.querySelectorAll("[data-example]").forEach((button) => {
    button.addEventListener("click", () => {
      input.value = examples[button.dataset.example] || "";
      render();
      input.focus({preventScroll:true});
      panel.scrollIntoView({behavior:"smooth",block:"nearest"});
    });
  });
  render();
  feedback.textContent = "Analyzer ready. Type any fictional instruction, then choose Analyze.";
})();

} catch (error) {
  // Visible failure rather than an apparently inert analysis button.
  const label = document.getElementById("analysis-feedback");
  if (label) label.textContent = "Analyzer failed to initialize. Please reload the page; if this persists, contact the project owner.";
  const btn = document.getElementById("analyze-button");
  if (btn) btn.disabled = true;
  console.error("VOXGATE analyzer initialization failed:", error);
}
