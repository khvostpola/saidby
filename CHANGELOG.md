# Changelog

All notable changes are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Documentation: a getting-started guide, a how-it-works page with Mermaid diagrams (GitHub draws them in the reader's theme), a pixel-art cassette logo, a commands guide,
  troubleshooting, benchmarks with their limits, and a generated command reference. Tests keep
  links, anchors, documented commands and diagrams in sync.
- `saidby --help` is grouped by what you are trying to do, `-h` works everywhere, every option and
  argument is described, and commands show examples.

### Fixed
- `saidby.toml`: `compute_type` under `[asr]` was rejected. The file now has documented sections
  (`saidby`, `asr`, `diarizer`, `identify`, `glossary`, `llm`), unknown keys are errors that name
  the key, and a relative `directory` is resolved against the file.

## [0.4.1] - 2026-10-11

### Changed
- CUDA 12 cuBLAS moved to the `cuda` extra (`uv tool install 'saidby[cuda]'`). The default install no
  longer pulls about 1 GB of NVIDIA libraries that CPU machines cannot use.
- `saidby doctor` rewritten: one line per check with the command that fixes it, a driver check,
  a check that PyTorch and CTranslate2 can both use the GPU, `--smoke` and `--device`.

### Fixed
- With a CPU build of PyTorch and an NVIDIA GPU present, `--device auto` chose the GPU and the
  diarizer failed. It now falls back to the CPU and records the reason in `manifest.json`.

## [0.4.0] - 2026-10-11

### Added
- `process --compare NAME`: runs a second diarizer, records the agreement (0.25 s margin) and
  the disagreement spans in `manifest.json` and telemetry.
- `saidby review`: walks through disagreement spans, rejected LLM proposals and low-confidence
  words; corrections and speaker changes are logged, decisions are remembered, and new spellings
  can be added to the directory as variants.
- `process --bias-mode windows` (experimental): biased pass only around likely terms.
- `process --deterministic`: temperature 0 and no conditioning on previous text; three full runs gave identical words and timestamps.
- `saidby eval` (extra `eval`): scoring against a hand-made reference (WER, terms, diarization) and blind arbitration of the spans where two runs disagree, with typed corrections and a pre-registered non-inferiority margin.

## [0.3.0] - 2026-10-11

### Added
- Glossary: biased second pass with the directory's names and terms (`asr_bias`), transplant of
  the terms into the plain transcript, deterministic dialect unification, and `--no-bias` and
  `--no-transplant`.
- Optional LLM correction (`--correct`) through a local `llama-server` subprocess or any
  OpenAI-compatible endpoint (`--llm-url`, loopback only unless `--allow-remote-llm`), with
  guardrails enforced in code and prompts for Spanish, English and Portuguese.
- `corrections.jsonl` and a `source` on every word; `glossary` block in `manifest.json`.

## [0.2.0] - 2026-10-11

### Added
- People: directory format with JSON Schema, `saidby directory validate|schema|init`,
  `saidby enroll` with recorded consent (exit code 5 without it) and comment-preserving,
  backed-up writes of the directory and `consent.yaml`.
- Speaker identification by voiceprint with one-to-one assignment, a 0.5 score threshold and a
  3 s speech minimum; a built-in WeSpeaker ResNet34 that matches pyannote's embeddings
  (cosine above 0.999), so pyannote.audio stays optional.
- `saidby speakers show|map|merge` to rename and merge speakers without reprocessing.
- `process --directory`, `--no-identify` and `--identify-threshold`.

### Fixed
- Re-running with different speaker names no longer leaves stale tracks behind.

## [0.1.0] - 2026-10-11

### Added
- `saidby process`: ingest, transcription (faster-whisper large-v3), diarization (Nemotron-3, or
  pyannote community-1 with the `pyannote` extra), word-to-speaker alignment, aligned
  per-speaker FLAC tracks, `transcript.txt`, `transcript.vtt`, `transcript.words.json`,
  `diarization.rttm` and `manifest.json`.
- Resume by stage from `.work/`, several inputs per run with models loaded once, progress as
  human lines or JSON events, `--strict-offline`.
- Public-corpus fixtures (Multilingual LibriSpeech, CC BY 4.0) with four channel profiles.

## [0.0.1] - 2026-10-10

### Added
- CLI skeleton: `saidby --version`, `saidby doctor` and `saidby models list|pull|licenses|path`.
- Revision-pinned model registry with license and attribution data.
- Offline runtime guard, network audit guard and closed-field telemetry schema.
