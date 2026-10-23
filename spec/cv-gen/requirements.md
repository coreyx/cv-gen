---
status: approved
---

# Requirements Specification: cv-gen

## 1. Project Summary

This spec builds the first version of cv-gen: a Python command-line tool with three layers. A **source adapter** reads one source (a file, a web page, anything a plugin can reach) and returns the **standard resume model**. **Generators** turn that model into DOCX, Markdown, plain text and JSON, and, styled by an optional **design system** in the W3C Design Tokens (DTCG) format, into HTML and PDF.

It also delivers a documented, copyable example adapter, a generic declarative web-extraction engine, and the first real adapter: a profile and small plugin for coreystruzan.com/about that live in a separate, git-ignored `cv-gen-corey` package, wired in through a git-ignored config that follows the config-example pattern.

**Related documents**
- [Product](product.md)

## 2. Requirements (EARS Format)

### REQ-1: Standard resume model

**User Story**: As an adapter author, I want one well-defined data model to produce, so that every generator works with every adapter.

- **1.0.1 (Ubiquitous)**: The system shall define a resume model that is a superset of the JSON Resume 1.0 schema (basics, work, volunteer, education, awards, certificates, publications, skills, languages, interests, references, projects, meta).
- **1.0.2 (Ubiquitous)**: The model shall add, as documented extensions, `basics.headline`, per-entry `periods` (a list of start/end ranges), per-entry `tags`, and a list of free-form custom `sections` (each with an id, a title, paragraphs and items).
- **1.0.3 (Ubiquitous)**: Dates shall be ISO 8601 partial dates (`YYYY`, `YYYY-MM` or `YYYY-MM-DD`); an absent end date means "present".
- **1.0.4 (Event-Driven)**: When asked, the system shall emit the model's JSON Schema.
- **1.0.5 (Unwanted Behavior)**: If a resume document fails validation, then the system shall report each failing field by its path and exit non-zero.

#### Acceptance Criteria
- **1.1**: A valid JSON Resume document from jsonresume.org's sample loads into the model without loss of any standard field.
- **1.2**: `cv-gen schema` prints a JSON Schema that validates the model's own JSON output.
- **1.3**: A document with `startDate: "2021-13"` fails validation with a message naming `work[0].startDate`, and the command exits non-zero.
- **1.4**: Custom `sections`, `periods`, `tags` and `headline` round-trip through JSON unchanged.

### REQ-2: Pluggable adapter layer

**User Story**: As a developer, I want to add a source without touching the core, so that any source can be supported.

- **2.0.1 (Ubiquitous)**: The system shall define an adapter contract: a name, a typed options model, and one method that returns a standard resume model.
- **2.0.2 (Ubiquitous)**: The system shall discover adapters from the built-ins, from the `cv_gen.adapters` Python entry-point group, and from a `module:Class` reference.
- **2.0.3 (Optional Feature)**: Where the configuration lists plugin paths, the system shall make modules under those paths importable before resolving adapters, so a plugin works without being installed.
- **2.0.4 (Event-Driven)**: When an adapter is selected, the system shall validate its options against the adapter's options model before running it.
- **2.0.5 (Unwanted Behavior)**: If an adapter name cannot be resolved, then the system shall list the available adapter names in the error.

#### Acceptance Criteria
- **2.1**: `cv-gen adapters list` shows every built-in adapter and every adapter registered by an installed entry point.
- **2.2**: `cv-gen adapters show web` prints the adapter's description and its options as a JSON Schema.
- **2.3**: An adapter referenced as `my_pkg.mod:MyAdapter` from a configured plugin path runs without installation.
- **2.4**: Passing an unknown option to an adapter fails before the adapter runs, naming the option.
- **2.5**: An unknown adapter name fails with a message listing the available names.

### REQ-3: Built-in file adapter

**User Story**: As a user, I want to feed an existing JSON Resume or YAML file in, so that I can render without writing an adapter.

- **3.0.1 (Ubiquitous)**: The system shall provide a `file` adapter that reads a JSON or YAML document in the standard model (JSON Resume included).

#### Acceptance Criteria
- **3.1**: `cv-gen extract --adapter file --option path=resume.yaml` writes the same model a JSON copy of that file produces.

### REQ-4: Generic web-extraction engine

**User Story**: As a site owner, I want to describe my page's structure declaratively, so that supporting a new site needs a profile, not an engine change.

- **4.0.1 (Ubiquitous)**: The system shall provide a `web` adapter that loads a page from an `http(s)` URL or a local file and applies an extraction profile.
- **4.0.2 (Ubiquitous)**: A profile shall map model fields to CSS selectors, with per-field extraction (text, attribute, inner HTML-free text, JSON in an attribute), lists of records, and named transforms applied in order.
- **4.0.3 (Ubiquitous)**: The engine shall provide built-in transforms: whitespace normalization, regex capture, split, prefix/suffix strip, date-range parsing (including multiple periods and open ranges written with `-`, `–` or `—`), lead-sentence split, and constant values.
- **4.0.4 (Ubiquitous)**: A profile shall be able to remove elements matching "exclude" selectors before extraction (for example, duplicated responsive variants).
- **4.0.5 (Ubiquitous)**: The engine shall read schema.org `Person` JSON-LD from the page as a baseline for `basics`, which explicit profile fields override.
- **4.0.6 (Optional Feature)**: Where a profile names a transforms module, the system shall register that module's transforms so profile fields can use them by name.
- **4.0.7 (Unwanted Behavior)**: If a fetch fails or times out, then the system shall report the URL and the cause and exit non-zero, without a traceback.
- **4.0.8 (Unwanted Behavior)**: If a profile selector marked required matches nothing, then the system shall fail naming the field and the selector; an optional selector that matches nothing leaves the field empty.

#### Acceptance Criteria
- **4.1**: The generic fixture page in the test suite extracts to the expected model using only a YAML profile.
- **4.2**: `2006–2007, 2010–2013` parses to two periods, start `2006`, end `2013`; `2024–` parses to start `2024` and no end; `2022` parses to start and end `2022`.
- **4.3**: An exclude selector removes the matched elements, so their text never appears in extracted fields.
- **4.4**: A page with Person JSON-LD and no profile `basics` fields yields name, label, location and profiles from the JSON-LD.
- **4.5**: A transform registered from a profile's transforms module is applied to the field that names it.
- **4.6**: A missing required selector fails naming the field; a fetch to an unreachable host fails with the URL in the message and no traceback.

### REQ-5: Multiple sources and overlays

**User Story**: As a user whose website lacks contact details, I want to layer a private file over the extracted data, so that the CV is complete without publishing those details.

- **5.0.1 (Ubiquitous)**: The configuration shall accept a list of sources, each with its own adapter and options.
- **5.0.2 (Ubiquitous)**: The system shall merge sources in order: mappings merge recursively, a later scalar replaces an earlier one, and a later list replaces an earlier list unless that source's merge mode is `append`.

#### Acceptance Criteria
- **5.1**: A web source followed by a file source carrying only `basics.email` yields the web data plus that email.
- **5.2**: A later source's `skills` list replaces the earlier one by default, and is appended to it under `merge: append`.

### REQ-6: Core generators

**User Story**: As a job seeker, I want Word, Markdown, text and JSON versions, so that I can send whatever is asked for, to people or to software.

- **6.0.1 (Ubiquitous)**: The system shall generate Markdown, plain text, DOCX and JSON from the standard model.
- **6.0.2 (Ubiquitous)**: Generated documents shall be readable by machines: real heading levels (DOCX heading styles, Markdown `#` levels), no tables used for layout, conventional section names, one entry per block, and document metadata (DOCX core properties: title, author, keywords).
- **6.0.3 (Ubiquitous)**: Plain text output shall be UTF-8, wrapped at a configurable width (default 80), with section headings underlined.
- **6.0.4 (Optional Feature)**: Where the render options name sections, the generators shall include only those sections, in that order.
- **6.0.5 (Ubiquitous)**: Empty sections shall be omitted from every format.

#### Acceptance Criteria
- **6.1**: The Markdown output has one `#` heading (the name), `##` section headings and `###` entries, and contains every work entry's organization, dates and summary.
- **6.2**: The DOCX output, read back with python-docx, has paragraphs in the `Title`/`Heading 1`/`Heading 2` styles for name, sections and entries, contains no tables, and its core properties carry the name as author and title.
- **6.3**: No line of the text output exceeds the configured width, except a single unbreakable token (a URL).
- **6.4**: The JSON output validates against `cv-gen schema`.
- **6.5**: With render sections `[skills, work]`, outputs contain Skills before Experience and nothing else.
- **6.6**: A model with no education produces no Education heading in any format.

### REQ-7: HTML generator

**User Story**: As a job seeker, I want a styled web page of my CV, so that I can link to it or print it.

- **7.0.1 (Ubiquitous)**: The system shall generate a single self-contained HTML file: semantic HTML5, inline CSS, print styles (`@page` size and margins), and the model embedded as schema.org `Person` JSON-LD.
- **7.0.2 (Ubiquitous)**: All source text shall be HTML-escaped; source data shall never inject markup or script.
- **7.0.3 (Ubiquitous)**: The page shall meet WCAG 2.2 AA text contrast with the default design system and use a document language attribute.
- **7.0.4 (Optional Feature)**: Where a template directory is configured, the system shall render with templates from it, falling back to the built-ins for any template it lacks.

#### Acceptance Criteria
- **7.1**: A summary containing `<script>alert(1)</script>` appears escaped in the HTML, and no `<script>` other than the JSON-LD block exists.
- **7.2**: The HTML contains a parseable `application/ld+json` block whose `name` equals `basics.name`.
- **7.3**: A template directory containing only `base.html.j2` overrides that template and the built-in partials still render.

### REQ-8: PDF generator

**User Story**: As a job seeker, I want a PDF that looks like the HTML, so that I can attach it to applications.

- **8.0.1 (Ubiquitous)**: The system shall render the HTML output to PDF through a pluggable engine.
- **8.0.2 (Ubiquitous)**: The system shall provide a `chrome` engine that drives an installed Chromium-family browser (Chrome, Edge, Chromium) headlessly, needing no extra Python packages, and optional `playwright` and `weasyprint` engines when those packages are installed.
- **8.0.3 (Event-Driven)**: When the engine is `auto`, the system shall pick the first available engine in the order playwright, chrome, weasyprint.
- **8.0.4 (Unwanted Behavior)**: If no engine is available, then the system shall say how to make one available and exit non-zero, after still writing the other requested formats.

#### Acceptance Criteria
- **8.1**: On a machine with Chrome or Edge, `--format pdf` writes a PDF whose extracted text contains the name and every work organization.
- **8.2**: With no engine available (simulated), the error names the engines and how to install one, the other formats are written, and the exit code is non-zero.

### REQ-9: Design system input

**User Story**: As a designer or user, I want to restyle the HTML and PDF with a standard tokens file, so that a new look needs no code.

- **9.0.1 (Ubiquitous)**: The system shall accept a design system as a DTCG-format tokens file (`$value`/`$type`, groups, `{alias}` references), in JSON or YAML.
- **9.0.2 (Ubiquitous)**: The system shall document a fixed set of semantic token names it consumes (colors, fonts, font sizes, spacing, page size and margins, accent and rule styles), and use built-in defaults for any token not supplied.
- **9.0.3 (Ubiquitous)**: The system shall turn tokens into CSS custom properties only after validating each value against its type, so a token value can never break out of its CSS declaration.
- **9.0.4 (Optional Feature)**: Where the design system is given as an `https` URL, the system shall fetch it, and where a `sha256` pin is given, refuse it if the content's hash differs.
- **9.0.5 (Optional Feature)**: Where the design system names a local custom CSS file, the system shall append it to the page styles; a design system loaded from a URL shall not add custom CSS.
- **9.0.6 (Ubiquitous)**: The DOCX generator shall apply the design system's body and heading font families and accent color where present.

#### Acceptance Criteria
- **9.1**: A tokens file setting `color.accent` to `#ff2bd6` produces `--cv-color-accent: #ff2bd6` in the HTML.
- **9.2**: An alias `{color.brand}` resolves to the referenced token's value; a circular alias fails naming the token.
- **9.3**: A color value of `red; } body { display:none` is rejected naming the token.
- **9.4**: A URL design system whose content does not match its `sha256` pin is refused.
- **9.5**: `cv-gen design validate tokens.json` reports the tokens it will use and any it ignores.
- **9.6**: With a design system setting `font.body`, the DOCX `Normal` style uses that font's first family.

### REQ-10: Configuration

**User Story**: As a user, I want my sources and settings in one private file with a committed example, so that my setup is repeatable and stays out of the repository.

- **10.0.1 (Ubiquitous)**: The system shall read a YAML configuration (default `cv-gen.config.yaml` in the working directory, or `--config`) describing sources, plugin paths, outputs, design system, render options and guards.
- **10.0.2 (Ubiquitous)**: Relative paths in the configuration shall resolve against the configuration file's folder.
- **10.0.3 (Ubiquitous)**: The repository shall commit `cv-gen.config.example.yaml` and ignore `cv-gen.config.yaml` and `*.local.yaml`.
- **10.0.4 (Ubiquitous)**: Command-line options shall override configuration values.
- **10.0.5 (Unwanted Behavior)**: If the configuration is missing or invalid, then the system shall name the file and the problem, and point to the example file.

#### Acceptance Criteria
- **10.1**: `git check-ignore cv-gen.config.yaml cv-gen-corey` reports both as ignored; `cv-gen.config.example.yaml` is tracked.
- **10.2**: A config in another folder with `path: ./data.yaml` reads that folder's `data.yaml` when run from elsewhere.
- **10.3**: `--format md` on the command line builds only Markdown even when the config lists every format.
- **10.4**: Running `build` with no config and no `--adapter` fails naming the missing file and the example file.

### REQ-11: Command-line interface

**User Story**: As a user, I want a small set of clear commands, so that I can build, inspect and debug each layer.

- **11.0.1 (Ubiquitous)**: The CLI shall provide `build` (extract and render), `extract` (adapter to standard JSON), `render` (standard JSON to formats), `validate`, `schema`, `adapters list|show`, `formats`, and `design validate`.
- **11.0.2 (Ubiquitous)**: Every command shall exit 0 on success and non-zero on failure, write errors to standard error without a traceback (unless `--debug`), and print the paths it wrote.
- **11.0.3 (Ubiquitous)**: Console output shall be UTF-8 safe on Windows consoles.

#### Acceptance Criteria
- **11.1**: `cv-gen --help` lists every command above.
- **11.2**: `cv-gen render resume.json --format md --format txt --out out/` writes exactly `out/<basename>.md` and `out/<basename>.txt` and prints both paths.
- **11.3**: A failing command exits non-zero and prints a one-line error; with `--debug` it prints the traceback.
- **11.4**: Output containing `–` and `●` prints on a cp1252 Windows console without an encoding error.

### REQ-12: Example adapter and documentation

**User Story**: As a developer, I want a working example and a guide, so that I can write my own adapter quickly.

- **12.0.1 (Ubiquitous)**: The repository shall include an example adapter as a standalone, installable package that registers itself through the entry-point group and reads a simple source format.
- **12.0.2 (Ubiquitous)**: The documentation shall cover the adapter contract, options models, registration (entry point, `module:Class`, plugin paths), writing a web-extraction profile and custom transforms, testing an adapter, and the model reference.
- **12.0.3 (Ubiquitous)**: The documentation shall also cover configuration, every CLI command, generators, and the design-token reference.

#### Acceptance Criteria
- **12.1**: After installing the example package, `cv-gen adapters list` shows its adapter, and `cv-gen extract --adapter <it>` on its sample file produces a valid model.
- **12.2**: The example package's own tests pass.
- **12.3**: `docs/` holds an adapter guide, a web-profile guide, a design-token reference, a configuration reference and a CLI reference, linked from the README.

### REQ-13: coreystruzan.com adapter (private)

**User Story**: As Corey, I want my About page turned into a CV with no site-specific code in the public repository, so that my CV always matches my site.

- **13.0.1 (Ubiquitous)**: The site-specific part shall be a separate package, `cv-gen-corey`, holding a web-extraction profile for coreystruzan.com/about, any custom transforms it needs, and its own tests against a saved copy of the page.
- **13.0.2 (Ubiquitous)**: `cv-gen-corey` shall be its own git repository, its local copy inside this workspace ignored by the main repository.
- **13.0.3 (Ubiquitous)**: The extraction shall take only what the public page says: identity and links, headline and summary, the Current focus, the Origin story, the Timeline as work entries (organization, periods, role where the description leads with one, summary, kind as a tag) and Tools & Skills as skill groups; the desktop wording, never both responsive variants.
- **13.0.4 (Ubiquitous)**: The private config shall run the generic `web` adapter with that profile, and may add a private overlay source, so nothing about the site is hard-coded in the engine.

#### Acceptance Criteria
- **13.1**: Against the saved page, extraction yields name "Corey Struzan", label "Senior Software Engineer", location Portland, OR, six profiles, twelve work entries in page order with Intel's two periods, and fourteen skill groups.
- **13.2**: No extracted field contains phone-only wording (for example, "Mixed reality for a global brand.").
- **13.3**: `cv-gen build` with the private config writes DOCX, Markdown, text, JSON, HTML and PDF from the live page.
- **13.4**: `git -C cv-gen-corey log` shows its own history, and the main repository's tracked files contain no coreystruzan.com selector or profile.

### REQ-14: Output guard

**User Story**: As a user with confidential history, I want the build to refuse to write forbidden words, so that a source change can never leak them into a CV.

- **14.0.1 (Optional Feature)**: Where the configuration lists forbidden terms, the system shall check every generated text output (case-insensitive, whole words) before writing it.
- **14.0.2 (Unwanted Behavior)**: If a forbidden term appears, then the system shall write no output files for that build, name the term and the format, and exit non-zero.

#### Acceptance Criteria
- **14.1**: With forbidden term `acme` and a work entry naming "Acme", the build fails naming `acme` and writes nothing.

### REQ-15: Quality and portability

**User Story**: As the maintainer, I want the tool tested and portable, so that changes are safe.

- **15.0.1 (Ubiquitous)**: The system shall run on Python 3.11 or later on Windows, macOS and Linux.
- **15.0.2 (Ubiquitous)**: The automated test suite shall run offline; tests that need a browser shall skip when none is installed.
- **15.0.3 (Ubiquitous)**: The suite shall reach at least 80% line coverage of the package.

#### Acceptance Criteria
- **15.1**: `uv run pytest` passes with no network access (network-dependent code is exercised against local fixtures or a local server).
- **15.2**: The coverage report shows at least 80% line coverage for `cv_gen`.
