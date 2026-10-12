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

## Generated documentation

Two files are generated and checked by the tests, so they cannot go stale:

```bash
uv run python tools/gen_cli_reference.py   # docs/cli-reference.md, from the CLI's own help
uv run python tools/diagrams.py            # docs/img/*.svg
```

The tests also check that every link, image and anchor in the documentation resolves and that
every `saidby ...` command shown in a code block exists with the options it uses.
