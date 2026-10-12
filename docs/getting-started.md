# Getting started

About 15 minutes the first time, most of it downloading models. You need Linux, `ffmpeg`, and
`uv` (see [uv's install page](https://docs.astral.sh/uv/getting-started/installation/)). An NVIDIA
GPU makes it three to four times faster but is not required.

## 1. Install

With an NVIDIA GPU (driver 580 or newer):

```bash
uv tool install 'saidby[cuda]'
```

Without one, or to skip about 1 GB of CUDA libraries:

```bash
uv tool install saidby --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
```

Check that `saidby --help` lists the commands. If your shell says `saidby: command not found`,
run `uv tool update-shell` and open a new terminal.

## 2. Check the machine

```bash
saidby doctor
```

```
saidby 0.4.1
ok    python   3.12.14
ok    ffmpeg   ffmpeg version 7.1.5
ok    gpu      NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MB, driver 580.178.04
ok    cuda     GPU is usable by PyTorch and CTranslate2
ok    device   auto selects the GPU (NVIDIA GeForce RTX 4060 Laptop GPU)
FAIL  models   missing: asr:large-v3, diarizer:nemotron3, embedder:wespeaker-resnet34
               -> run: saidby models pull --all
...
1 problem(s) to fix before processing
```

Every line that is not `ok` says how to fix it. Run it again after each fix.

## 3. Download the models (once)

```bash
saidby models pull --all
```

This is the only step that uses the network: about 3.5 GB in total (the recognizer, the diarizer
and the voice model). They go to the Hugging Face cache, shared with other tools. `saidby doctor
--smoke` then runs a few seconds of real transcription to prove the whole stack works.

## 4. Your first transcript

```bash
saidby process call.m4a --out out/ --language es
```

```
device      GPU · cuda · NVIDIA GeForce RTX 4060 Laptop GPU · 8 GB   (auto → cuda)
[1/1] audio      ffmpeg · 15:07 of audio   0:01
[1/1] transcript faster-whisper large-v3 · cuda   1:33 · 9.8x faster than the audio
[1/1] speakers   nemotron3 · cuda · 2 speakers   0:08 · 113x faster than the audio
[1/1] done       out/call · 2 speakers · 2 tracks
[total]    1:52   started 9:27:10 PM · finished 9:29:02 PM · 15:07 of audio · 8.1x faster than the audio
```

The first line says which device does the work. Then one line per step that takes time, with how
fast it went compared with the length of the audio; the quick steps (aligning words, writing the
tracks and files) are counted in the `done` line. The last line is the whole run: its duration,
when it started and finished, and the speed over all the audio. `logs/run.log` and
`--progress json` list every step. When something is left to do, the run ends by saying what
and which command does it:

```
  name:     saidby speakers map out/call --set SPEAKER_00=NAME
  review:   saidby review out/call   3 doubtful spans
```

Open `out/call/transcript.txt`:

```
[00:00:03] SPEAKER_00: Hola, buenas tardes, ¿cómo vas con el informe?
[00:00:07] SPEAKER_01: Bien, ya casi lo termino. Me falta la parte de Acme.
```

The other files are described in [how it works](how-it-works.md#the-folder-you-get). Pass
`--language` when you know it: it is faster and more accurate than detecting it.

To stop retyping it, set the folder up once:

```bash
saidby init --language es
```

It writes `saidby.toml` (language and output folder), an empty `directory.yaml` and a
`consent.yaml`. From then on `saidby process call.m4a` needs no flags in that folder. Run
`saidby init --global` instead to set defaults for every folder.

## 5. Put names on the speakers

Create a directory and add the people:

```bash
saidby directory init directory.yaml --language es
```

```yaml
people:
  - id: ana
    name: Ana Gómez
  - id: ben
    name: Ben Ruiz
```

Enroll each voice from a finished run, recording that the person agreed:

```bash
saidby enroll out/call --speaker SPEAKER_00=ana --directory directory.yaml \
  --consent-source "signed form" --consent-declared-by "Ana Gómez"
saidby enroll out/call --speaker SPEAKER_01=ben --directory directory.yaml \
  --consent-source "signed form" --consent-declared-by "Ben Ruiz"
```

From now on:

```bash
saidby process next-call.m4a --out out/ --directory directory.yaml
```

```
[00:00:03] Ana Gómez: Hola, buenas tardes, ¿cómo vas con el informe?
```

If the diarizer split one person in two, or you want to rename someone, use
`saidby speakers merge` and `saidby speakers map`: they rewrite the results without reprocessing
audio.

## 6. Teach it your words

Add the terms the recognizer gets wrong to the same file:

```yaml
terms:
  - term: Acme
    variants: [akme, acne]        # how it usually comes out wrong
    context: our biggest customer
  - term: parce
    type: dialect                 # slang: always written the same way
    variants: [parse]
```

Run again with `--directory directory.yaml`. Each change is listed in
`out/call/corrections.jsonl`. Add `--correct` to let a local LLM catch what the second pass
missed (it needs [llama.cpp](https://github.com/ggml-org/llama.cpp) and one more download:
`saidby models pull llm:qwen3.5-9b-q4`).

## 7. Fix what is still wrong

```bash
saidby process call.m4a --out out/ --directory directory.yaml --compare pyannote-community1
saidby review out/call --directory directory.yaml
```

`review` shows the spans the machine is least sure about. Type the right text, or press Enter to
keep what is there. Spellings you fix are offered to your directory as new variants.

## Where to go next

- [Commands](commands.md): every command, when to use it, exit codes and the config file.
- [How it works](how-it-works.md): the stages, the glossary, privacy.
- [Troubleshooting](troubleshooting.md): when something does not work.
- [Evaluation](evaluation.md): how to measure whether it is better than what you use today.
