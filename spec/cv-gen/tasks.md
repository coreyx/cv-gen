---
status: approved
---

# Implementation Tasks: cv-gen

This document defines the implementation plan as a numbered checklist. Each task is linked to one or more acceptance criteria from [`requirements.md`](./requirements.md).

## Task List

### Milestone 1: The model, config and adapter layer work

A JSON Resume file can be loaded, validated, merged and resolved through the adapter registry.

- [x] **TASK-1: Set up the project skeleton**
  - **Associated Acceptance Criteria**: none (project setup)
  - **Concrete Steps**:
    1. Write `pyproject.toml` (hatchling, `requires-python >=3.11`, dependencies from tech.md, `playwright`/`weasyprint` extras, `cv-gen` script, dev group with pytest, pytest-cov, pypdf, ruff).
    2. Create `src/cv_gen/` with `__init__.py` (version) and `__main__.py`, and `tests/`.
    3. Write `.gitignore` (venv, caches, `out/`, `cv-gen.config.yaml`, `*.local.yaml`, `cv-gen-corey/`), `.gitattributes`, ruff and pytest settings, and an MIT `LICENSE`.
    4. `uv sync` and confirm `uv run pytest` runs.

- [x] **TASK-2: Implement the standard resume model and error formatting**
  - **Associated Acceptance Criteria**: `1.1`, `1.3`, `1.4`
  - **Concrete Steps**:
    1. Write `model.py`: every JSON Resume section, the extensions, `PartialDate`, `extra="allow"`, `Resume.load()`/`dump()` helpers.
    2. Write `errors.py`: `CvGenError(message, hint)` and the Pydantic error formatter (`work[0].startDate: …`).
    3. Add a JSON Resume sample fixture and tests for loading, round-tripping extensions and date validation.

- [x] **TASK-3: Implement configuration and source merging**
  - **Associated Acceptance Criteria**: `5.1`, `5.2`, `10.2`
  - **Concrete Steps**:
    1. Write `merge.py` (`deep_merge` with `replace`/`append`, `None` never erases).
    2. Write `config.py`: config models, `source`/`sources` sugar, `load_config()` with base-dir resolution and the missing-file hint.
    3. Test merge rules and relative-path resolution from another working directory.

- [x] **TASK-4: Implement the adapter contract, registry and file adapter**
  - **Associated Acceptance Criteria**: `2.1`, `2.3`, `2.4`, `2.5`, `3.1`
  - **Concrete Steps**:
    1. Write `adapters/base.py` (`Adapter`, `AdapterOptions` with `extra="forbid"`, `AdapterContext`).
    2. Write `adapters/registry.py` (built-ins, `cv_gen.adapters` entry points, `module:Class`, plugin paths, the unknown-name error).
    3. Write `adapters/file.py` (JSON and YAML).
    4. Write `pipeline.extract()` (resolve, validate options, run, merge, validate the result, record `meta.sources`).
    5. Test each discovery route, option validation and the file adapter.

### Milestone 2: The generic web-extraction engine works

Any page can be turned into the model with a YAML profile.

- [x] **TASK-5: Implement transforms and date-range parsing**
  - **Associated Acceptance Criteria**: `4.2`, `4.5`
  - **Concrete Steps**:
    1. Write `adapters/web/dates.py` (periods, open ranges, dash variants, `present`).
    2. Write `adapters/web/transforms.py`: the `@transform` registry, `register_module()`, and the built-ins (`normalize`, `regex`, `split`, `strip_prefix`, `strip_suffix`, `date_range`, `lead_sentence`, `as_list`, `absolute_url`, `lower`, `upper`, `replace`, `join`, `map`).
    3. Test every built-in and a module-registered transform.

- [x] **TASK-6: Implement fetching, JSON-LD, the profile engine and the web adapter**
  - **Associated Acceptance Criteria**: `4.1`, `4.3`, `4.4`, `4.6`
  - **Concrete Steps**:
    1. Write `fetch.py` (http/https/local file, timeout, size cap, User-Agent, errors naming the URL).
    2. Write `jsonld.py` (Person → basics).
    3. Write `profile.py` (field-spec models) and `engine.py` (exclude, scopes, `each`, `all`, `drop`, `"."` merge, required/optional, transform application, empty-value pruning).
    4. Write `adapter.py` (`WebAdapter`, options `url`/`path`/`profile`/`timeout`/`user_agent`).
    5. Add a generic fictional fixture page and profile under `tests/fixtures/web/` and `examples/profiles/`; test extraction, exclusion, JSON-LD baseline, a missing required selector, and a fetch through a local HTTP server and to an unreachable host.

### Milestone 3: Every output format renders

The model renders to Markdown, text, JSON, DOCX, HTML and PDF, styled by design tokens.

- [x] **TASK-7: Implement the section view and the Markdown, text and JSON generators**
  - **Associated Acceptance Criteria**: `6.1`, `6.3`, `6.4`, `6.5`, `6.6`
  - **Concrete Steps**:
    1. Write `generators/base.py` (registry, `RenderRequest`, `RenderOptions`) and `view.py` (default order, titles, omission, date display).
    2. Write `markdown.py`, `text.py` (wrapping, underlines) and `jsonout.py`.
    3. Test structure, wrapping, schema validity, section selection and empty-section omission.

- [x] **TASK-8: Implement design-token loading and the theme**
  - **Associated Acceptance Criteria**: `9.1`, `9.2`, `9.3`, `9.4`
  - **Concrete Steps**:
    1. Write `design/tokens.py` (DTCG JSON/YAML, groups, `$type` inheritance, aliases with cycle detection, URL fetch with sha256 pin).
    2. Write `design/theme.py` (semantic token table, typed validators, CSS custom properties, `customCss`/`fontImports` for local files only, ignored-token report) and `default.tokens.json`.
    3. Test values, aliases, injection rejection, hash pinning and the URL/local distinction.

- [x] **TASK-9: Implement the DOCX generator**
  - **Associated Acceptance Criteria**: `6.2`, `9.6`
  - **Concrete Steps**:
    1. Write `generators/docx.py`: Title/Heading styles, entries, bullets, links as text, core properties, theme fonts and accent color.
    2. Test by reading the document back with python-docx.

- [x] **TASK-10: Implement the HTML generator**
  - **Associated Acceptance Criteria**: `7.1`, `7.2`, `7.3`
  - **Concrete Steps**:
    1. Write the Jinja2 templates (`base.html.j2` and section partials) with autoescape, print CSS and the theme's variables.
    2. Write `generators/html.py` (template-directory override with fallback, JSON-LD Person builder).
    3. Test escaping, JSON-LD and template override.

- [x] **TASK-11: Implement the PDF engines and generator**
  - **Associated Acceptance Criteria**: `8.1`, `8.2`
  - **Concrete Steps**:
    1. Write `pdf/engines.py` (`chrome` executable discovery and invocation, `playwright`, `weasyprint`, `auto` order, install hints).
    2. Write `generators/pdf.py` (HTML from the HTML generator, rendered in a temporary folder).
    3. Test a real render with pypdf text extraction (skipped without a browser) and the no-engine path.

- [ ] **TASK-12: Implement the render pipeline and the output guard**
  - **Associated Acceptance Criteria**: `14.1`
  - **Concrete Steps**:
    1. Write `guard.py` and `pipeline.render()`/`write()` (render all in memory, guard, write, per-format errors).
    2. Test that a forbidden term writes nothing and that a PDF failure still writes the other formats.

### Milestone 4: The CLI, example adapter and documentation are usable

Someone new can install the tool, run the example and write an adapter from the docs.

- [ ] **TASK-13: Implement the CLI**
  - **Associated Acceptance Criteria**: `1.2`, `2.2`, `9.5`, `10.3`, `10.4`, `11.1`, `11.2`, `11.3`, `11.4`
  - **Concrete Steps**:
    1. Write `console.py` (UTF-8 setup) and `cli.py` (every command, shared options, `--debug`, error printing).
    2. Test every command with Typer's `CliRunner`, the cp1252 console case and exit codes.

- [ ] **TASK-14: Build the example adapter package**
  - **Associated Acceptance Criteria**: `12.1`, `12.2`
  - **Concrete Steps**:
    1. Create `examples/adapter-example/` (`pyproject.toml` with the entry point, `src/cv_gen_example_adapter/`, a sample TOML source, tests, README).
    2. Add it to the dev dependency group as a uv path source; confirm `cv-gen adapters list` shows it and its tests pass.

- [ ] **TASK-15: Write the documentation and the example config**
  - **Associated Acceptance Criteria**: `12.3`, `10.1`
  - **Concrete Steps**:
    1. Write `README.md`, `docs/adapters.md`, `docs/web-profiles.md`, `docs/design-tokens.md`, `docs/configuration.md`, `docs/cli.md`, `docs/model.md`, and `CHANGELOG.md`.
    2. Write `examples/sample-resume.yaml`, `examples/designs/` sample tokens, and `cv-gen.config.example.yaml` that builds the sample out of the box.

- [ ] **TASK-16: Reach the coverage target and verify offline**
  - **Associated Acceptance Criteria**: `15.1`, `15.2`
  - **Concrete Steps**:
    1. Run the suite with coverage, add tests for uncovered branches until line coverage is at least 80%.
    2. Set `--cov-fail-under=80` in the pytest configuration.

### Milestone 5: Corey's CV builds from coreystruzan.com

The private adapter turns the live About page into every format.

- [ ] **TASK-17: Create the private cv-gen-corey package**
  - **Associated Acceptance Criteria**: `13.1`, `13.2`, `13.4`
  - **Concrete Steps**:
    1. Create `cv-gen-corey/` as its own git repository: `pyproject.toml`, `src/cv_gen_corey/` with the About profile, transforms and the Neon Underground tokens, a saved copy of the page, tests and README.
    2. Run its tests from the main environment; confirm the main repository ignores it and tracks no site-specific selector.

- [ ] **TASK-18: Wire the private config and build Corey's CV from the live page**
  - **Associated Acceptance Criteria**: `13.3`, `10.1`
  - **Concrete Steps**:
    1. Write the git-ignored `cv-gen.config.yaml` (web adapter, the private profile, plugin path, design, render sections), and keep a copy in `cv-gen-corey/`.
    2. Run `cv-gen build` against the live page; check every format by reading it back, and look at the PDF.
