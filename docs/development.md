# Development

```bash
uv sync --all-extras
uv run saidby models pull asr:tiny
uv run pytest                 # sockets are blocked except loopback
uv run pytest -m gpu          # needs a CUDA device
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run reuse lint
uv run python tools/third_party_notices.py --check
```

CPU-only machines: `UV_TORCH_BACKEND=cpu uv sync --extra pyannote --extra eval` (the `cuda` extra
adds about 1 GB of NVIDIA libraries that a CPU machine does not need).

Fixtures: `uv run python tools/build_fixtures.py synthetic` regenerates the tone fixture.

## Windows

The same commands work in PowerShell once `uv` and ffmpeg are installed (`winget install ffmpeg`,
then open a new terminal). Type-check both systems from either one:

```bash
uv run mypy && uv run mypy --platform win32
```

Calls into Windows APIs live inside literal `if sys.platform == "win32":` blocks and everything
else that differs by system goes through `saidby.runtime.host`; `tests/unit/test_portability.py`
keeps text files UTF-8 with LF and shell quoting inside `host`. `tools/screenshot.py` drives a pty
and only runs on Linux. CI tests on Ubuntu and Windows; there, tests marked `needs_ffmpeg` fail
instead of skipping (`CI_REQUIRE_FFMPEG=1`).

## Generated documentation

One file is generated and checked by the tests, so it cannot go stale:

```bash
uv run python tools/gen_cli_reference.py   # docs/cli-reference.md, from the CLI's own help
```

Diagrams are Mermaid blocks inside the Markdown, which GitHub draws in the reader's theme.

The tests also check that every link, image and anchor in the documentation resolves and that
every `saidby ...` command shown in a code block exists with the options it uses.
