# Command reference

Generated from `saidby --help` by `tools/gen_cli_reference.py`; do not edit by hand. For a guided tour of the commands see [commands.md](commands.md).

## `saidby process`

Turn recordings into transcripts with speakers, timestamps and a track per speaker.

Arguments:

- `INPUTS`: Audio or video files (anything ffmpeg reads).

| Option | Type | Default | What it does |
|---|---|---|---|
| `--out` | path |  | Folder for the results, one subfolder per input (default: ./saidby). |
| `--config` | path |  | A saidby.toml with defaults for the options below. |
| `--language` | str |  | Recording language code (es, en, pt...). Detected from the audio if omitted. |
| `--device` | str |  | auto (default): GPU if usable, else CPU. Or force cuda or cpu. |
| `--asr-model` | str |  | Recognition model: large-v3 (default), tiny, or a path to a CTranslate2 model. |
| `--compute-type` | str |  | auto (float16 on GPU, int8 on CPU), float16, int8, int8_float16 or float32. |
| `--deterministic` | flag |  | Same input, same output: temperature 0 and no conditioning on earlier text. |
| `--diarizer` | str |  | Who-spoke-when engine: nemotron3 (default) or pyannote-community1 (extra). |
| `--num-speakers` | int range |  | Fix the number of speakers when you know it. |
| `--compare` | str |  | Also run this second diarizer and record where the two disagree. |
| `--no-identify` | flag |  | Do not name speakers even if the directory has voiceprints. |
| `--identify-threshold` | number |  | Minimum voiceprint similarity to assign a name (default 0.5). |
| `--directory` | path |  | Directory YAML with people, voiceprints and terms; turns on the glossary. Repeat it to combine files (the last one wins). Replaces the files named in saidby.toml. |
| `--term` | str |  | A term to spell right in this run only; repeat it for several. Not saved. |
| `--no-bias` | flag |  | Skip the second, hotword-biased recognition pass. |
| `--bias-mode` | str |  | full (default) biases all audio; windows (experimental) only near likely terms. |
| `--no-transplant` | flag |  | Run the biased pass but do not merge its terms into the transcript. |
| `--correct` | flag |  | Let a local LLM fix directory terms, within strict limits. Needs llama-server. |
| `--llm-url` | str |  | Use an OpenAI-compatible server you already run, not llama-server. |
| `--llm-binary` | str |  | Path to llama-server (default: PATH or SAIDBY_LLAMA_SERVER). |
| `--allow-remote-llm` | flag |  | Allow an LLM endpoint that is not on this machine. |
| `--keep-intermediates` | flag |  | Keep the .work folder after success (it is kept on failure). |
| `--force` | flag |  | Overwrite an output folder that holds results for a different input. |
| `--fail-fast` | flag |  | Stop at the first input that fails. |
| `--progress` | str |  | human (default, on stderr), json (one event per line on stdout) or none. |
| `--strict-offline` | flag |  | Fail with exit code 8 if anything tries to leave this machine. |
| `--interactive`, `-i` | flag |  | Show a plan and start with one key; afterwards listen to and name the voices. |

Examples:

```bash
saidby process call.m4a --language es
saidby process a.mp4 b.mp3 --directory directory.yaml
saidby process call.m4a --term Acme --term "Rappi Pay"
saidby process call.m4a --out results/ --directory directory.yaml --correct
saidby process call.m4a --device cpu --asr-model tiny
saidby process call.m4a -i
```

## `saidby review`

Review uncertain spans of a finished run and fix them by typing the right text.

This is the one command that prints transcript text on the terminal.

Arguments:

- `OUT_DIR`: Output folder of a finished run (the one `saidby process` wrote).

| Option | Type | Default | What it does |
|---|---|---|---|
| `--kinds` | str | `diarization,llm_rejected,low_confidence` | Comma list of: diarization, llm_rejected, low_confidence |
| `--low-confidence` | number | `0.6` | Reviewed when word probability is below |
| `--limit` | int range |  | Review at most this many spans |
| `--directory` | path |  | Offer to add new variants here (default: the last configured file) |
| `--yes` | flag |  | Accept directory suggestions |

## `saidby enroll`

Store voiceprints of people who spoke in a finished run. Requires recorded consent.

Arguments:

- `OUT_DIR`: Output folder of a finished run (the one `saidby process` wrote).

| Option | Type | Default | What it does |
|---|---|---|---|
| `--speaker` | str |  | LABEL=PERSON (an id or a name) |
| `--directory` | path |  | Directory file to update (default: the last configured one) |
| `--consent-file` | path |  | consent.yaml (default: next to the directory) |
| `--consent-source` | str |  | How consent was given |
| `--consent-declared-by` | str |  | Who declared it |
| `--consent-date` | str |  | YYYY-MM-DD, default today |
| `--channel` | str | `mobile-call` | Recording channel label |
| `--embedder` | str | `wespeaker-resnet34` | Voiceprint model. |
| `--device` | str | `auto` | auto, cuda or cpu. |
| `--interactive`, `-i` | flag |  | Ask for each named voice whether the person consented, instead of --speaker. |

## `saidby init`

Create saidby.toml, directory.yaml and consent.yaml, so the next run needs no flags.

| Option | Type | Default | What it does |
|---|---|---|---|
| `--language` | str |  | Language of your recordings, such as es or en (default: asks). |
| `--yes` | flag |  | Do not ask: take the language option or the default. |
| `--global` | flag |  | Set up ~/.config/saidby for every folder, not this one. |

## `saidby doctor`

Check that this machine can run saidby and say how to fix what is missing.

| Option | Type | Default | What it does |
|---|---|---|---|
| `--json` | flag |  | Machine-readable output |
| `--smoke` | flag |  | Also run a short transcription with asr:tiny |
| `--device` | str | `auto` | Device to check: auto, cuda or cpu |

## `saidby speakers`

Inspect, rename and merge speakers of a finished run.

### `saidby speakers show`

List the speakers of an output folder.

Arguments:

- `OUT_DIR`: Output folder of a finished run (the one `saidby process` wrote).

| Option | Type | Default | What it does |
|---|---|---|---|
| `--json` | flag |  | Machine-readable output. |

### `saidby speakers map`

Give speakers a person id and name without reprocessing audio.

Arguments:

- `OUT_DIR`: Output folder of a finished run (the one `saidby process` wrote).

| Option | Type | Default | What it does |
|---|---|---|---|
| `--set` | str |  | LABEL=PERSON (an id or a name) or LABEL="Free name" |
| `--directory` | path |  | Directory to find people in (default: the configured ones) |
| `--add-missing` | flag |  | Add names that are not in the directory to its last file, without asking. |
| `--interactive`, `-i` | flag |  | Listen to each voice and name it, with questions, instead of --set. |

### `saidby speakers merge`

Merge speakers that the diarizer split by mistake.

Arguments:

- `OUT_DIR`: Output folder of a finished run (the one `saidby process` wrote).
- `LABELS`: Speakers to merge

| Option | Type | Default | What it does |
|---|---|---|---|
| `--into` | str |  | Speaker that keeps the merged speech (required) |

## `saidby models`

List, download and locate models.

### `saidby models list`

Show every known model and whether it is installed.

### `saidby models licenses`

Show the license and attribution of every model.

### `saidby models path`

Print the local snapshot path of an installed model.

Arguments:

- `KEY`: Model key, e.g. asr:large-v3

### `saidby models pull`

Download models. This is the only command that uses the network.

Arguments:

- `KEYS`: Model keys to download

| Option | Type | Default | What it does |
|---|---|---|---|
| `--all` | flag |  | Pull every default model |
| `--token` | str |  | Hugging Face token |
| `--allow-noncommercial` | flag |  | Also pull models that are not for commercial use. |

## `saidby directory`

Validate, create and edit directory files.

### `saidby directory validate`

Check a directory file against the schema.

Arguments:

- `FILE`: Directory YAML file to check.

### `saidby directory schema`

Print the JSON Schema of the directory format.

### `saidby directory init`

Create a starter directory file.

Arguments:

- `FILE`: Where to create the starter directory.

| Option | Type | Default | What it does |
|---|---|---|---|
| `--language` | str | `es` | Recording language |
| `--global` | flag |  | Create it in ~/.config/saidby/, shared by every folder. |

### `saidby directory add-person`

Add a person to a directory file, keeping its comments.

Arguments:

- `NAME`: The person's name as it should be written.

| Option | Type | Default | What it does |
|---|---|---|---|
| `--id` | str |  | Id for the person (default: made from the name). |
| `--alias` | str |  | Other name they go by; repeatable. |
| `--variant` | str |  | A misspelling the recognizer makes; repeatable. |
| `--context` | str |  | Role or relation, optional. |
| `--directory` | path |  | Directory file to edit (default: the last configured one). |

### `saidby directory add-term`

Add a term to a directory file, keeping its comments.

Arguments:

- `TERM`: The term, spelled the way it should be written.

| Option | Type | Default | What it does |
|---|---|---|---|
| `--variant` | str |  | A misspelling the recognizer makes; repeatable. |
| `--confusion` | str |  | A real word it gets mistaken for; repeatable. |
| `--context` | str |  | What it means, optional. |
| `--dialect` | flag |  | Regional slang with one canonical spelling. |
| `--directory` | path |  | Directory file to edit (default: the last configured one). |

## `saidby eval`

Measure runs against a hand-corrected reference and arbitrate differences blind.

### `saidby eval score`

WER, directory terms spelled correctly and, if the reference names speakers, diarization.

Arguments:

- `REFERENCE`: Hand-corrected reference file (see docs/evaluation.md).
- `RUN_DIR`: Output folder of the run to score.

| Option | Type | Default | What it does |
|---|---|---|---|
| `--directory` | path |  | Directory for terms and dialect |

### `saidby eval arbitrate-build`

Build clips of every span where two runs disagree, with A and B shuffled.

Arguments:

- `NAME`: Short name of this recording, used in clip ids.
- `LABEL`: Human-readable name shown in the page.
- `MEDIA`: The original recording (audio or video).
- `REFERENCE`: Hand-corrected reference of a stretch of it.
- `CANDIDATE`: Output folder of the system being evaluated.
- `BASELINE`: Output folder of the system to compare against.

| Option | Type | Default | What it does |
|---|---|---|---|
| `--out` | path | `arbitration` | Where to write clips and keys |
| `--directory` | path |  | Directory, to unify dialect terms before comparing. |
| `--seed` | int | `7` | Seed for the A/B shuffle. |

### `saidby eval arbitrate-serve`

Serve the arbitration page on 127.0.0.1 (the clips are private audio; never publish them).

| Option | Type | Default | What it does |
|---|---|---|---|
| `--out` | path | `arbitration` | Folder written by arbitrate-build. |
| `--port` | int | `8765` | Local port to listen on. |

### `saidby eval arbitrate-score`

Estimate the WER difference (candidate minus baseline) with a 95% bootstrap interval.

| Option | Type | Default | What it does |
|---|---|---|---|
| `--out` | path | `arbitration` | Folder written by arbitrate-build. |
| `--directory` | path |  | Directory, to unify dialect terms before scoring. |
| `--margin` | number |  | Pre-registered non-inferiority margin, in WER points |
