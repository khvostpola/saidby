# Changelog

All notable changes are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
