# Releasing

1. Move the `Unreleased` notes in `CHANGELOG.md` under `## [X.Y.Z] - date`.
2. `uv version X.Y.Z`
3. `git commit -s -m "chore: release X.Y.Z"`
4. `git tag -s vX.Y.Z -m "saidby X.Y.Z"` and `git push origin main --follow-tags`.
5. Approve the `pypi` environment deployment. The workflow publishes with PyPI trusted
   publishing; no tokens are stored.

One-time setup: a pending trusted publisher on PyPI for project `saidby`, owner `khvostpola`,
repository `saidby`, workflow `release.yml`, environment `pypi`.

## Windows before a release

CI runs the suite on Windows and smokes the wheel there, but the GPU, the console and
`llama-server` only get checked by hand. On a Windows machine with an NVIDIA GPU, from the
release commit:

1. `uv build`, then install the wheel into a fresh tool environment (PowerShell does not expand
   `*`, so name the file):
   `uv tool install "saidby[cuda] @ .\dist\saidby-X.Y.Z-py3-none-any.whl" --index https://download.pytorch.org/whl/cu130 --index-strategy unsafe-best-match`
2. `saidby doctor --smoke --device cuda`: the `platform` row says Windows, `cuda` is `ok` and the
   smoke test runs on `cuda`.
3. `saidby process fixtures\conversations\test\test-conv-01.flac` in Windows Terminal: the plan,
   the coloured stage lines with CPU or GPU usage, the voices, example names; then the same run
   with `--no-interactive` redirected to a file, which must be readable UTF-8.
4. The same `process` with `--correct` and a `llama-server` from a llama.cpp Windows release on
   `PATH` (or `SAIDBY_LLAMA_SERVER`): the only real exercise of the helper process on Windows.
5. `saidby review` on that folder, with `p` playing a span through `ffplay`.
6. Once in conhost (`cmd`) and once in PowerShell 5.1: colours and the progress line still draw.
7. On a machine with Smart App Control on: Python from python.org, `py -m venv`,
   `pip install saidby`, `python -m saidby doctor --smoke`. Record the outcome in the release
   notes if it changed.
