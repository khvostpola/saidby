# CLI

```
saidby --version
saidby doctor [--json]
saidby models list | pull KEY... [--all] | licenses | path KEY
saidby process INPUT... --out DIR [options]
```

## `saidby process`

| Option | Meaning |
|---|---|
| `--language CODE` | Recording language (for example `es`); autodetected if omitted |
| `--device auto\|cuda\|cpu` | Where to run models |
| `--asr-model KEY` | `large-v3` by default, `tiny` for quick tests, or a local model path |
| `--diarizer NAME` | `nemotron3` (default), `pyannote-community1` (needs `saidby[pyannote]`) or `fake` |
| `--num-speakers N` | Fix the number of speakers when known |
| `--keep-intermediates` | Keep `.work/` after success |
| `--force` | Overwrite a folder that holds results for a different input |
| `--fail-fast` | Stop at the first failed recording |
| `--strict-offline` | Fail with exit code 8 if anything tries to leave the machine |
| `--progress human\|json\|none` | Progress lines on stderr, or one JSON event per line on stdout |

Several inputs share one run: models are loaded once and each stage runs over all files
before the next one starts. Output folders are named after the input file; duplicates get
`-2`, `-3`.

Configuration precedence: command line, `SAIDBY_*` environment variables, `saidby.toml`
(`--config`, `./saidby.toml` or `~/.config/saidby/config.toml`), defaults.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected error |
| 2 | Usage or configuration error |
| 3 | Input error (missing file, not decodable, output folder holds another input) |
| 4 | Model unavailable or license refused |
| 5 | Consent missing (reserved) |
| 6 | Stage failure, or more than one file failed |
| 7 | LLM backend unavailable (reserved) |
| 8 | Network attempt under `--strict-offline` |
| 130 | Interrupted |
