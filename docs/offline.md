# Offline guarantees

- Processing runs with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`.
- `PYANNOTE_METRICS_ENABLED=false` and `HF_HUB_DISABLE_TELEMETRY=1` are set before any model
  library is imported.
- `saidby.runtime.netguard` audits socket activity and only allows loopback. The test suite
  runs with sockets disabled.
- Logs and telemetry stay on disk, use a closed set of fields and never include transcript
  text, names, glossary terms, voiceprints or file names.
