# Directory format

One YAML file with people and terms. Validate with `saidby directory validate FILE`, create a
starter with `saidby directory init FILE`, and see the JSON Schema with
`saidby directory schema` (also committed as `schemas/directory-1.schema.json`).

```yaml
version: 1
language: es
people:
  - id: ana                  # lowercase letters, digits, "_" and "-"; used for track file names
    name: Ana Gomez
    aliases: [Anita]
    variants: [Anna]         # common misspellings of the name
    confusions: []
    context: accountant      # optional role
    voiceprint: {...}        # written by `saidby enroll`, never by hand
terms:
  - term: Acme
    variants: [akme]
    confusions: []
    context: customer name
  - term: parce
    type: dialect            # regional slang with a canonical spelling
```

## Voiceprints and consent

`saidby enroll OUT_DIR --speaker SPEAKER_00=ana --directory directory.yaml` stores the vector
of a speaker of a finished run. It refuses (exit code 5) unless `consent.yaml` has a record for
that person:

```yaml
- person: ana
  scope: voiceprint
  source: signed form
  declared_by: Ana Gomez
  date: 2026-10-11
```

Passing `--consent-source` and `--consent-declared-by` appends that record for you. The
directory and the consent file are backed up (`name.bak-YYYYMMDD-HHMMSS.yaml`) before every
write, and comments are preserved.

A voiceprint stores the vector, never audio, plus the model, its revision, the preprocessing
and the channel. Identification only uses voiceprints made with the same model and revision as
the installed one; others are skipped with a warning in `manifest.json`. A name is assigned only
with a cosine score of at least 0.5 and at least 3 s of speech; each person is used once.
