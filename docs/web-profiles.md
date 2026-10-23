# Web extraction profiles

The `web` adapter turns any web page into the [standard model](model.md) using a
**profile**: a YAML file that says which CSS selectors hold which fields. Supporting a new
site means writing a profile, not code.

```sh
cv-gen extract --adapter web -o profile=my-site.yaml -o url=https://me.example/about
cv-gen extract --adapter web -o profile=my-site.yaml -o path=saved/about.html   # offline
```

The worked example is [`examples/profiles/generic-about.yaml`](../examples/profiles/generic-about.yaml),
run against the fictional page [`tests/fixtures/web/about.html`](../tests/fixtures/web/about.html).

## How a page is read

1. The page is fetched (`url`) or read from disk (`path`).
2. If `jsonld` is on (the default), a schema.org `Person` in the page's JSON-LD fills
   `basics`: name, job title, description, email, phone, image, address and `sameAs` links
   (as profiles). Many personal sites publish one for search engines, so this alone often
   yields a usable header.
3. Elements matching `exclude` are removed.
4. `fields` are evaluated. Anything they produce overrides the JSON-LD baseline, field by
   field.
5. Empty values are dropped and the result is validated against the model.

## Profile keys

```yaml
name: my-site-about                 # informational
url: https://me.example/about       # the default page; the url/path options override it
jsonld: true                        # read a schema.org Person into basics first
exclude: [".mobile-only"]           # removed before extraction
transforms_module: my_plugin.transforms   # optional; a name or a list
fields:
  <target path>: <field spec>                  # or a list of specs, concatenated
```

A **target path** is a dotted path into the model: `basics.headline`,
`basics.location.city`, `work`, `sections`. Inside a record, paths are relative to the
record (`name`, `location`). The special target `"."` merges a mapping into the current
record (see [one element, several fields](#one-element-several-fields)).

## Field specs

| Key | Meaning |
|---|---|
| `selector` | CSS selector, relative to the current scope. Omit it to read the scope element itself. |
| `attr` | Read this attribute instead of the text (`href`, `data-kind`, `datetime`). |
| `extract` | `text` (default), `attr`, `json` (parse the attribute or text as JSON), `html` (inner HTML). |
| `all` | `true` returns a list of every match instead of the first. |
| `drop` | Selectors removed from a copy of the matched element before it is read. |
| `transforms` | Transforms applied in order (see below). |
| `required` | `true` fails the build when the selector matches nothing. |
| `default` | The value when an optional selector matches nothing. |
| `value` | A constant; nothing is read from the page. |
| `each` + `fields` | One record per element matching `each`; `fields` describe a record, relative to that element. |
| `fields` (without `each`) | One nested object built inside the matched element. |

Text is read with whitespace collapsed, `<br>` counted as a space, and inline elements
joined without inserted spaces (`Alpha<span>, beta</span>` reads `Alpha, beta`).

### Lists of records

```yaml
work:
  each: "#experience li.job"     # one work entry per <li class="job">
  required: true                 # fail if the page has no jobs at all
  fields:
    name: { selector: ".org", required: true }
    url: { selector: ".org a", attr: href, transforms: [absolute_url] }
    tags: { attr: data-kind, transforms: [as_list] }
```

`selector` and `each` combine: `selector` narrows the scope, then `each` repeats inside it.

### One element, several fields

A transform that returns a mapping is applied to the `"."` target, which merges the
mapping into the record. Give `"."` a list to merge several:

```yaml
".":
  - { selector: ".dates", transforms: [date_range] }      # startDate, endDate, periods
  - { selector: ".desc", transforms: [lead_sentence] }    # position, summary
```

### Custom sections

`sections` holds content JSON Resume has no place for. Each record needs an `id` (a
lowercase slug that is not a built-in section name) and a `title`:

```yaml
sections:
  - each: "#now"
    fields:
      id: { value: now }
      title: { selector: "h2" }
      items:
        each: ".now-item"
        fields:
          title: { selector: "b" }
          text: { drop: ["b", "a"] }     # the paragraph without its bold lead and link
  - each: "#story"
    fields:
      id: { value: story }
      title: { selector: "h2" }
      paragraphs: { selector: "p", all: true }
```

### Responsive duplicates

Sites often render a long and a short version of the same text for different screens. Put
the version you don't want in `exclude`, or the result reads both, run together.

## Built-in transforms

A transform is a name, or a one-key mapping from the name to its arguments (a mapping of
keyword arguments, a list of positional ones, or a single value). String transforms also
work element-wise on lists.

| Transform | Does | Example |
|---|---|---|
| `normalize` | Collapse whitespace, trim | `normalize` |
| `lower`, `upper` | Change case | `lower` |
| `replace` | Replace text | `{replace: {old: "&", new: "and"}}` |
| `strip_prefix`, `strip_suffix` | Remove a prefix or suffix when present | `{strip_prefix: "@"}` |
| `regex` | First match's capture group (default 1), or nothing | `{regex: {pattern: "(\\d{4})"}}` |
| `split` | Split into a trimmed list | `{split: {sep: "·"}}` |
| `join` | Join a list | `{join: ", "}` |
| `as_list` | Wrap a single value in a list | `as_list` |
| `first` | First item of a list | `first` |
| `map` | Look up in a table; keep the value, or use `default`, when absent | `{map: {mapping: {agency: Agency}}}` |
| `absolute_url` | Resolve a relative link against the page URL (or `base_url`) | `absolute_url` |
| `date_range` | Parse written dates into `startDate`/`endDate`/`periods` | `date_range` |
| `lead_sentence` | Split a short first sentence into one field and the rest into another | `{lead_sentence: {max_words: 4, lead: position, rest: summary}}` |

`date_range` reads `2022`, `2021–`, `2013 - 2019`, `Jan 2020 to present`,
`Sept. 2019 – March 2021`, `4/2018 - 12/2019` and comma- or semicolon-separated periods
(`2006–2007, 2010–2013`). Use a dash between two years; `2010-12` is read as December 2010.

`lead_sentence` turns `Founder. Game studio, Paydirt.` into `position: Founder` and
`summary: Game studio, Paydirt.`; text whose first sentence is longer than `max_words`
words, or that is one sentence, goes entirely to `rest`.

## Custom transforms

When a site needs logic, write a module of transforms and name it in the profile:

```python
# my_plugin/transforms.py
from cv_gen.adapters.web import TransformContext, transform


@transform("kind_label")
def kind_label(value, ctx: TransformContext, labels=None):
    """Turn a data-kind code into words."""
    labels = labels or {"founder": "Founder", "agency": "Agency"}
    return labels.get(value, value)
```

```yaml
transforms_module: my_plugin.transforms
fields:
  work:
    each: "li.job"
    fields:
      tags: { attr: data-kind, transforms: [kind_label, as_list] }
```

The module must be importable: installed, or in a folder listed under `plugins.paths` in
the configuration. A transform receives the current value and a `TransformContext`
(`base_url`, and `field`, the path being built, for error messages); raise `ValueError` for
bad input and cv-gen reports it against the field. Registering an existing name replaces
it, deliberately.

## Options of the web adapter

| Option | Default | Meaning |
|---|---|---|
| `profile` | (required) | The profile file |
| `url` | the profile's `url` | The page to fetch |
| `path` | | Read a saved copy of the page instead of fetching |
| `base_url` | the page URL | What relative links resolve against (useful with `path`) |
| `timeout` | 20 | Seconds before a fetch fails |
| `user_agent` | `cv-gen/<version>` | The User-Agent header |

Pages larger than 5 MB are refused. Fetch failures name the URL and the cause.

## Testing a profile

Save the page (`curl -L https://me.example/about -o tests/about.html`), run
`cv-gen extract --adapter web -o profile=... -o path=tests/about.html`, and assert on the
result in a test. Mark the selectors your CV can't do without as `required: true`: when the
site is redesigned, the build fails naming the field rather than quietly producing a CV with
an empty Experience section.

Respect the sites you read: extract your own pages, or pages whose terms allow it.
