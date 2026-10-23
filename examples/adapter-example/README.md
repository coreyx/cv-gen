# cv-gen example adapter

A complete, installable cv-gen source adapter. It reads a small TOML "profile" format
([`sample-profile.toml`](sample-profile.toml)) that is deliberately unlike the cv-gen
model, and maps it onto the model. Copy this folder to write an adapter for your own source.

The full guide is [docs/adapters.md](../../docs/adapters.md).

## Try it

From the cv-gen checkout, where the development environment already installs this package:

```sh
uv run cv-gen adapters list          # example-toml is listed
uv run cv-gen extract --adapter example-toml -o path=examples/adapter-example/sample-profile.toml
uv run cv-gen build   --adapter example-toml -o path=examples/adapter-example/sample-profile.toml --out out/example
```

Or install it into any environment that has cv-gen:

```sh
pip install ./examples/adapter-example
```

## Make it yours

1. Copy the folder and rename the package (`cv_gen_example_adapter`) and the project
   (`cv-gen-example-adapter`).
2. In `pyproject.toml`, change the entry point: the name on the left becomes the adapter's
   name in configs and on the command line.
3. In `__init__.py`, change the options model to the settings your source needs, set `name`
   and `description`, and rewrite `to_model()` to map your source's shape onto the model.
4. Replace the sample file and the tests. `uv run pytest` runs them.

Not ready to package it? Skip the entry point: put the folder under `plugins.paths` in your
config and name the adapter as `your_module:YourAdapter`.

## Files

| File | What it shows |
|---|---|
| `pyproject.toml` | The `cv_gen.adapters` entry point that registers the adapter |
| `src/cv_gen_example_adapter/__init__.py` | Options model, adapter class, mapping, error handling |
| `sample-profile.toml` | A source in the made-up format |
| `tests/test_adapter.py` | Testing the mapping, the options, the errors and the registration |
