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

CPU-only machines: `UV_TORCH_BACKEND=cpu uv sync`.

Fixtures: `uv run python tools/build_fixtures.py synthetic` regenerates the tone fixture.
