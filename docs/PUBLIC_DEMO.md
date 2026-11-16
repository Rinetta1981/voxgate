# VOXGATE public demo

This directory is a GitHub Pages site. `index.html`, `site.css`, `detector.js`, and `site.js` are a **read-only, browser-only** demonstration of WaitWise V4 candidate instruction-revision detection. The source detector is `core/analysis_v4.py` at repository commit `53283b0`.

## Publishing

On GitHub, open **Settings > Pages**, choose **Deploy from a branch**, select `main` and `/docs`, then **Save**. After GitHub reports the Pages URL, check that `https://rinetta1981.github.io/voxgate/` loads and the examples classify as expected. The DNS/site URL is only a suggested path until GitHub Pages confirms it.

## Boundaries

- The input is analyzed entirely in JavaScript in the browser. There are no web requests, analytics or storage performed by the demo code; GitHub may still maintain normal website access logs.
- No AI model runs in the browser or on a server, no speech recognition is performed, no user study data are collected, and no external tools/actions are available.
- Results are flags for possible human review **not** proof of speaker permission, correctness, or safety.
- It intentionally does not expose the Django research server, Ollama, local reports, participant CSVs or audio recordings.
- If the exact V4 Python detector changes later, update the JS port and re-run the paired tests; do not describe V4 as a validated safety gate.

## Experimental explanation layer

The public page also includes `interpret.js`, an exploratory, transparent text-span explanation layer. It identifies possible opening instructions, cue words, and subsequent command-like text using additional heuristics. This is **not WaitWise V4**, is not a language model, and has not been validated as a safety or semantic understanding mechanism. The frozen V4 baseline and published V3/V4 numbers are unaffected.

The public analysis can flag likely revisions or state that a sentence is outside its supported patterns. It cannot reliably derive final intent, authorize actions, or handle arbitrary natural language.
