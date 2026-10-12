# Commands

`saidby --help` groups the commands the way you use them. Every command has its own `--help`
with examples; the complete list of options is in the [command reference](cli-reference.md).

```
Transcribe     process      turn recordings into transcripts with speakers and tracks
After a run    review       correct the spans the machine is unsure about
               enroll       store a person's voiceprint (needs recorded consent)
               speakers     show, map (rename) and merge speakers without reprocessing
Set up         doctor       check this machine and say how to fix what is missing
               models       list, download (pull) and locate models
               directory    validate or create the directory file
Measure        eval         score a run and arbitrate differences between two systems blind
```

## I want to...

| I want to | Command |
|---|---|
| know if my machine can run it | `saidby doctor` (add `--smoke` for a real test) |
| download the models | `saidby models pull --all` |
| transcribe one or several files | `saidby process a.m4a b.mp4 --out out/ --language es` |
| use my names and terms | `saidby process ... --directory directory.yaml` |
| name the speakers | `saidby enroll` once per person, then `process --directory` |
| rename or merge speakers afterwards | `saidby speakers map` / `saidby speakers merge` |
| fix mistakes by listening | `saidby process ... --compare pyannote-community1`, then `saidby review` |
| get the same result every time | `saidby process ... --deterministic` |
| work with no GPU | `saidby process ... --device cpu` (use `--asr-model tiny` on slow machines) |
| prove nothing leaves the machine | `saidby process ... --strict-offline` |
| see which models and licenses are involved | `saidby models list` and `saidby models licenses` |
| check my directory file | `saidby directory validate directory.yaml` |
| measure against a hand-corrected reference | `saidby eval score reference.txt out/call` |

## Several files, one run

```bash
saidby process monday.m4a tuesday.m4a --out out/
```

Each input gets its own folder (`out/monday`, `out/tuesday`; duplicates get `-2`, `-3`). Models
are loaded once, and each stage runs for all the files before the next stage starts. If one file
fails, the others finish and the exit code tells you; `--fail-fast` stops at the first failure.

## Progress for scripts

`--progress json` prints one JSON event per line on stdout (`stage.start`, `stage.end`,
`stage.skip`, `stage.error`, `file.end`, and a final `run.end` with the start and finish times,
the total seconds, the audio seconds and how many files failed) instead of the human lines, so `saidby process ... --progress json >
events.jsonl` gives a machine-readable log. The human lines go to stderr. On a terminal, a stage that takes more than a moment shows what it is
doing and how long it has been at it (`transcribing...  0:12`), replaced by the result line when it
finishes; when stderr is not a terminal you only get the result lines. Every run ends with a
`[total]` line: how long it took, when it started and finished, and how much audio it covered.

## Configuration

Defaults can come from files so you do not retype options. Precedence, highest first: the
command line, `SAIDBY_*` environment variables, the project file, the global file, built-in
defaults. The two files are merged key by key, so a project can change one setting and keep the
rest from the global file.

- **Global file**: `~/.config/saidby/config.toml` (or under `$XDG_CONFIG_HOME`).
- **Project file**: the nearest `saidby.toml`, looking in the current folder and then in each
  parent folder up to your home folder, like git does for `.git`. Outside your home folder only
  the current folder is checked, so a stray file in a shared parent is never read.
- **`--config FILE`**: use exactly that file and ignore both of the above.

Relative paths in a file, such as `directory`, are resolved against the file that declares them.

```toml
[saidby]
out = "saidby"             # where results go; relative to this file (default: ./saidby)
device = "auto"            # auto, cuda or cpu
language = "es"
keep_intermediates = false
progress = "human"

[asr]
model = "large-v3"         # or tiny, or a path to a CTranslate2 model
compute_type = "auto"
deterministic = false

[diarizer]
engine = "nemotron3"       # or pyannote-community1
num_speakers = 2           # leave out to detect it
compare = "pyannote-community1"

[identify]
enabled = true
threshold = 0.5

[glossary]
directory = "directory.yaml"   # relative to this file
bias = true
bias_mode = "full"             # or windows (experimental)
transplant = true
correct = false

[llm]
binary = "/opt/llama.cpp/llama-server"
model = "qwen3.5-9b-q4"
```

Unknown keys are errors that name the key, so a typo cannot silently do nothing. Every setting
can also be an environment variable: `SAIDBY_LANGUAGE=es`, `SAIDBY_DEVICE=cpu`,
`SAIDBY_ASR_MODEL=tiny`, and so on (the upper-cased name of the key in `[saidby]`).

## Exit codes

| Code | Meaning | What to do |
|---|---|---|
| 0 | Success | |
| 1 | Unexpected error | Run again with the same arguments; if it repeats, open an issue with `saidby doctor` output |
| 2 | Usage or configuration error | The message names the option or key |
| 3 | Input problem: missing or undecodable file, or the output folder holds another input | Check the path; `--force` to overwrite |
| 4 | Model not installed, gated, or licensed for non-commercial use only | `saidby models pull KEY` |
| 5 | No recorded consent for that person's voiceprint | Pass `--consent-source` and `--consent-declared-by` |
| 6 | A stage failed, or more than one file failed | See `logs/run.log` in the failed folder |
| 7 | The LLM is not available | Install `llama-server` or fix `--llm-url` |
| 8 | Something tried to leave the machine under `--strict-offline` | |
| 130 | Interrupted with Ctrl+C | Run again to resume |

Errors print as `error: ClassName: message` on stderr, without a traceback.
