# Command reference

Every command exits 0 on success and 1 on failure. Expected failures print an `error:` line
and usually a `hint:` line on standard error; add `--debug` before the command to see the
full traceback instead. Commands that write files print `wrote <path>` for each.

```text
cv-gen [--debug] [--version] COMMAND [OPTIONS]
```

## build

Extract from the sources and write every output format.

```sh
cv-gen build                                   # everything from ./cv-gen.config.yaml
cv-gen build -c ~/cv/cv-gen.config.yaml -f pdf -f docx
cv-gen build -a file -o path=resume.yaml --out out/   # no config file needed
```

| Option | Meaning |
|---|---|
| `-c`, `--config PATH` | Configuration file (default `./cv-gen.config.yaml`) |
| `-a`, `--adapter NAME` | Use this adapter instead of the configured sources |
| `-o`, `--option KEY=VALUE` | An adapter option (repeatable); values are read as YAML scalars, so `timeout=5` is a number |
| `--plugin-path DIR` | Folder to import plugins from (repeatable) |
| `-f`, `--format FORMAT` | Output format (repeatable): `md`, `txt`, `docx`, `json`, `html`, `pdf`; also `markdown`, `text`, `word` |
| `--out DIR` | Output folder |
| `--design REF` | Design system: a DTCG tokens file or `https` URL |
| `--design-sha256 HASH` | Refuse the design system unless its SHA-256 matches |
| `--pdf-engine NAME` | `auto`, `chrome`, `playwright` or `weasyprint` |
| `--basename NAME` | Output file name without extension |

If one format fails (typically PDF with no engine installed), the others are still
written, the failure is reported, and the exit code is 1. If the guard finds a forbidden
term, nothing is written.

## extract

Run the source adapters and print the merged standard model as JSON; `-O FILE` writes it
to a file instead. Takes `--config`, `--adapter`, `--option` and `--plugin-path` like
`build`. Use it to see what an adapter or profile produces, or to snapshot a source:

```sh
cv-gen extract -a web -o profile=profiles/about.yaml -o url=https://me.example/about -O resume.json
```

## render

Render a standard-model file (JSON or YAML) without running any adapter. Takes the
output options of `build`; `--config` is optional and supplies render options, design,
guard and output defaults.

```sh
cv-gen render resume.json -f md -f txt --out out/
```

## validate

Check a JSON or YAML file against the standard model, naming every failing field.

## schema

Print the model's JSON Schema (`-O FILE` to write it), for editors and other tools.

## formats

List the output formats with their extensions.

## adapters list | show

`adapters list` shows every adapter: built-ins, installed plugins, and (with `--config` or
`--plugin-path`) plugin folders. `adapters show NAME` prints an adapter's description and
its options as JSON Schema; `NAME` may be a `module:Class` reference.

## design validate

`design validate REF [--sha256 HASH]` loads a design system, reports which tokens it
supplies and which it ignores, and prints every resolved value (`*` marks the supplied
ones).

## Environment

| Variable | Meaning |
|---|---|
| `CV_GEN_CHROME` | The Chromium-family browser the `chrome` PDF engine runs |
