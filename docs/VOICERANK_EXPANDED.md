# VoiceRank expanded listening study (version 2)

## Purpose and limitations

This is a **local, exploratory perception study**, not a test of AI-agent permission decisions. It uses the **same eight audio recordings** as the original VoiceRank pilot (four matched utterances, 155 and 210 nominal WPM, same macOS synthesis voice). There is **no need to regenerate the recordings**. The original pilot page, data, and analysis remain intact.

**Independent variable:** nominal speaking rate. **Primary dependent variable:** listener-rated perceived authority (1–5). **Secondary:** clarity and urgency (1–5). Other voice properties may change as a by-product of TTS rate changes; the acoustic manipulation has not been validated. Synthesized speech does not itself establish socially authoritative personae.

## Installation / running

From `~/Desktop/voxgate` with your `.venv` active, unzip the supplied update. No new Python packages, subscriptions, API keys, or model downloads are required. Check the existing generated audio:

```bash
python generate_voicerank_stimuli.py --check
```

**Offline tests (work without Django):**

```bash
python -m unittest core.test_voicerank_study -v
```

**Django integration tests (requires your existing Django installation):**

```bash
python manage.py test core.test_voicerank_study_django -v 1
```

Start or restart the existing local development server and visit `http://127.0.0.1:8000/voice/study/`.

## Study flow

- Before starting, read the local information notice and explicitly opt in. **Do not recruit outside participants without appropriate ethics review and a suitable approved consent process.**
- A randomly generated **pseudonymous participant code** and one of **eight pre-specified counterbalanced schedules** are created for your browser session. Identical prompt pairs are separated (the two versions of a prompt are never adjacent).
- Across the eight possible schedules, each of the four prompts appears twice at each first-block position, and each speaking rate appears first for each prompt in four schedules. **Random selection does not guarantee balance in a realized sample**: inspect the exported assignment counts.
- Rate all eight stimuli. Export a single CSV for that completed session. **Do not submit multiple exports for the same participant**, because the aggregator rejects repeated participant codes.
- To run a new participant, choose **Discard session and start again** after exporting. That creates a new pseudonymous code. Do not allow one person to create multiple independent-participant records.
- Local Django sessions can be lost or reset; files are not uploaded automatically. Each export includes participant code, assignment, audio fingerprint, trial order, and rating metadata. The export contains no fields for name, IP or email. Django's development web server may retain ordinary request logs.

## Aggregate analysis

After collecting **one complete file per independent participant** (e.g. in a private local directory), run:

```bash
python analyze_voicerank_study.py ~/Downloads/voicerank_study_*.csv --output-dir ~/Desktop/voxgate-voice-study-reports
```

The analyzer rejects malformed trial sets, repeated participant codes, inconsistent order, missing ratings, and **different audio fingerprints**. It creates `summary.json` and `participant_summary.csv`, with one independent analysis unit per participant. It reports, separately for authority, clarity, and urgency, average listener ratings for slower and faster speech and the mean **within-participant** faster-minus-slower difference averaged across four matched prompts.

Do not enter the original `voicerank_pilot.csv` in this command: it is a legacy single-session format and remains analyzable with the older `analyze_voicerank.py` script. You can retain it as preliminary background, but should not silently mix it with v2 participant data.

This module reports **descriptive statistics**, with no p-values, causal inference beyond the narrow controlled comparison, or claims of AI-agent authorization performance. A future multi-participant study needs documented sampling, ethics review, acoustic measurements, preregistered hypotheses, inter-stimulus controls and appropriate statistical modeling for repeated measures. **Do not publicly expose this local-only Django app as a participant-recruitment website.**

## Future VOXGATE research

After a validated manipulation check, test whether matched audio features influence **audio-capable models' simulated permission decisions**, using the same authorization policy and available actions. Compare against transcript-only and unmodified-audio controls. This distinct agent experiment has not yet been run.
