# Fixtures

- `synthetic/`: a deterministic two-speaker tone recording and its RTTM, rebuilt with
  `uv run python tools/build_fixtures.py synthetic`. Dedicated to the public domain (CC0-1.0).
- `conversations/`: four two-speaker Spanish conversations (two in `dev`, two in `test`, with
  no speakers in common) built from Multilingual LibriSpeech clips, each in a clean version
  and four channel profiles (`phone-pstn`, `phone-mobile`, `voip-app`, `room-recorder`), with
  RTTM and expected transcript. Licensed CC BY 4.0; see `ATTRIBUTION.md`. Rebuild with
  `uv run --group tools python tools/build_fixtures.py speech` (needs network).
- `MANIFEST.json`: sha256 and size of every file; a test checks it and the 10 MB budget.
