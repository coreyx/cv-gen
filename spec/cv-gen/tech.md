---
status: approved
---

# cv-gen Tech Stack

## Summary

Python 3.11+ package managed with uv and built with hatchling; Typer CLI; Pydantic 2 for the model, options and config; BeautifulSoup 4 (stdlib `html.parser`) for extraction; the standard library's `urllib` for fetching; Jinja2 for Markdown/HTML templates; python-docx for Word; PDF through a pluggable engine (system Chrome/Edge by default, Playwright or WeasyPrint optional); pytest + pytest-cov; ruff.

## Decisions

### Language and packaging
**Choice:** Python ≥ 3.11 (developed on 3.14.7), `src/` layout, hatchling build backend, uv for environments and the lock file.
**Why:** cv-gen is specified as a Python CLI. 3.11 is the oldest version still receiving security fixes and gives `tomllib` and modern typing (REQ-15). uv is installed (0.12.15) and makes `uv run` reproducible from `uv.lock`. Hatchling is the uv default and needs no config for entry points (REQ-2, REQ-12).
**Alternatives considered:** Poetry (slower, own lock format, nothing gained); setuptools (more boilerplate).

### CLI
**Choice:** Typer 0.27 (on Click 8.5), MIT.
**Why:** Typed command signatures, sub-command groups (`adapters list|show`, `design validate`) and help text for free (REQ-11). Testable through its `CliRunner`.
**Alternatives considered:** Click directly (more decorators, same engine); argparse (no sub-app ergonomics, more code).

### Data model, options and configuration
**Choice:** Pydantic 2.14, MIT.
**Why:** One library validates the resume model, every adapter's options and the config file, reports errors by field path (1.0.5, 2.0.4, 10.0.5), and exports JSON Schema (1.0.4, 2.2). Partial ISO dates are a constrained string type.
**Alternatives considered:** dataclasses + jsonschema (two sources of truth); attrs/cattrs (no schema export).

### HTML extraction
**Choice:** BeautifulSoup 4.15 with the stdlib `html.parser` backend; CSS selectors via soupsieve (bs4's dependency), MIT.
**Why:** Declarative CSS selectors are what a site profile is written in (REQ-4); `html.parser` needs no compiled extension, so it installs everywhere, Python 3.14 on Windows included.
**Alternatives considered:** lxml backend (faster, compiled; not needed for one page); selectolax (fast, smaller selector support, less known); parsel/XPath (less readable for profile authors).

### HTTP fetching
**Choice:** `urllib.request` from the standard library, with an explicit timeout and User-Agent.
**Why:** The engine fetches one page at a time (4.0.1, 4.0.7); a dependency adds nothing. httpx's last release was 2024-12, a further reason not to take it on for this.
**Alternatives considered:** httpx, requests.

### YAML
**Choice:** PyYAML 6.0 (`safe_load` only), MIT.
**Why:** Config, profiles, overlays and YAML tokens files (REQ-3, REQ-9, REQ-10). Safe loading means a YAML file cannot construct Python objects.
**Alternatives considered:** ruamel.yaml (round-trip editing not needed).

### Templates (Markdown, HTML)
**Choice:** Jinja2 3.1, BSD-3-Clause, with autoescape on for HTML and off for Markdown/text.
**Why:** Templates are overridable by directory (7.0.4) and autoescape is the escaping guarantee (7.0.2). Markdown and text are produced by Python code that escapes Markdown-significant characters, because their layout rules (wrapping, underlines) are easier to test in code.
**Alternatives considered:** string building for HTML (no override story); Mako (less familiar).

### Word
**Choice:** python-docx 1.2, MIT.
**Why:** Writes real `Title`/`Heading` styles and core properties (6.0.2) and reads documents back for tests (6.2). Maintained; no Office install needed.
**Alternatives considered:** docxtpl (template-first, harder to keep ATS-clean); pandoc (external binary, not installed).

### PDF
**Choice:** An engine interface with three engines: `chrome` (default fallback; runs the installed Chrome/Edge/Chromium with `--headless --print-to-pdf`, no Python dependency), `playwright` (optional extra, Apache-2.0) and `weasyprint` (optional extra, BSD-3-Clause).
**Why:** Chromium renders the same HTML/CSS the browser shows, so PDF matches HTML (REQ-8). Chrome and Edge are both present on this machine, and Edge ships with Windows, so the zero-install path works for most users. WeasyPrint needs GTK/Pango on Windows and Playwright downloads ~150 MB of browser, so both are opt-in.
**Alternatives considered:** xhtml2pdf (weak CSS, would make the design system a lie); ReportLab (a second layout implementation).

### Testing and quality
**Choice:** pytest 9, pytest-cov 7, pypdf 6 (reading generated PDFs in tests), ruff for lint and format.
**Why:** Full-tier testing standard: real framework and measured coverage (REQ-15). pypdf extracts PDF text for 8.1. Network tests use a local `http.server` thread, so the suite runs offline (15.1).
**Alternatives considered:** unittest (more boilerplate); coverage.py directly (pytest-cov is the thin wrapper).

### Standards adopted
**Choice:** JSON Resume 1.0 schema as the model's base; W3C Design Tokens Community Group format (DTCG, 2025.10 stable) for the design system; schema.org `Person` JSON-LD for machine-readable HTML.
**Why:** Interoperability: JSON Resume themes and tools read the JSON output (1.0.1); DTCG is the cross-tool token format exported by Figma Tokens Studio, Style Dictionary and others (9.0.1); schema.org is read by search engines and parsers (7.0.1, 4.0.5).
**Alternatives considered:** a bespoke model and theme format (no ecosystem).

## Constraints & risks

- **soupsieve 3.0.4 was released on 2026-10-22** (today) and requires Python ≥ 3.11.5. The lock file pins what was tested; review the lock on upgrade.
- **The `chrome` engine depends on browser command-line flags** (`--headless`, `--print-to-pdf`, `--no-pdf-header-footer`), which Chromium has changed before. It is isolated behind the engine interface and covered by a test that skips without a browser.
- **WeasyPrint on Windows** needs a GTK runtime; the engine reports that clearly rather than failing at import.
- **Web extraction is brittle by nature.** A site redesign breaks its profile. Required selectors fail loudly (4.0.8), and the private package keeps a saved page so a broken profile is caught by its tests, not by a bad CV.
- All dependencies are MIT, BSD or Apache-2.0: compatible with any license the project picks. The project itself is licensed MIT (assumed; see the walkthrough).
