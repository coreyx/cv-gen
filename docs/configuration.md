# Configuration

`cv-gen build` reads `cv-gen.config.yaml` in the working directory, or the file named
with `--config`. The repository commits only
[`cv-gen.config.example.yaml`](../cv-gen.config.example.yaml): copy it to
`cv-gen.config.yaml` (git-ignored, as is anything named `*.local.yaml`) and edit the copy.
Personal sources, overlays with contact details and private adapters stay out of version
control that way.

Relative paths anywhere in the file resolve against **the file's own folder**, so
`cv-gen build --config ~/cv/cv-gen.config.yaml` works from any directory. Paths given on
the command line resolve against the working directory.

## Full reference

```yaml
plugins:
  paths: [./my-adapters]           # folders to import plugin modules from

# One source...
source:
  adapter: web                     # a name (cv-gen adapters list) or module:Class
  options:                         # validated against the adapter's options
    profile: ./profiles/about.yaml
    url: https://me.example/about

# ...or several, merged in order (use one of source/sources).
sources:
  - adapter: web
    options: {profile: ./profiles/about.yaml}
  - adapter: file
    options: {path: ./private-overlay.local.yaml}
    merge: replace                 # replace (default) or append

output:
  dir: out                         # where files go
  basename: null                   # file name without extension; default: <name>-cv
  formats: [md, txt, docx, json, html]   # add pdf when a PDF engine is available

design: ./designs/mine.tokens.json # or {ref: https://…, sha256: …}; see design-tokens.md

render:
  sections: null                   # ids to include, in order; null = all, in the default order
  section_titles: {work: Experience}
  text_width: 80                   # 40–200, plain-text wrapping
  templates: null                  # folder of HTML template overrides

pdf:
  engine: auto                     # auto, chrome, playwright or weasyprint

guard:
  forbidden_terms: []              # words that must never appear in any output
```

Unknown keys are errors, so a typo is reported instead of silently ignored.

## Sources and merging

Sources run in order and merge:

- mappings merge key by key;
- a later scalar replaces an earlier one;
- a later list **replaces** an earlier list, unless that source has `merge: append`, which
  adds its items after the earlier ones;
- an absent or empty value never erases an earlier one.

The usual pattern is a public source followed by a private overlay that adds what the
public one lacks:

```yaml
# private-overlay.local.yaml
basics:
  email: me@example.com
  phone: "+1 555 0100"
education:
  - {institution: Example University, studyType: BSc, area: Physics, endDate: "2008"}
```

## Sections

The default order is: `summary`, `work`, `projects`, `skills`, `education`, `certificates`,
`awards`, `publications`, `volunteer`, `languages`, `interests`, `references`, then custom
sections in source order. `render.sections` picks and orders them, custom section ids
included. Empty sections are always left out. Unknown ids fail the build, listing the ids
available.

Default titles: Summary, Experience, Projects, Skills, Education, Certifications, Awards,
Publications, Volunteering, Languages, Interests, References. Custom sections use their own
title. `render.section_titles` renames any of them.

## The guard

`guard.forbidden_terms` lists words or phrases that must never reach a CV: an NDA client,
an unannounced product, an old name. Matching is case-insensitive and whole-word. Before
anything is written, every output's visible text is checked (Word documents are read back,
PDFs are checked through the page they are printed from); one hit fails the build and
**no** file is written.

## Command line overrides

`--format`, `--out`, `--design`, `--design-sha256`, `--pdf-engine` and `--basename`
override the configuration for one run. `--adapter` with `--option key=value` replaces the
configured sources; with `--adapter`, no configuration file is needed at all. See
[cli.md](cli.md).
