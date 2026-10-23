# Walkthrough: cv-gen

cv-gen 0.1.0 is a Python command-line tool. Pluggable source adapters turn a source into one standard resume model, and generators turn that model into Word, Markdown, plain text, JSON, HTML and PDF. HTML and PDF are styled by a DTCG design-tokens file. The first real adapter, for coreystruzan.com/about, lives in the private, git-ignored `cv-gen-corey` repository. It is a profile plus one transform for the generic web engine, not engine code.

## What Was Implemented

### 1. Model, configuration and adapter layer
- **`src/cv_gen/model.py`**: the standard model. It is JSON Resume 1.0 plus `basics.headline`, `periods`, `tags`, custom `sections` and `meta.sources`. Dates are ISO partial dates, unknown keys are kept, and empty values are pruned on output.
- **`src/cv_gen/errors.py`**: `CvGenError(message, hint)` and validation messages qualified by path (`work[0].startDate: …`).
- **`src/cv_gen/config.py`, `merge.py`**: the YAML configuration, with relative paths resolved against the config file. Sources merge in order, with `replace` or `append` list semantics.
- **`src/cv_gen/adapters/`**: the adapter contract (a typed options model plus `extract()`) and the registry. Adapters are found as built-ins, as `cv_gen.adapters` entry points, or as `module:Class` references on plugin paths. Includes the `file` adapter.

### 2. Generic web-extraction engine
- **`src/cv_gen/adapters/web/`**: profiles map CSS selectors to model fields. Features: `each`/`fields` records, global `exclude` and per-field `drop`, a `"."` merge target, constants and defaults, required selectors, and a schema.org Person JSON-LD baseline. Named transforms include `date_range` (open ranges, dash variants, month names, multiple periods) and `lead_sentence`; plugin modules can add more with `@transform`.
- **`src/cv_gen/fetch.py`**: fetches over http(s) with a timeout, a 5 MB cap and errors that name the URL. Design-system URLs are https-only.

### 3. Generators and design systems
- **`src/cv_gen/generators/view.py`**: one section view for every format. It decides section order, titles, omission of empty sections and date wording.
- **Markdown, text, JSON, Word**: real heading levels; wrapped text with underlined headings; the model as JSON Resume; Word with `Title`/`Heading 1`/`Heading 2` styles, real lists, no tables, hyperlinks and core properties.
- **HTML** (`html.py`, `templates/`): overridable Jinja2 templates with autoescaping and a safe-scheme link filter. The stylesheet comes from validated tokens, with print rules and a full-bleed `@page` background. The page embeds JSON-LD that cannot close its script element.
- **PDF** (`pdf/engines.py`): the `chrome` engine (installed Chrome, Edge or Chromium, no packages), plus optional `playwright` and `weasyprint` engines. `auto` falls through to whichever works.
- **`src/cv_gen/design/`**: DTCG tokens in JSON or YAML, from a path or a sha256-pinned https URL. Aliases resolve across the defaults and the user's file. Every value is parsed by its type and re-serialized. Local design systems may add custom CSS and font imports.
- **`src/cv_gen/guard.py`, `pipeline.py`**: all formats render in memory, the forbidden-terms guard runs, and only then is anything written. A guard hit writes nothing; a failed format such as PDF doesn't stop the others.

### 4. CLI, example and documentation
- **`src/cv_gen/cli.py`**: `build`, `extract`, `render`, `validate`, `schema`, `formats`, `adapters list|show` and `design validate`. Errors are one line, with `--debug` for tracebacks. Output is UTF-8 safe on Windows consoles.
- **`examples/adapter-example/`**: an installable adapter package, registered through the entry point, with tests and a README on adapting it. The dev environment installs it.
- **`docs/`**: guides to configuration, the CLI, writing adapters, web profiles, design tokens and the model. Also a README, a CHANGELOG, `cv-gen.config.example.yaml`, a fictional sample resume, and serif and compact sample design systems.

### 5. Private adapter (`cv-gen-corey`, its own repository, git-ignored here)
- **`profiles/about.yaml`**: the coreystruzan.com/about profile. It reads identity and links, the headline and summary, Current focus, the Timeline (12 entries, roles split from descriptions, Intel's two periods), Tools & Skills (14 groups) and the Origin story with the Tamino callout. It excludes `.only-phone`, so every field carries the desktop wording.
- **`transforms.py`**: `kind_label`, which turns the Timeline's `data-kind` codes into the page's key labels.
- **`designs/`**: Neon Underground design systems in two editions: `paper` (print, from the site's light-theme tokens) and `dark` (screen). The HTML and PDF load the site's Fontsource fonts.
- **`config/cv-gen.config.yaml`**: the master copy of the git-ignored `cv-gen.config.yaml`. **`config/overlay.example.yaml`** is a template for private details (`*.local.yaml` is ignored).

## Verification & Test Results

### Automated Tests
Ran the full suite, `uv run pytest`:
- **196 passed** across the model, config, adapters, web engine, transforms, generators, design tokens, PDF, pipeline, CLI, docs and the example adapter's own tests.
- Coverage: **97.31%** (line and branch combined), above the gate set at 80% (`--cov-fail-under=80`).
- The browser test printed a real PDF through headless Chrome and read its text back with pypdf: **Passed**.
- Network tests use a local HTTP server or the reserved `.invalid` domain, so the suite runs offline: **Passed**.
- `ruff check` and `ruff format --check`: **Passed**.
- `cv-gen-corey`: 8 tests against the saved page (identity, timeline, skills, sections, no phone wording, designs): **Passed**.

### Regression Testing
The suite ran after every task. Three defects surfaced while verifying against the live page; each was fixed in its own commit with a regression test:
- Word core properties over 255 characters (a long skills list) crashed the Word generator. Keywords now stop at the last whole item that fits.
- A colored design printed with white page margins. The `@page` rule now carries the background.
- A list item with a link but no title lost its link in Markdown and HTML.

Two CLI tests also failed once a personal `cv-gen.config.yaml` existed in the checkout, because commands read it from the working directory. Every test now runs from an empty folder.

### End-to-end
`cv-gen build` with the private config against the live https://coreystruzan.com/about wrote all six formats to `out/corey/`, and each was read back:
- the JSON validates;
- the PDF is 2 pages, embeds Big Shoulders Stencil Display and Chivo, and contains the name and all 12 organizations;
- the Word file has 5 `Heading 1` sections and no tables;
- no output contains the phone-only wording.

## Manual Verification
1. From `cv-gen/`, run `uv run cv-gen build`, then open `out/corey/corey-struzan-cv.pdf` and check the layout, the fonts and the paper ground on both pages.
2. Open `out/corey/corey-struzan-cv.docx` in Word. Check that the Navigation pane lists Summary, Current focus, Experience, Skills and Origin story, and that links work. Chivo shows only if it is installed; otherwise Word substitutes a font.
3. Try the screen edition: `uv run cv-gen build --design cv-gen-corey/src/cv_gen_corey/designs/neon-underground-dark.tokens.json -f html -f pdf`.
4. Decide what the overlay should hold, if anything. Copy `cv-gen-corey/config/overlay.example.yaml` to `overlay.local.yaml`, fill it in, and uncomment the overlay source in `cv-gen.config.yaml` and in its master copy.
5. Add the never-name terms from the site's content rules to `guard.forbidden_terms` in both copies of the config. They were deliberately not written into any file.
6. `cv-gen-corey` has no remote yet. Push it to a private repository: `git -C cv-gen-corey remote add origin <private-url>`, then `git -C cv-gen-corey push -u origin main`.

## Follow-ups
- **LinkedIn**: an adapter for LinkedIn's official "Download your data" export (CSV files), rather than scraping, which LinkedIn's terms forbid.
- **Design-system registry**: a public repository of DTCG design systems addressed by URL. URL loading with a `sha256` pin already exists; a short name such as `gh:owner/repo/name@tag` would be a small addition.
- **Tailored variants**: named profiles that pick sections and filter work entries by tag (`tags` is already extracted), for example a games CV or a one-page CV.
- **Automation**: a scheduled job that rebuilds the CV when the site deploys, and a check that diffs a fresh page against the saved fixture.
- **ATS check**: a lint command that flags layout risks (missing contact details, very long bullets) before sending a CV.
