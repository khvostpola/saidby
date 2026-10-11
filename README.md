# saidby

Offline-first diarized transcription: a command-line tool and Python library that
turns any recording into a transcript with speakers, timestamps, glossary-aware
spelling and one audio track per speaker.

Status: pre-alpha. Version 0.4.0 transcribes with faster-whisper, diarizes with Nemotron-3,
aligns words to speakers, renders one aligned audio track per speaker and names speakers by
voiceprint (with recorded consent). With a directory it also spells your names and terms
correctly (biased pass, transplant and an optional local LLM, all logged). A second
diarizer can be compared on the same audio, and `saidby review` walks through the uncertain
spans so you can type the right text and feed new spellings back into the directory.

## Install

```bash
uv tool install saidby
```

For machines without an NVIDIA GPU, avoid downloading the CUDA build of PyTorch:

```bash
uv tool install saidby --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
```

Requirements: `ffmpeg` on the PATH and, for GPU use, an NVIDIA driver 580 or newer.

## Quick start

```bash
saidby models pull --all          # one-time download, the only step that uses the network
saidby process call.m4a --out out/ --language es
```

Each recording gets its own folder under `out/`:

| File | Content |
|---|---|
| `manifest.json` | Engines, models and versions per stage, speakers, timings |
| `transcript.txt` | `[HH:MM:SS] Speaker: text` |
| `transcript.vtt` | WebVTT with `<v Speaker>` voice tags |
| `transcript.words.json` | Word-level transcript with timestamps and speaker labels |
| `corrections.jsonl` | Every glossary change, accepted or rejected, with its reason |
| `diarization.rttm` | Standard "who spoke when" |
| `speakers/<id>.flac` | One track per speaker, same length as the original, silent elsewhere |
| `logs/run.log`, `logs/telemetry.jsonl` | Local log and closed-field telemetry |

To name speakers, enroll them once and pass the directory:

```bash
saidby enroll out/call --speaker SPEAKER_00=ana --directory directory.yaml \
  --consent-source "signed form" --consent-declared-by "Ana Gomez"
saidby process next-call.m4a --out out/ --directory directory.yaml
```

See [docs/directory-format.md](docs/directory-format.md).

A failed run keeps `.work/` so the next run resumes from the last finished stage;
`--keep-intermediates` keeps it on success too. See [docs/cli.md](docs/cli.md).

## Models

Models are never bundled and are only downloaded by an explicit command:

```bash
saidby models list
saidby models pull --all
```

Processing always runs offline (`HF_HUB_OFFLINE=1`). A Hugging Face token (`HF_TOKEN`)
is needed only for gated models such as `pyannote/speaker-diarization-community-1`;
if the conditions have not been accepted, the error shows the URL where to accept them.

## Privacy

- No telemetry leaves the machine. Logs and telemetry are written locally and never
  contain transcript text, names, glossary terms or voiceprints.
- A test suite blocks any non-loopback network access during processing.

## License

Apache-2.0. See [LICENSE](LICENSE), [NOTICE](NOTICE) and
[MODEL_LICENSES.md](MODEL_LICENSES.md). Contributions are accepted under the
[Developer Certificate of Origin](CONTRIBUTING.md).
