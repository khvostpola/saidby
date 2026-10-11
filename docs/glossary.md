# Glossary: terms, bias and correction

Pass a directory (see [directory format](directory-format.md)) with `--directory` and saidby
helps the recognizer spell your names and terms. Everything here runs on your machine.

## Stages

1. **Bias (`asr_bias`)**: a second transcription pass with the directory's names and terms as
   `hotwords` (people, then terms, then dialect terms, up to Whisper's 223-token budget; anything
   that does not fit is dropped and reported in `manifest.json`). Turn off with `--no-bias`.
2. **Transplant (`transplant`)**: the biased pass changes the style of the whole transcript and can
   skip long passages, so saidby keeps the plain transcript and takes from the biased one only
   the spans where it wrote a directory word. Spans whose length differs by more than two words
   are ignored. Turn off with `--no-transplant`. Dialect terms (`type: dialect`) are then
   unified deterministically to their canonical spelling.
3. **Correction (`correct`, off by default)**: with `--correct`, a local LLM may propose replacing
   a word, or up to three consecutive words, with a directory term. It runs as a `llama-server`
   subprocess on a free `127.0.0.1` port (or you pass `--llm-url`). The limits are enforced in
   code, not by the prompt:
   - only a directory term or variant can be written, never free text;
   - a span longer than the term is accepted only if it is a known variant or confusion;
   - the original must be a known variant or resemble the term (similarity of at least 0.5);
   - overlapping changes keep the first; truncated model output skips that chunk;
   - word timestamps are never changed.

Every accepted or rejected change is written to `corrections.jsonl` with its time, original,
replacement, origin (`bias`, `dialect`, `llm`) and rejection reason. Words carry a `source`
field in `transcript.words.json`.

## Setting up the LLM

saidby does not install `llama.cpp`. Put `llama-server` on the `PATH`, or set
`SAIDBY_LLAMA_SERVER`, or pass `--llm-binary`. Download the model once:

```bash
saidby models pull llm:qwen3.5-9b-q4
saidby process call.m4a --out out/ --directory directory.yaml --correct
```

An endpoint that is not on this machine is refused unless you also pass `--allow-remote-llm`.
If the LLM cannot start, the run fails with exit code 7 before processing anything.

## What it costs

On a 15-minute call, the biased pass roughly doubles transcription time and the LLM adds under a
minute on an 8 GB GPU. The glossary stages are cached by input, so changing the directory only
reruns the stages that depend on it.
