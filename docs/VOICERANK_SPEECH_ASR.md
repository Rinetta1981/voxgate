# VoiceRank: Offline speech recognition and action-selection audit

## Research scope

This batch tests a *speech-recognition pipeline* on the existing eight matched
VoiceRank clips. It measures how well the locally run Whisper tiny.en model
transcribes slow/fast versions of the **same text**, then optionally measures
how the existing local Qwen text model selects from an inert, fixed catalog
when shown either (a) exact reference transcripts or (b) Whisper transcripts.

**It does not test whether an audio-capable AI model treats a voice as
socially authoritative.** The text model never receives audio. Any observed
variation may be due to Whisper transcription or nondeterministic model output.
The four prompts are researcher constructed, and the sample is too small for
generalization, as in earlier VOXGATE pilot stages.

## Install once on Apple Silicon macOS

The Homebrew package is currently named `whisper.cpp` (with a dot):

```bash
brew install whisper.cpp
mkdir -p ~/Desktop/voxgate-models
curl --fail --location --retry 2 \
  --output ~/Desktop/voxgate-models/ggml-tiny.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin
```

These are public third-party downloads, not API calls. `whisper-cli` is the
actual command installed by Homebrew. Whisper tiny.en is approximately 75 MiB;
allow sufficient disk capacity for the Homebrew dependencies. If Homebrew is
not installed, install it from https://brew.sh/ before the commands above.
The experiment script itself downloads **nothing**.

## Run from an activated VOXGATE virtual environment

```bash
cd ~/Desktop/voxgate
python -m unittest core.test_voicerank_speech -v
python voicerank_speech_benchmark.py --check
python voicerank_speech_benchmark.py --run-asr
```

The ASR pass produces `~/Desktop/voxgate-voice-asr-reports/voicerank_asr_trials.csv`
and `voicerank_asr_summary.json` with word error rates (WER) and normalized
exact-match counts. The script verifies the original manifest and audio hashes,
resamples to 16 kHz mono PCM16 in a temporary directory, then calls only your
local installed Whisper binary. It never changes the eight originals.

### Optional downstream text-model run

If Ollama is open, and `qwen2.5:0.5b` is already installed:

```bash
python voicerank_speech_benchmark.py --run-model
```

This reuses the saved ASR output without repeating recognition and performs at
most 16 localhost Ollama text-model requests. No simulated action is ever
executed. Output: `voicerank_text_decisions.csv` and a summary JSON.

The *fixed catalog* comprises the four original action descriptions (not case-
specific labels), plus the `HOLD` option. A 'correct' selection means it matches
the transcript's nominal action, not that the speaker has authorized execution.
There is no ability to send email, access files, or perform transactions.

## Experimental limits and planned next step

- Two speaking rates with **one synthesizer voice**, not an authority manipulation.
- Four matched phrases, not a representative voice or language sample.
- Tiny.en accuracy may be poor on short speech; WER can exceed 100%.
- Pure-Python linear sample-rate conversion is used for reproducibility; use
  a quality-controlled antialiasing resampler in a formal study.
- Single local model; no actual end-to-end acoustic perception or action tools.

A publishable VoiceRank safety study needs new consent/authorization stimuli,
validated acoustic manipulations, independent authority ratings, and an
**audio-capable** model benchmark that uses the original signals directly.

## Privacy and reproducibility

This script uses no paid APIs, stores only local result files and temporary
PCM audio, and limits network interactions to local Ollama (when requested).
Installing Homebrew or downloading model weights does contact public package
hosts, as expected. Do not claim these data validate causal vocal authority.
