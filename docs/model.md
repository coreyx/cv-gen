# The standard model

Every adapter produces, and every generator reads, one data model: the
[JSON Resume 1.0 schema](https://jsonresume.org/schema) plus a few documented extensions.
A cv-gen JSON file is therefore a valid JSON Resume document, usable by JSON Resume themes
and tools, and a JSON Resume file can be fed straight to the `file` adapter.

`cv-gen schema` prints the exact JSON Schema; `cv-gen validate FILE` checks a file
against it.

## Shape

```yaml
basics:
  name, label, headline*, image, email, phone, url, summary
  location: {address, postalCode, city, countryCode, region}
  profiles: [{network, username, url}]
work:          [{name, position, url, location, description, startDate, endDate,
                 periods*, summary, highlights, tags*}]
projects:      [{name, description, highlights, keywords, startDate, endDate, periods*,
                 url, roles, entity, type, tags*}]
education:     [{institution, url, area, studyType, startDate, endDate, score, courses}]
volunteer:     [{organization, position, url, startDate, endDate, summary, highlights}]
awards:        [{title, date, awarder, summary}]
certificates:  [{name, date, url, issuer}]
publications:  [{name, publisher, releaseDate, url, summary}]
skills:        [{name, level, keywords}]
languages:     [{language, fluency}]
interests:     [{name, keywords}]
references:    [{name, reference}]
sections*:     [{id, title, updated, paragraphs, items: [{title, subtitle, text, url, date}]}]
meta:          {canonical, version, lastModified, sources*: [{adapter, location}]}
```

`*` marks an extension.

## Rules

- **Dates** are ISO 8601 partial dates: `2021`, `2021-04` or `2021-04-15`. An absent
  `endDate` means "present". Generators word them for people: `2021`, `Apr 2021`,
  `2013 – 2019`, `2021 – Present`.
- **Unknown keys are kept**, at any level, so data from other tools survives a round trip;
  generators ignore them.
- **Empty values are dropped** on output: empty strings, empty lists and empty mappings.
- **Custom section ids** are lowercase slugs (`current`, `origin-story`), unique, and may
  not reuse a built-in section name (`work`, `skills`, …).

## Extensions

| Field | Why |
|---|---|
| `basics.headline` | A one-line tagline, separate from the job `label` ("I turn slow, fragile services into fast, boring ones."). |
| `periods` (work, projects) | Separate stretches at the same place (`2006–2007, 2010–2013`). `startDate`/`endDate` still give the overall span, for tools that only read those. |
| `tags` (work, projects) | Free-form labels (`founder`, `agency`) for filtering or styling; not printed by default. |
| `sections` | Content JSON Resume has no place for: a "Current focus" list, an origin story, talks. Rendered as their own sections, placed by `render.sections`. |
| `meta.sources` | Which adapters produced the document, and from where. |

## Example

[`examples/sample-resume.yaml`](../examples/sample-resume.yaml) uses most of the model,
including periods and a custom section.
