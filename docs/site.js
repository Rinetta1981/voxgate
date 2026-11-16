"use strict";
/* VOXGATE public demo UI — offline, no network or action execution.
 * Preserves frozen V4 classification; a separate, explicitly exploratory
 * uncertainty screen explains unsupported and ambiguous input.
 */
(function () {
  const form = document.getElementById("revision-form");
  const input = document.getElementById("instruction");
  const charCount = document.getElementById("char-count");
  const panel = document.getElementById("result-panel");
  const resultIcon = document.getElementById("result-icon");
  const title = document.getElementById("result-title");
  const description = document.getElementById("result-description");
  const details = document.getElementById("result-details");
  const opening = document.getElementById("result-opening");
  const revision = document.getElementById("result-revision");
  const review = document.getElementById("result-review");
  const button = form.querySelector('button[type="submit"]');
  const examples = {
    correction: "Send the report to Alice. Actually, send it to Bob instead.",
    comment: "Forward the contract to Legal. Actually, the office is closed.",
    asr: "sent the calendar invitation now, but change that to tomorrow."
  };
  // A cue alone does not establish a revision. Used only for uncertainty notes.
  const CUES = /\b(on second thought|actually|sorry|wait|instead|rather|i mean|make that|scratch that|forget that|never mind|nevermind|cancel that|no)\b/i;

  function show(state, symbol, heading, message, recognized, pattern, reviewText) {
    panel.dataset.state = state;
    resultIcon.className = "result-icon " + (state === "flagged" ? "result-flagged" : "result-neutral");
    resultIcon.textContent = symbol;
    title.textContent = heading;
    description.textContent = message;
    details.hidden = recognized === null;
    if (recognized !== null) {
      opening.textContent = recognized;
      revision.textContent = pattern;
      review.textContent = reviewText;
    }
  }

  function render() {
    const transcript = input.value.trim();
    countChars();
    if (!transcript) {
      show("empty", "?", "Enter any fictional instruction", "Type your own text or choose an example. The page will analyze the input locally as you type.", null, "", "");
      return;
    }
    if (transcript.length > 2000) {
      show("empty", "!", "Input too long", "Please shorten the text to 2,000 characters or less.", null, "", "");
      return;
    }
    if (!window.VOXGATE_DETECT || typeof window.VOXGATE_DETECT.evaluate !== "function") {
      show("empty", "!", "Detector failed to load", "Reload this page; if the problem persists, try a private browser window. No analysis occurred.", null, "", "");
      return;
    }
    let result;
    try {
      result = window.VOXGATE_DETECT.evaluate(transcript);
    } catch (_) {
      show("empty", "!", "Unable to analyze this text", "The detector encountered an unexpected input. Nothing was submitted or stored.", null, "", "");
      return;
    }
    const match = CUES.exec(transcript);
    const cue = match ? '\u201c' + match[0] + '\u201d' : null;
    if (result.candidate) {
      show("flagged", "\u21b6", "Possible instruction revision detected",
        "WaitWise V4 found an initial command followed by a possible replacement directive. This is a review flag, not an instruction interpretation or permission to act.",
        "Yes (V4)", "Yes (V4)", "Review suggested");
    } else if (cue) {
      show("not-flagged", "?", "Possible correction cue; meaning uncertain",
        "This input was analyzed. It contains " + cue + ", but V4 could not establish a supported command-plus-replacement pattern. A human would need to check whether the original instruction was revised.",
        result.recognizedOpening ? "Yes (V4)" : "Not recognized (V4)",
        "Unconfirmed", "Consider review");
    } else if (result.recognizedOpening) {
      show("not-flagged", "\u2713", "No explicit revision pattern found",
        "This text was analyzed. V4 recognized the opening instruction but did not find a supported correction pattern. That does not establish final intent, correctness or authorization.",
        "Yes (V4)", "Not detected", "Not triggered*");
    } else {
      show("not-flagged", "?", "Text analyzed; outside supported patterns",
        "V4 did not recognize a supported opening command or explicit correction. This limited English rule-based demo cannot reliably interpret arbitrary sentences, questions, or unfamiliar instructions.",
        "Not recognized", "Unassessed", "Manual review if consequential");
    }
  }

  function countChars() { charCount.textContent = input.value.length + " / 2000 characters"; }
  // Browser-only button ensures strict form-action CSP cannot cause navigation.
  button.type = "button";
  button.addEventListener("click", render);
  form.addEventListener("submit", (event) => { event.preventDefault(); render(); });
  input.addEventListener("input", render);
  document.querySelectorAll("[data-example]").forEach((exampleButton) => {
    exampleButton.addEventListener("click", () => {
      input.value = examples[exampleButton.dataset.example] || "";
      render();
      input.focus({ preventScroll: true });
      panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  });
  countChars();
  render();
})();
