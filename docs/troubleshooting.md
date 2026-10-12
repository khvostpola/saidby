# Troubleshooting

Start with `saidby doctor`: it checks most of what follows and prints the fix next to each
problem. For anything else, `saidby process` leaves `logs/run.log` in the output folder of the
file that failed.

| Symptom | Cause | Fix |
|---|---|---|
| `saidby: command not found` | `uv` tools are not on your PATH | `uv tool update-shell`, then open a new terminal |
| `ffmpeg not found` | ffmpeg is not installed | Install it with your package manager (for example `sudo dnf install ffmpeg`) |
| `ModelUnavailableError: model ... is not installed` | You have not downloaded it | `saidby models pull KEY` (or `--all`) |
| `... is gated: accept its conditions at https://hf.co/...` | `pyannote-community1` needs you to accept its terms | Open the URL, accept, then set `HF_TOKEN` and pull again |
| `... is not licensed for commercial use` | The model forbids commercial use | `--allow-noncommercial` if that is fine for you |
| Runs on the CPU although you have a GPU | The GPU is not usable (see `saidby doctor`) | The message tells you which part: a CPU-only PyTorch (`uv tool install 'saidby[cuda]'`), missing CUDA 12 libraries (same extra) or a driver older than 580 |
| `CUDA failed with error out of memory` | Less than about 6 GB of free GPU memory | Close other GPU programs, or `--device cpu`, or `--asr-model tiny` |
| Very slow on the CPU | large-v3 is big | `--asr-model tiny`; on a modern 20-thread CPU large-v3 runs at about 0.4 times real time |
| `InputError: output folder holds results for a different input` | The folder name collides with an earlier, different file | Use another `--out`, or `--force` to overwrite |
| `words could not be assigned to a speaker` (warning) | Some words fell outside every diarized turn | Usually a few at the edges; if many, try `--num-speakers` |
| One person appears as two speakers | The diarizer split them | `saidby speakers merge out/call SPEAKER_01 --into SPEAKER_00` |
| Nobody is named | No voiceprint matched | Check `manifest.json` warnings (a voiceprint from another model is skipped), enroll again, or lower `--identify-threshold` |
| `ConsentMissingError` (exit 5) | There is no consent record for that person | `--consent-source` and `--consent-declared-by` on `saidby enroll` |
| `LlmUnavailableError` (exit 7) | `llama-server` is missing or did not start | Install llama.cpp and put `llama-server` on the PATH, or set `SAIDBY_LLAMA_SERVER`; `saidby doctor` shows what it finds |
| The same file gives slightly different text each run | Whisper samples at random when a segment looks wrong | `--deterministic` |
| The transcript is in the wrong language | Language was detected, and the first seconds were misleading | Pass `--language` |
| A word you care about is always wrong | The recognizer does not know it | Add it to the directory with its usual mistakes as `variants`, see [getting started](getting-started.md#6-teach-it-your-words) |

## Still stuck?

Open an issue at https://github.com/khvostpola/saidby/issues and include the output of
`saidby doctor`. Do not attach recordings or transcripts of real people; redact names from logs.
