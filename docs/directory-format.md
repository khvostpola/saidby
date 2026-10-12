# Directory format

One YAML file with people and terms. Validate with `saidby directory validate FILE`, create a
starter with `saidby directory init FILE` (or `--global` for the one shared by every folder),
and see the JSON Schema with
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

## Editing from the command line

```bash
saidby directory add-person "Ana Gómez" --alias Anita --context accountant
saidby directory add-term Acme --variant akme --confusion acne
saidby directory add-term chimba --dialect
```

Both commands edit one file (`--directory FILE`, or the last configured one), keep its comments,
back it up first and refuse duplicates. The person's `id` is made from the name without accents
(`ana-gomez`), with `-2`, `-3` if it is taken; pass `--id` to choose it, which is required when
the name has no Latin letters.

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

Identification also needs the consent: a voiceprint is used only if the `consent.yaml` next to
the file that holds it has a record for that person. Otherwise it is skipped, counted in
`voiceprints_skipped`, and `manifest.json` names the person and the file. Run `saidby enroll`
again or add the record.

## Several directory files

`--directory` can be repeated, and `directory` in `saidby.toml` can be a list, so a shared
file (your team, your own regulars) can sit under one for each project:

```toml
[glossary]
directory = ["~/shared/team-directory.yaml", "directory.yaml"]   # far to near
```

A `directory` list in the project file replaces the one in the global file, so list the shared
file again if the project should use it. Files are read from the farthest to the nearest, and the
nearest wins:

- **Terms** are combined; if the same term is in two files (ignoring case) the nearest entry is used.
- **People** are combined by `id`; the nearest entry wins field by field, except the voiceprint,
  which comes from the nearest file that has a usable one.
- **`language`** is the nearest file's.
- **Consent** is read next to each file, so a voiceprint never borrows a record from another file.
- Writes (`saidby enroll`, `saidby review`) go to one file: the one you name with `--directory`,
  or the last one configured.

`manifest.json` lists every file under `directory.files`, with its `sha256`; `directory.path`
and `directory.sha256` are those of the last file.
