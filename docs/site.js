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
  const submitButton = form.querySelector('[type="submit"]');
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
      return;
    }
    if (!window.VOXGATE_DETECT || !window.VOXGATE_EXPLAIN) {
      panel.dataset.state = "empty";
      title.textContent = "Analyzer did not load";
      description.textContent = "Reload the page. Nothing was processed remotely.";
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
    } catch (error) {
      title.textContent = "Could not inspect this text";
      description.textContent = "This input is outside the supported format. No action was taken.";
      details.hidden = true;
      evidence.hidden = true;
    }
  }
  submitButton.type = "button";
  submitButton.addEventListener("click", render);
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
})();
