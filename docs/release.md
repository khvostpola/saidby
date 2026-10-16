# Releasing

```bash
uv run python tools/release.py X.Y.Z
```

The command refuses to start unless you are on a clean `main` that matches `origin/main`, the
version is newer than the current one, the tag `vX.Y.Z` does not exist locally or on `origin`, and
`CHANGELOG.md` has notes under `Unreleased` and no `X.Y.Z` section yet. It then moves those notes
under `## [X.Y.Z] - date`, runs `uv version X.Y.Z`, runs the lint, type and test gates, builds the
wheel and checks that it reports `X.Y.Z`. It prints a summary table and asks for confirmation;
only then does it commit (`chore: release X.Y.Z`, signed off), create the signed tag `vX.Y.Z` and
run `git push origin main --follow-tags`. Any failure or a "no" restores the three files.
`--dry-run` stops at the table, `--skip-checks` skips the gates and the build, and `--yes` skips
the question (required without a terminal).

Then approve the `pypi` environment deployment, a required-reviewer gate. The workflow publishes
with PyPI trusted publishing; no tokens are stored.

One-time setup: a pending trusted publisher on PyPI for project `saidby`, owner `khvostpola`,
repository `saidby`, workflow `release.yml`, environment `pypi`.

## Windows before a release

CI runs the suite on Windows and smokes the wheel there, but the GPU, the console and
`llama-server` only get checked by hand. On a Windows machine with an NVIDIA GPU, from the
release commit:

1. `uv build`, then install the wheel into a fresh tool environment (PowerShell does not expand
   `*`, so name the file):
   `uv tool install "saidby[cuda] @ .\dist\saidby-X.Y.Z-py3-none-any.whl" --index https://download.pytorch.org/whl/cu130 --index-strategy unsafe-best-match`
2. `saidby models pull --all`, then `saidby models pull asr:tiny` (the smoke test transcribes with
   the tiny recognizer, which `--all` does not pull), then `saidby doctor --smoke --device cuda`:
   the `platform` row says Windows, `cuda` is `ok` and the smoke test runs on `cuda`.
3. `saidby process fixtures\conversations\test\test-conv-01.flac` in Windows Terminal: the plan,
   the coloured stage lines with CPU or GPU usage, the voices, example names; then, from `cmd`,
   `saidby --ui-lang es process fixtures\conversations\test\test-conv-01.flac --no-interactive > out.txt 2>&1`.
   Without a terminal everything goes to stderr, so `2>&1` is what fills the file; the Spanish
   messages carry accents, which must read back intact as UTF-8.
4. `saidby models pull llm:qwen3.5-9b-q4`, then the same `process` with `--correct --term Acme`
   (correction needs terms) and a `llama-server` from a llama.cpp Windows release on `PATH` (or
   `SAIDBY_LLAMA_SERVER`): the only real exercise of the helper process on Windows.
5. `saidby review` on that folder, with `p` playing a span through `ffplay`.
6. Once in conhost (`cmd`) and once in PowerShell 5.1: colours and the progress line still draw.
7. On a machine with Smart App Control on: Python from python.org, `py -m venv`,
   `pip install saidby`, `python -m saidby doctor --smoke`. Record the outcome in the release
   notes if it changed.
