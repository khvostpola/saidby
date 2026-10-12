<p align="center">
  <img src="https://raw.githubusercontent.com/khvostpola/saidby/main/docs/img/logo.svg" width="260" alt="A pixel-art cassette tape labelled saidby">
</p>

# saidby

**Who said what, and when, on your own machine.**

saidby turns a recording (a phone call, a meeting, an interview) into a transcript with
speakers, timestamps and one audio track per person. It knows *your* names and terms, can put
names on voices (with consent), checks its own work, and never sends your audio anywhere. It is
a command-line tool and a Python library.

[![PyPI](https://img.shields.io/pypi/v/saidby)](https://pypi.org/project/saidby/)
[![CI](https://github.com/khvostpola/saidby/actions/workflows/ci.yml/badge.svg)](https://github.com/khvostpola/saidby/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/khvostpola/saidby/blob/main/LICENSE)

```
recording → ingest → transcribe → diarize → align → tracks → results folder
                          │            │
                  [bias + transplant]  [compare] [identify] [correct]     [ ] = only when you ask for it
```

How the stages fit, with diagrams: [how it works](https://github.com/khvostpola/saidby/blob/main/docs/how-it-works.md).

## What you get

```bash
saidby process call.m4a --out out/ --language es
```

```
out/call/
├── transcript.txt          [00:00:03] Ana Gómez: Hola, buenas tardes...
├── transcript.vtt          subtitles with the speaker in every cue
├── transcript.words.json   every word with start, end, confidence and speaker
├── diarization.rttm        standard "who spoke when"
├── speakers/ana.flac       one track per person, aligned with the original
├── corrections.jsonl       every spelling change, with the reason
├── manifest.json           which engines, models and versions produced it
└── logs/                   timings and counts, never your text
```

## Why saidby

- **It stays on your machine.** Processing runs offline. Models are downloaded once, on request.
  A test fails the build if anything but loopback is touched, and `--strict-offline` enforces it
  on every run.
- **It spells your world right.** Give it a YAML file with your people, your product names and
  your slang. A second recognition pass finds them and a strictly limited local LLM can fix what
  is left. Every change is logged and can be traced.
- **It names the speakers.** Voiceprints, created only with a recorded consent, put names on
  voices. A person split in two, or a wrong name, is one command to fix.
- **It checks itself, and lets you check it.** Two diarizers can vote; a review mode walks you
  through the doubtful spans and feeds your fixes back into the directory. A built-in bench
  (blind A/B arbitration, pre-set margins) lets you test the claims on your own recordings.

## Install

Linux or Windows, with [uv](https://docs.astral.sh/uv/getting-started/installation/) and `ffmpeg`
(`sudo dnf install ffmpeg`, `sudo apt install ffmpeg` or `winget install ffmpeg`).

Linux with an NVIDIA GPU (driver 580 or newer):

```bash
uv tool install "saidby[cuda]"
```

Windows with an NVIDIA GPU (driver 580 or newer). PyPI's PyTorch is a CPU build on Windows, so the
CUDA build comes from PyTorch's own index:

```powershell
uv tool install "saidby[cuda]" --index https://download.pytorch.org/whl/cu130 --index-strategy unsafe-best-match
```

No GPU, or to skip about 1 GB of CUDA libraries, on either system:

```bash
uv tool install saidby --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
```

Then:

```bash
saidby doctor                 # checks the machine and says how to fix what is missing
saidby models pull --all      # downloads the models, about 3.5 GB; the only step using the network
```

## Quick start

```bash
saidby init --language es                                          # once per folder: no more flags
saidby process call.m4a                                            # transcript, speakers, tracks in ./saidby/
saidby directory add-term Acme --variant akme                      # your people and terms
saidby review saidby/call                                          # fix the doubtful spans
```

On a terminal, `saidby process` shows what it is about to do and starts on Enter. When the run
ends it plays each voice, asks who it is, offers to remember what you chose, and says what is
left to review. Scripts get none of that: nothing is asked without a terminal, with
`--progress json`, with `--no-interactive`, or with `interactive = false` in `saidby.toml`.

<p align="center">
  <img src="https://raw.githubusercontent.com/khvostpola/saidby/main/docs/img/interactive.png" width="820" alt="A terminal running saidby process: the plan, the stage lines, the table of voices and the questions that name them">
</p>

The [getting started guide](https://github.com/khvostpola/saidby/blob/main/docs/getting-started.md)
walks through each step, including naming the speakers.

## Commands

```
Transcribe     process      recordings in, transcripts with speakers and tracks out
After a run    review       correct the spans the machine is unsure about
               enroll       store a voiceprint (needs recorded consent)
               speakers     show, rename and merge speakers without reprocessing
Set up         doctor       check this machine and say how to fix what is missing
               models       list, download and locate models
               directory    validate or create the directory file
Measure        eval         score a run; arbitrate differences between two systems blind
```

`saidby --help` and `saidby COMMAND --help` explain every option with examples. The full list is
in the [command reference](https://github.com/khvostpola/saidby/blob/main/docs/cli-reference.md).

## How well does it work?

On two real phone calls in Spanish, against WhisperX: the terms of the directory spelled right
85 to 88 % of the time against 12 to 20 %, speakers given the right name where WhisperX gives
anonymous labels, and speaker confusion of 2 to 3 % against 6 to 11 %. On plain word errors it is
a draw (ahead on one call, five words behind on the other). That is two calls and one language, so
read [the benchmarks](https://github.com/khvostpola/saidby/blob/main/docs/benchmarks.md), including
what they do not show.

A 15-minute call takes about 2 minutes with a laptop GPU (5 with the glossary and the LLM) and
about 6 to 7 on a 20-thread CPU.

## Status

Pre-alpha. It is developed and tested on Linux and Windows, on the CPU and on NVIDIA GPUs; the
command line and the output formats may still change between 0.x versions. It is a library and a CLI, not a service: there is no server and no
account. Models keep their own licenses (`saidby models licenses`).

## Documentation

- [Getting started](https://github.com/khvostpola/saidby/blob/main/docs/getting-started.md)
- [How it works](https://github.com/khvostpola/saidby/blob/main/docs/how-it-works.md): stages, glossary, voiceprints, privacy
- [Commands](https://github.com/khvostpola/saidby/blob/main/docs/commands.md) and the [reference](https://github.com/khvostpola/saidby/blob/main/docs/cli-reference.md)
- [Directory format](https://github.com/khvostpola/saidby/blob/main/docs/directory-format.md)
- [Glossary and LLM correction](https://github.com/khvostpola/saidby/blob/main/docs/glossary.md)
- [Review and comparison](https://github.com/khvostpola/saidby/blob/main/docs/review.md)
- [Evaluation](https://github.com/khvostpola/saidby/blob/main/docs/evaluation.md) and [benchmarks](https://github.com/khvostpola/saidby/blob/main/docs/benchmarks.md)
- [Troubleshooting](https://github.com/khvostpola/saidby/blob/main/docs/troubleshooting.md)

## Contributing and license

See [CONTRIBUTING.md](https://github.com/khvostpola/saidby/blob/main/CONTRIBUTING.md): contributions
are signed off under the Developer Certificate of Origin. Apache-2.0, see
[LICENSE](https://github.com/khvostpola/saidby/blob/main/LICENSE),
[NOTICE](https://github.com/khvostpola/saidby/blob/main/NOTICE) and
[MODEL_LICENSES.md](https://github.com/khvostpola/saidby/blob/main/MODEL_LICENSES.md).
