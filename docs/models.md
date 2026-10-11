# Models

The registry in `saidby.models.registry` pins every model to a full revision. See
[MODEL_LICENSES.md](../MODEL_LICENSES.md) for licenses and attribution.

- `saidby models list` shows what is installed.
- `saidby models pull KEY...` or `--all` downloads models. It is the only command that uses
  the network.
- Gated models need a Hugging Face token (`HF_TOKEN`) and accepted conditions; the error
  message includes the URL.
- Models that are not licensed for commercial use are refused unless `--allow-noncommercial`
  is given, and never are defaults.
