# Changelog

All notable changes are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
