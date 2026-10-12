# Output format

Every JSON file carries a `schema` tag (`saidby.words/1`, `saidby.diarization/1`,
`saidby.manifest/1`). Floats are in seconds.

## `transcript.words.json`

```json
{"schema": "saidby.words/1", "language": "es", "duration_s": 1574.2,
 "engine": {"kind": "asr", "name": "faster-whisper", "model": "large-v3", "revision": "..."},
 "speakers": [{"label": "SPEAKER_00", "speech_s": 612.3, "track": "speakers/SPEAKER_00.flac"}],
 "segments": [{"start": 0.52, "end": 4.1, "words": [
   {"start": 0.52, "end": 0.8, "word": " hola", "p": 0.98, "speaker": "SPEAKER_00", "source": "asr"}]}]}
```

`word` keeps the engine's leading space. `source` says where the word came from (`asr` today;
later `bias`, `dialect`, `llm`, `review`).

## `manifest.json`

Tool version, `status` (`ok`, `failed`, `interrupted`), source file with sha256, device (what
you asked for, what ran, the GPU name and memory, and `reason` when the CPU ran: `requested_cpu`,
`no_gpu` or `gpu_unusable`), one record per stage (engine, model, revision, wall time, cached), speakers, files, warnings
and, on failure, `failed_stage` and `error_type`.

## `logs/telemetry.jsonl`

One event per line with a closed set of fields: stage, engine, model, revision, device,
timings, real-time factor, memory peak, counts and, for a stage that did not run, the reason. Every
`stage.start` is followed by a `stage.end`, `stage.skip` or `stage.error`. It never contains transcript text,
names, glossary terms, voiceprints or file names. The GPU memory peak is `null` on Windows,
where the driver does not report memory per process.

## `corrections.jsonl`

Written when a directory is given. One JSON object per line: `t` and `end` (seconds), `from`,
`to`, `by` (`bias`, `dialect`, `llm`, later `review`), `status` (`accepted` or `rejected`),
`reason` for rejections (`out_of_range`, `span_too_long`, `term_not_allowed`, `already_equal`,
`covers_extra_words`, `low_similarity`, `overlaps_change`, `truncated_response`) and `similarity`.
