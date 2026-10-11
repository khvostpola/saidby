# CLI

```
saidby --version
saidby doctor [--json]
saidby models list | pull KEY... [--all] | licenses | path KEY
saidby process INPUT... --out DIR [options]
saidby enroll OUT_DIR --speaker LABEL=PERSON_ID... --directory FILE [consent options]
saidby speakers show OUT_DIR
saidby speakers map OUT_DIR --set LABEL=PERSON_ID [--directory FILE]
saidby speakers merge OUT_DIR LABEL... --into LABEL
saidby directory validate FILE | schema | init FILE
```

## `saidby process`

| Option | Meaning |
|---|---|
| `--language CODE` | Recording language (for example `es`); autodetected if omitted |
| `--device auto\|cuda\|cpu` | Where to run models |
| `--asr-model KEY` | `large-v3` by default, `tiny` for quick tests, or a local model path |
| `--diarizer NAME` | `nemotron3` (default), `pyannote-community1` (needs `saidby[pyannote]`) or `fake` |
| `--num-speakers N` | Fix the number of speakers when known |
| `--directory FILE` | Directory with people (and voiceprints); enables identification |
| `--no-bias`, `--no-transplant` | Skip the biased pass, or keep it but do not merge it |
| `--correct` | Fix directory terms with a local LLM (see [glossary](glossary.md)) |
| `--llm-url URL`, `--llm-binary PATH` | Use an existing OpenAI-compatible endpoint, or a specific `llama-server` |
| `--allow-remote-llm` | Allow an endpoint that is not on this machine |
| `--no-identify` | Skip identification even when voiceprints exist |
| `--identify-threshold X` | Minimum cosine score to assign a name (default 0.5) |
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
| 7 | LLM backend unavailable |
| 8 | Network attempt under `--strict-offline` |
| 130 | Interrupted |

## Speakers after processing

`speakers map` and `speakers merge` rewrite `transcript.words.json`, `transcript.txt`,
`transcript.vtt`, `diarization.rttm`, the tracks and `manifest.json` (it records each edit under
`edits`) without reprocessing audio. Speaker labels (`SPEAKER_00`) never change; names and
track file names do. Merge is for a person the diarizer split in two.
