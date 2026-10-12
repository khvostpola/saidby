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
| stop retyping the same options | `saidby init` (this folder) or `saidby init --global` |
| transcribe one or several files | `saidby process a.m4a b.mp4 --out out/ --language es` |
| be guided: plan, one key to start | `saidby process call.m4a -i` |
| use my names and terms | `saidby process ... --directory directory.yaml` |
| name the speakers | `saidby enroll` (or `enroll -i`) once per person, then `process --directory` |
| rename or merge speakers afterwards | `saidby speakers map -i` / `saidby speakers merge` |
| fix mistakes by listening | `saidby process ... --compare pyannote-community1`, then `saidby review` |
| get the same result every time | `saidby process ... --deterministic` |
| work with no GPU | `saidby process ... --device cpu` (use `--asr-model tiny` on slow machines) |
| prove nothing leaves the machine | `saidby process ... --strict-offline` |
| see which models and licenses are involved | `saidby models list` and `saidby models licenses` |
| check my directory file | `saidby directory validate directory.yaml` |
| add a person or a term | `saidby directory add-person "Ana Gómez"` / `saidby directory add-term Acme` |
| measure against a hand-corrected reference | `saidby eval score reference.txt out/call` |

## Several files, one run

```bash
saidby process monday.m4a tuesday.m4a --out out/
```

Each input gets its own folder (`out/monday`, `out/tuesday`; duplicates get `-2`, `-3`). Models
are loaded once, and each stage runs for all the files before the next stage starts. If one file
fails, the others finish and the exit code tells you; `--fail-fast` stops at the first failure.

## Progress

Human lines go to stderr. A run starts with the device line, which says what will do the work and
why:

```
device      GPU · cuda · NVIDIA GeForce RTX 4060 Laptop GPU · 8 GB   (auto → cuda)
device      CPU · 8 threads   (auto → cpu: no NVIDIA GPU found)
```

If a GPU is present but cannot be used (for example PyTorch is the CPU build), the line says so
and points to `saidby doctor`. On a terminal, the moments that take a while show what they are
doing and for how long, and are replaced by the result when they finish: `starting` (loading
PyTorch and CTranslate2), `device` (checking the GPU, which can take a couple of seconds the
first time on a laptop) and each stage. A stage first says it is loading its model
(`loading large-v3 into the GPU...`), then what it is doing (`transcribing...  0:12`), and ends
with how much of the device is in use (`GPU 5.1/8.0 GB · 93%`, or `CPU 8 threads · 94%`).
That is the load of the whole device, not only saidby's share, and it is left out when the line
would not fit. When stderr is not a terminal you only get the result lines. Every run ends with a `[total]` line: how long it took, when it
started and finished, and how much audio it covered.

## The banner

On a terminal, `saidby` with no arguments draws the pixel-art cassette with what it knows about
your setup: the models, the device from the last run (it never probes the GPU just to draw a
banner), the glossary and the configuration file in use. `saidby process` shows a three-row
version before the device line. Both need a terminal that says it supports true color
(`COLORTERM=truecolor`) and at least 60 columns; otherwise you get one plain line (bare `saidby`)
or nothing (`process`). Nothing is drawn when stderr is not a terminal, with `--progress json` or
`none`, or with `NO_COLOR` set.

## Progress for scripts

`--progress json` prints one JSON event per line on stdout instead of the human lines, so
`saidby process ... --progress json > events.jsonl` gives a machine-readable log:

| Event | When | Fields |
|---|---|---|
| `run.start` | the run begins | `saidby` (version) |
| `device` | the device is chosen | `requested`, `used`, `name`, `vram_total_mb`, `reason` |
| `stage.start` | a stage begins | `file`, `stage` |
| `stage.loading` | a stage starts loading its model (once per model, not per file) | `file`, `stage`, `model` |
| `stage.end`, `stage.skip` | a stage finishes, or was already done | `file`, `stage`, `wall_s`, `rtf` |
| `stage.error` | a stage fails | `file`, `stage`, `error_type` |
| `file.end` | a file finishes | `file`, `status`, `out` |
| `run.end` | the run ends | `started`, `finished`, `wall_s`, `audio_s`, `rtf`, `files`, `failed` |

`reason` is `requested_cpu`, `no_gpu`, `gpu_unusable` or `null` when the GPU is used.

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

Relative paths in a file, such as `directory`, are resolved against the file that declares them,
and `~` means your home folder. `saidby init` writes a starter project file for you.
`directory` can be a list. Like every other key, the one in the project file replaces the one in
the global file, so a project that wants the shared glossary names it too (`saidby init` asks).
A `--directory` on the command line (repeat it for several files) or `SAIDBY_DIRECTORY` (separated
with `:` on Linux) replaces the files named in configuration.

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
directory = "directory.yaml"   # relative to this file; or a list of files
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

## Language of the messages

saidby writes its questions, progress lines, summaries and error messages in your language when
there is a translation, and in English otherwise. It looks at `--ui-lang` first (`saidby
--ui-lang es process ...`), then `SAIDBY_UI_LANG`, then the system locale (`LC_ALL`,
`LC_MESSAGES`, `LANG`). Spanish (`es`) ships today.

Some things are never translated, so scripts and documentation keep working: command names,
options and their help, the `--json` output of `doctor` and `speakers show`, the events of
`--progress json`, `logs/run.log`, the telemetry, `manifest.json` and every file saidby writes
for you. An error keeps its English id and exit code next to the translated message:
`error: no se encontró el archivo de directorio: x.yaml  [input · exit 3]`.

## Exit codes

| Code | Id | Meaning | What to do |
|---|---|---|---|
| 0 | | Success | |
| 1 | `error` | Unexpected error | Run again with the same arguments; if it repeats, open an issue with `saidby doctor` output |
| 2 | `usage` | Usage or configuration error | The message names the option or key |
| 3 | `input` | Input problem: missing or undecodable file, or the output folder holds another input | Check the path; `--force` to overwrite |
| 4 | `model_unavailable` | Model not installed, gated, or licensed for non-commercial use only | `saidby models pull KEY` |
| 5 | `consent_missing` | No recorded consent for that person's voiceprint | Pass `--consent-source` and `--consent-declared-by` |
| 6 | `stage_failed` | A stage failed, or more than one file failed | See `logs/run.log` in the failed folder |
| 7 | `llm_unavailable` | The LLM is not available | Install `llama-server` or fix `--llm-url` |
| 8 | `network_attempt` | Something tried to leave the machine under `--strict-offline` | |
| 130 | | Interrupted with Ctrl+C | Run again to resume |

Errors print as `error: message  [id · exit N]` on stderr, without a traceback. The id and the
number are the same whatever language the message is in.
