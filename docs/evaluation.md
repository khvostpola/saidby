# Evaluation

`pip install "saidby[eval]"` adds `saidby eval`, the same bench used to decide whether saidby is
better than another tool. It never needs your recordings to leave your machine.

## The reference

A text file you correct by hand while listening, for a stretch of 5 to 10 minutes:

```
# offset_s: 210
00:00-00:11 | Ana | hola, buenas tardes >> Ben buenas
00:11-00:20 | Ben | vamos a empezar con el informe
```

- `# offset_s:` is where the stretch starts in the recording (seconds).
- Each line is `MM:SS-MM:SS | speaker | text`, relative to the offset. Use `?` when you do not
  want to score speakers. `>> Name` inside a line marks a change of speaker.
- Use the spelling you want in the output; case and punctuation are ignored.

## Scoring a run

```bash
saidby eval score reference.txt out/call --directory directory.yaml
```

It prints the WER (plain and with dialect terms unified), the share of directory terms spelled
correctly, and, when the reference names speakers, the diarization error rate, the speaker
confusion and the share of speech with the correct name.

## Two pitfalls, measured

1. **The tool that wrote the first draft wins.** If you correct a draft written by system X, the
   errors of X that you do not notice count as correct, so X scores a WER close to your edits
   and every other system scores worse. On two real calls the system that wrote the draft got
   3.8 % and 7.2 % while the other got 9.0 % and 17.5 %. Start from a draft by a system that is
   not in the comparison, or mix drafts, and use blind arbitration for the final word.
2. **Decoding is random unless you ask otherwise.** The recognizer's temperature fallback made
   the same call score between 17.8 % and 19.8 % WER on three runs. Run the systems you compare
   with `saidby process --deterministic` (temperature 0 and no conditioning on previous text):
   three full runs produced identical words and timestamps, at a WER inside that same range.

## Blind arbitration

The difference between two systems lives only in the spans where they disagree. Listen to
those instead of redoing the reference:

```bash
saidby eval arbitrate-build call1 "Call 1" call.m4a reference.txt out/saidby out/other
saidby eval arbitrate-serve              # http://127.0.0.1:8765, keys 1 2 3 4, space to replay
saidby eval arbitrate-score --margin 1.0
```

Each span is a short clip with the two versions, A and B shuffled per span and in random order,
so any prefix is a random sample. Pick the version that is right, both, or neither, or type
what you hear: typed text is scored by word edit distance and replaces the vote. The clips are
private audio: the page only listens on `127.0.0.1` and must never be published.

The score is the difference in word errors (candidate minus baseline, so negative favours the
candidate) scaled to all disagreement spans, over the reference words, with a 95 % bootstrap
interval of 10,000 resamples. Judge every span if you can; a sample of 40 per call is the
minimum.

## Reading the result without tilting it

- Compare the point estimate with zero on the material you measured, per call.
- To claim "not worse" you need a margin fixed **before** you measure (the project uses 1 point
  of WER, for new calls only). With `--margin`, a run is non-inferior only if the upper end of the
  interval is below it. An interval that merely includes zero is not evidence of "not worse":
  it gets easier to include zero the less you measure.
