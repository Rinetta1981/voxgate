"use strict";
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
  const examples = {
    correction: "Send the report to Alice. Actually, send it to Bob instead.",
    comment: "Forward the contract to Legal. Actually, the office is closed.",
    asr: "sent the calendar invitation now, but change that to tomorrow."
  };

  function render() {
    const text = input.value;
    if (!text.trim()) {
      panel.dataset.state = "empty";
      resultIcon.className = "result-icon result-neutral";
      resultIcon.textContent = "?";
      title.textContent = "Enter an instruction";
      description.textContent = "Type a fictional instruction or try one of the examples. Nothing is uploaded.";
      details.hidden = true;
      return;
    }
    const result = window.VOXGATE_DETECT.evaluate(text);
    panel.dataset.state = result.candidate ? "flagged" : "not-flagged";
    resultIcon.className = "result-icon " + (result.candidate ? "result-flagged" : "result-neutral");
    resultIcon.textContent = result.candidate ? "↶" : "?";
    title.textContent = result.candidate ? "Possible revision detected" : "No revision pattern recognized";
    description.textContent = result.candidate
      ? "WaitWise V4 found a command followed by a possible replacement directive. In a real agent, this would warrant review—not automatic approval or execution."
      : result.recognizedOpening
        ? "This limited detector did not find an explicit replacement pattern. That does not mean the instruction is correct, final, or authorized."
        : "The initial command was not recognized. A transcription error, unfamiliar phrasing, or a different language can cause this. This does not imply safety.";
    details.hidden = false;
    opening.textContent = result.recognizedOpening ? "Yes" : "No";
    revision.textContent = result.revisionPattern ? "Detected" : "Not recognized";
    review.textContent = result.candidate ? "Recommended" : "Not triggered*";
  }

  function countChars() { charCount.textContent = `${input.value.length} / 2000 characters`; }
  form.addEventListener("submit", (event) => { event.preventDefault(); render(); });
  input.addEventListener("input", () => { countChars(); });
  document.querySelectorAll("[data-example]").forEach(button => {
    button.addEventListener("click", () => {
      input.value = examples[button.dataset.example] || "";
      countChars();
      render();
      input.focus({ preventScroll: true });
      document.getElementById("result-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  });
  countChars();
  render();
})();
