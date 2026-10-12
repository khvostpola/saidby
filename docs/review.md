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

For each span you see the words around it (dimmed) with the span itself in brackets and
highlighted, who spoke, and a question that names it, such as `Text for "akme"?`. You answer
with:

| Input | Effect |
|---|---|
| Enter | Keep the text (not asked again) |
| corrected text | Replace the span; new words get `source: review` |
| `p` | Play the span (a little before and after) and ask again |
| `@SPEAKER_01` or `@ana` | Set who spoke (optionally followed by the corrected text) |
| `/s` | Skip for now |
| `/q` | Quit |

Playing needs `ffplay` (it comes with ffmpeg). The audio is the kept `.work/audio.wav` when the
run used `--keep-intermediates`; otherwise the track of the voice that speaks most in the span;
otherwise the original recording, if it is still where the run found it. If none is there,
`p` says so.

Type only what the span should say. If your text starts or ends with the words that sit next to
the span (as when you retype the whole phrase), saidby notices, tells you which words repeat and
asks whether to replace only the span; answer `n` to keep your text exactly as typed.

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
