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

Tool version, `status` (`ok`, `failed`, `interrupted`), source file with sha256, device,
one record per stage (engine, model, revision, wall time, cached), speakers, files, warnings
and, on failure, `failed_stage` and `error_type`.

## `logs/telemetry.jsonl`

One event per line with a closed set of fields: stage, engine, model, revision, device,
timings, real-time factor, memory peak and counts. It never contains transcript text,
names, glossary terms, voiceprints or file names.
