# Review and comparison

## Comparing two diarizers

`saidby process call.m4a --out out/ --compare pyannote-community1` runs a second diarizer on the
same audio. The labels of the two are matched one-to-one, and the stretch around every turn
boundary (0.25 s) is ignored, as in standard diarization scoring. `manifest.json` gets a
`compare` block with the agreement (share of the speech time where both name the same speaker),
the seconds of disagreement and the list of spans where they differ. The telemetry records
the same counts. Nothing is merged: the first diarizer stays the one that is used.

## Reviewing

`saidby review out/call` goes through the spans a person should look at, in this order:

1. `diarization`: spans where the two diarizers disagree (needs `--compare` in the run).
2. `llm_rejected`: proposals of the LLM that the guardrails rejected.
3. `low_confidence`: runs of words whose recognizer probability is under `--low-confidence`
   (0.6 by default).

For each span you see the current text and the speakers, and you answer with:

| Input | Effect |
|---|---|
| Enter | Keep the text (not asked again) |
| corrected text | Replace the span; new words get `source: review` |
| `@SPEAKER_01` or `@ana` | Set who spoke (optionally followed by the corrected text) |
| `/s` | Skip for now |
| `/q` | Quit |

The corrected text keeps the original word timings when the number of words is the same, and
spreads the words evenly over the span otherwise. Every change is appended to
`corrections.jsonl` with `by: review`. Decisions (without any text) are kept in
`logs/review.jsonl` so the next session skips what you already answered, and each session is
recorded under `edits` in `manifest.json`.

With `--directory FILE`, a correction that spells a known term or person differently from
anything in the directory is offered as a new `variants` entry, so the next run gets it right
(`--yes` accepts without asking; the directory is backed up first).

Speaker changes made in review update the words, the transcript and the manifest, but not
`diarization.rttm` or the per-speaker tracks, which come from the diarizer; use
`saidby speakers merge` for structural fixes. `review` is the one command that prints
transcript text on the terminal.
