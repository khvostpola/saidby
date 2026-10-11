# saidby

Offline-first diarized transcription: a command-line tool and Python library that
turns any recording into a transcript with speakers, timestamps, glossary-aware
spelling and one audio track per speaker.

Status: pre-alpha. Version 0.0.1 ships the CLI skeleton (`--version`, `doctor`,
`models`). The processing pipeline arrives in 0.1.0.

## Install

```bash
uv tool install saidby
```

For machines without an NVIDIA GPU, avoid downloading the CUDA build of PyTorch:

```bash
uv tool install saidby --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
```

Requirements: `ffmpeg` on the PATH and, for GPU use, an NVIDIA driver 580 or newer.

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
