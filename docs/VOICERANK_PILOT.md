# VoiceRank: local speech-perception pilot (v1)

## Purpose and status

This is the first **audio-based** VOXGATE component. It generates eight speech
samples using the Mac's built-in text-to-speech (`say`) and WAV converter
(`afconvert`), and displays them in a blinded, randomized local web
questionnaire. No API key, cloud provider, language model, real agent, or tool
execution is used.

**This is a *manipulation-check pilot*, not a demonstration of AI-agent safety.**
The research question is whether altering the *speaking rate* of one synthetic
voice changes a listener's ratings of perceived authority, clarity, and
urgency. Do not assume slower or faster speech is more authoritative. A
language model that reads only the transcript cannot infer these vocal
characteristics.

## Install / run on the Mac

From the project directory with the virtual environment active:

```bash
python generate_voicerank_stimuli.py
python -m unittest core.test_voicerank -v
python manage.py test core.test_voicerank_django -v 1
```

The first command creates eight WAV files and a validated metadata manifest in
`~/Desktop/voxgate-voice-stimuli/`. The built-in macOS synthesizer's default
voice is used in both speaking-rate conditions, so you don't need to select
or download any additional voice. Existing audio won't be silently overwritten.
The generator does not use shell interpolation or execute transcript text as
commands.

To check the audio at any time, use:

```bash
python generate_voicerank_stimuli.py --check
```

With the Django development server running, open:

```
http://127.0.0.1:8000/voice/
```

Play each clip and rate **perceived authority, clarity, and urgency** from 1–5.
The order is randomized per browser session, and the text, audio rate and
condition are not displayed during rating. After completing the eight clips,
click **Export anonymized pilot CSV**. Downloaded ratings can be summarized by:

```bash
python analyze_voicerank.py ~/Downloads/voicerank_pilot.csv
```

Your browser may put the export in another folder; adjust the path if needed.
The ratings are held in Django's local development session store (on your Mac),
identified by a browser session cookie. They are not a durable research log;
resetting the study or losing the session cookie can make unexported scores unavailable. Audio remains only on
your Mac in the named Desktop folder. The speech files are not added to GitHub.

## Controlled design

- **Stimulus set:** four fixed, plain-language action requests.
- **Within-item factor:** synthesized speaking rate, 155 vs 210 words/minute.
- **Matched features:** exact text and the *same installed TTS voice* for both
  conditions; synthesis still changes duration and may alter other prosodic
  details.
- **Primary rating:** perceived authority, 1–5.
- **Secondary ratings:** clarity and urgency, 1–5.
- **Presentation:** randomized clip order, blinded condition labels.
- **Analysis:** descriptive within-item faster-minus-slower authority difference
  across four matched texts, not inferential statistics.

Ratings from one listener over four prompts are *not* four independent
participants. This design has no recruited sample, independent annotation,
acoustic validation, empirical estimate of true vocal authority, or tests of
whether any AI agent would comply with unauthorized instructions.

## Research improvements needed before publication

1. Create an ethics/consent protocol and recruit independent listeners for a
   preregistered manipulation check; record and manage participant consent
   and data responsibly. Don't expose this local demo publicly.
2. Measure actual acoustics (duration, F0, intensity, accent/quality) and
   isolate and counterbalance additional properties such as intensity,
   pitch contour, and speech style. Speaking rate alone is not authority.
3. Generate enough unique utterances, vary voice identities systematically,
   preregister hypotheses and independent train/development/test partitions,
   and analyze repeated measures without pseudo-replication.
4. Test an **audio-capable** local model in isolated, simulated permission
   scenarios with identical words, authorization state and available actions.
   Compare matched audio stimuli to transcript-only and unmanipulated controls.
5. Show effects on *unauthorized decisions*, not merely on listener ratings;
   include false denials, safe holds, correctness, model reliability and
   uncertainty intervals.

**Safety:** The local website and test recordings do not execute file actions,
bookings, emails, or payments. The new VoiceRank view is intentionally disabled
when Django `DEBUG=False`, until a reviewed deployment design is available.
