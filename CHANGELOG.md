# Changelog

All notable changes are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `saidby process -i` shows a plan before running (glossary, language, speakers, output and extra
  terms, each with where the value comes from) and waits for one key: Enter to start, `t` to add
  terms for this recording, `e` to change a value, `q` to quit. It asks only what nothing else
  set (the language). It needs a terminal and the human progress output.
  When the run ends it walks through each finished folder: it plays and names the voices, offers
  to store voiceprints (default no, with consent per person), offers once to save the terms you
  added into the glossary and the language, glossary and output you chose into `saidby.toml`
  (comments are kept and a backup is made), and closes with a summary and the equivalent
  command. Each folder's `manifest.json` records an `interactive` edit.
- `saidby enroll -i FOLDER` goes through the voices that already have a name in the directory and
  asks, for each person, whether they agreed to have their voiceprint stored. It asks how consent
  was given once and who declared it (the person by default). Without consent nothing is stored
  and no record is written; nothing is changed until you confirm the summary. It needs a
  terminal; `--speaker` still works without one, and `--speaker` is no longer required when `-i`
  is used.
- `saidby speakers map -i FOLDER` lists the voices of a run (speech, turns, a stretch where nobody
  else talks), plays a sample of each one with `ffplay` and asks a name for each, completing
  people from the directory with Tab. Nothing is written until you confirm. It needs a terminal;
  `--set` still works without one. `saidby doctor` warns when `ffplay` is missing.
- `saidby enroll --speaker LABEL=PERSON` takes a person's id or name, and tells you to run
  `saidby directory add-person` when the person is not in the directory yet.
- `saidby speakers map --set LABEL=PERSON` finds the person by id, name or alias, and a new name
  is offered for the directory: it asks on a terminal, or use `--add-missing`. Ids made from names
  no longer break on accents.
- The pixel-art cassette, drawn in the terminal with half-block characters. `saidby` with no
  arguments shows it with the models, the device from the last run, the glossary and the
  configuration in use; `saidby process` shows a three-row version. Plain text (or nothing)
  without true color, on a narrow terminal, with `NO_COLOR`, in a pipe, or with `--progress
  json` or `none`.
- A run that leaves something to do now ends by saying what and the command for it: `name`
  (speakers without names, `saidby speakers map`) and `review` (doubtful spans, `saidby review`
  with how many). Nothing is printed when there is nothing to do, with `--progress json` or
  `none`, or after a failure.
- The live line of a stage now says when it is loading its model, then what it is doing, and
  shows how much of the GPU memory (or the CPU) is in use. `--progress json` gains a
  `stage.loading` event.
- Every run starts with a `device` line (GPU or CPU, and why), and on a terminal the start-up
  shows `starting` and `device` live lines instead of looking frozen while PyTorch loads and the
  GPU is checked. `--progress json` gains `run.start` and `device` events.
- `manifest.json` says why the CPU ran (`device.reason`: `requested_cpu`, `no_gpu` or
  `gpu_unusable`). Every run and `saidby doctor` also remember the last device check in
  `~/.cache/saidby/device.json` (a forced `--device cpu` is not remembered, because it says
  nothing about the machine), so the banner can show it without probing the GPU.
- Message translation support: `--ui-lang` (or `SAIDBY_UI_LANG`, or your system language) picks
  the language of messages, with English for anything not translated. No translations ship yet.
- `out` setting (`[saidby] out`, `SAIDBY_OUT`) with `saidby/` as the default, so
  `saidby process call.m4a` works without flags.

- `saidby init` creates `saidby.toml`, `directory.yaml` and `consent.yaml` in the current folder
  (or `~/.config/saidby/` with `--global`) after asking the language and whether to reuse the
  global glossary. It never overwrites a file that is already there. `~` now works in paths
  inside configuration files.
- `saidby directory add-person` and `saidby directory add-term` edit a directory file without
  opening it, keeping comments and making a backup. Ids are made without accents:
  `saidby speakers map` now turns "Gómez" into `gomez` instead of `g-mez`.
- `--term` (repeatable, also `[glossary] terms` and `SAIDBY_TERMS`): terms for one run only,
  used by the bias pass, the transplant and `--correct` like directory terms, and never saved.
- Several directory files at once: `--directory` can be repeated and `directory` in
  `saidby.toml` can be a list (shared file under a project one). The nearest file wins, and the
  manifest lists every file. `saidby enroll`, `saidby review` and `saidby speakers map` fall back
  to the configured directory when `--directory` is not given.

### Changed
- `saidby speakers show` prints a table (speaker, name, speech, how it was named, track); the JSON
  it used to print is now `--json`, and gains the `track` of each speaker.
- The `name:` line at the end of a run suggests `saidby speakers map -i FOLDER`.
- Errors print as `error: message  [id · exit N]` instead of `error: ClassName: message`. The id
  (`consent_missing`, `model_unavailable`...) and the number are stable, and are the way to look
  an error up in the docs.
- Stage lines are easier to read: steps have plain names (`audio`, `transcript`, `terms`,
  `speakers`, `names`), the speed is written out ("9.8x faster than the audio" instead of
  `0.103x`), and the quick steps (`transplant`, `align`, `tracks`, `outputs`) are counted in the
  `done` line instead of getting a line each. The `[total]` line uses the same wording.
  `logs/run.log`, the manifest and `--progress json` still list every step by its id.
- A voiceprint is only used to name speakers when the `consent.yaml` next to the file that
  holds it has a record for that person. Voiceprints without one are skipped and reported in
  the manifest (`voiceprints_skipped`).
- `--out` is no longer required.
- The global config file (`~/.config/saidby/config.toml`) is no longer ignored when a
  `saidby.toml` exists: the two are merged key by key and the project file wins. saidby now
  looks for `saidby.toml` in the current folder and its parents up to your home folder.
  `--config FILE` still means exactly that one file.

### Fixed
- The live status line no longer wraps (and leaves stray text behind) on a narrow terminal: it is
  cut to the terminal width.
- `saidby review` no longer loses the edits you already made when a later answer fails (an
  unknown `@speaker`) or you press Ctrl+C: they are saved before the command stops.

## [0.4.4] - 2026-10-11

### Added
- Every run ends with a `[total]` line: duration, start and finish times, and the speed over all
  the audio (with `--progress json`, a `run.end` event with the same data).

## [0.4.3] - 2026-10-11

### Fixed
- Progress no longer looks frozen: on a terminal, a stage that takes more than a moment shows what
  it is doing and the elapsed time, and the JSON progress gains a `stage.start` event. The model
  weights progress bar that leaked into the output is gone.

## [0.4.2] - 2026-10-11

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
