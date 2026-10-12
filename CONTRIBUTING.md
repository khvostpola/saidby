# Contributing

## Setup

```bash
uv sync --all-extras
uv run saidby models pull asr:tiny
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run reuse lint
```

GPU tests are skipped by default; run them on a CUDA machine with `uv run pytest -m gpu`.
On a machine without a GPU, install the CPU build of PyTorch without the CUDA extra:
`UV_TORCH_BACKEND=cpu uv sync --extra pyannote --extra eval`.

## Rules

- Everything in the repository is in English: code, docs, issues, commits.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/), title only,
  50 characters when possible and never more than 72.
- Sign off every commit (Developer Certificate of Origin): `git commit -s`. To fix a missing
  sign-off, run `git rebase --signoff main` and force-push your branch. There is no CLA.
- Contributions are licensed under Apache-2.0.
- Never commit private recordings, voiceprints, transcripts of real people or model weights.
  Audio is only allowed under `fixtures/`, with a recorded license and source.
- Do not commit configuration files of AI tools or assistants.
- Add a line to `CHANGELOG.md` under `Unreleased` for every user-facing change.
- Telemetry and logs must never contain transcript text, names, glossary terms or
  voiceprints; the telemetry schema is a closed list.

## Translating the messages

User-facing text goes through `_()` (and `ngettext()` for plurals) from `saidby.i18n`; help
texts, JSON, logs and files stay in English. After adding or changing a message, update the
catalogs and translate what is new:

```bash
uv run python tools/i18n.py update es   # refresh src/saidby/locale/es/LC_MESSAGES/saidby.po
# translate the empty entries in that file, then
uv run python tools/i18n.py compile     # rebuild the .mo files (they are committed)
```

A new language is `uv run python tools/i18n.py update xx` followed by the same steps. The test
suite fails when a message has no translation or a `.mo` is stale, and checks that placeholders
such as `{n}` survive.

## Developer Certificate of Origin

By signing off you certify the statements of the
[DCO 1.1](https://developercertificate.org/): that you wrote the contribution or have the
right to submit it under the project's license.

## Pre-commit (optional)

```bash
uv tool install pre-commit
pre-commit install
```
