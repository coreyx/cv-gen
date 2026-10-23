# Writing a source adapter

An adapter is the only part of cv-gen that knows about a particular source. It reads
that source and returns the [standard model](model.md); every generator then works
from the model, so a new adapter gets Word, Markdown, text, JSON, HTML and PDF for free.

Before writing code, check whether you need to:

| Your source is | Use |
|---|---|
| A JSON Resume file, or YAML/JSON already in the cv-gen model | the built-in `file` adapter |
| A web page | the built-in `web` adapter with an [extraction profile](web-profiles.md) (no code) |
| A web page that needs a little logic | the `web` adapter plus a [transforms module](web-profiles.md#custom-transforms) |
| Anything else: an export file, an API, a database | a custom adapter (this guide) |

A complete, tested example lives in [`examples/adapter-example`](../examples/adapter-example):
copy it as your starting point.

## The contract

```python
from pathlib import Path

from cv_gen.adapters import Adapter, AdapterContext, AdapterOptions, Resume
from cv_gen.errors import CvGenError


class MyOptions(AdapterOptions):
    """The settings a config's `options:` may contain. Unknown keys are rejected."""

    path: Path
    include_links: bool = True


class MyAdapter(Adapter):
    name = "my-format"  # how configs and the CLI select it
    description = "My export format."  # shown by `cv-gen adapters list`
    Options = MyOptions

    def extract(self, options: MyOptions, ctx: AdapterContext) -> Resume:
        path = ctx.resolve(options.path)  # relative to the config file's folder
        if not path.is_file():
            raise CvGenError(f"no such file: {path}", "check options.path")
        data = parse_my_format(path)  # your code
        return Resume.from_data(
            {
                "basics": {"name": data["full_name"], "label": data["headline"]},
                "work": [
                    {"name": job["org"], "position": job["title"], "startDate": job["from"]}
                    for job in data["jobs"]
                ],
            }
        )
```

What each part does:

- **`Options`**: a Pydantic model. cv-gen validates a config's `options:` (or the CLI's
  `-o key=value` pairs) against it before calling `extract`, rejects unknown keys, and shows
  it as JSON Schema in `cv-gen adapters show <name>`. Give every field a type and, where
  sensible, a default.
- **`extract(options, ctx)`**: return a `Resume`. Building plain data and calling
  `Resume.from_data` is the simplest route: validation names any bad field
  (`work[2].startDate: '2021-13' is not in the expected format`). Empty strings, empty
  lists and `None` are pruned from output, so you need not filter them yourself.
- **`ctx.resolve(path)`**: resolves a relative path against the configuration file's folder
  (or the working directory, when the adapter is named on the command line).
- **`CvGenError(message, hint)`**: raise it for expected failures (missing file, bad
  input, unreachable service). The CLI prints `error:` and `hint:` lines without a
  traceback. Anything else is treated as a bug and shown in full.
- **`describe_source(options)`** (optional): what to record in `meta.sources`. The default
  uses an option called `url` or `path`.

Dates in the model are ISO partial dates: `2021`, `2021-04` or `2021-04-15`. An absent
`endDate` means "present". If your source writes ranges in prose, the web engine's parser
is reusable: `from cv_gen.adapters.web.dates import parse_date_range`.

## Making cv-gen find it

Three ways, from most to least formal:

1. **An installed package with an entry point.** In your `pyproject.toml`:

   ```toml
   [project.entry-points."cv_gen.adapters"]
   my-format = "my_package.adapter:MyAdapter"
   ```

   After `pip install` (or `uv pip install -e .`), `cv-gen adapters list` shows `my-format`
   and configs use `adapter: my-format`. A plugin cannot take a built-in's name.

2. **A `module:Class` reference on a plugin path, with no installation.** Keep the code in
   any folder and point the config at it:

   ```yaml
   plugins:
     paths: [./my-adapters]            # added to the import path
   source:
     adapter: my_adapter:MyAdapter     # module:Class
     options: {path: ./export.json}
   ```

   This suits private, personal adapters: keep the folder outside the repository (or
   git-ignored) and the config that names it git-ignored too.

3. **A `module:Class` reference to anything already importable**, on the command line:
   `cv-gen extract --adapter my_package.adapter:MyAdapter -o path=export.json`.

## Packaging a profile as an adapter

A web profile can ship inside a plugin as its own named adapter, so users need not know
where the YAML lives:

```python
from pathlib import Path

from cv_gen.adapters.web import WebAdapter


class MySiteAdapter(WebAdapter):
    name = "my-site"
    description = "my-site.example/about"
    default_profile = Path(__file__).parent / "profiles" / "about.yaml"
```

`profile` then becomes optional for that adapter; `url`, `path`, `timeout` and the other
web options still apply.

## Testing an adapter

Test the adapter the way cv-gen calls it: validate options from a mapping, pass a context
with a known base folder, and check the returned model. `examples/adapter-example/tests`
shows each case worth covering:

- a sample source mapping to the expected fields;
- each option changing the output;
- missing and malformed input raising `CvGenError`;
- unknown options being rejected;
- the entry point registering the adapter (`available_adapters()["my-format"]`).

For web adapters, keep a saved copy of the page in your tests and use the `path` option,
so the tests run offline and a site redesign shows up as a failing test rather than a
broken CV.

## Merging with other sources

A configuration may list several sources; they merge in order (see
[configuration](configuration.md#sources-and-merging)). An adapter therefore only has to
return what its source knows: a private overlay file can add an email address or education
that a public source never mentions.
