# Product: cv-gen

## Problem and motivation

A person's professional story usually already lives somewhere structured: a personal website, a LinkedIn profile, a JSON Resume file, a spreadsheet. Turning that into a CV means retyping it into Word, then retyping it again when the source changes, and again for every format a recruiter, an applicant-tracking system (ATS) or a portfolio needs. The copies drift apart from the source and from each other.

cv-gen makes the source the single place to edit. It reads a source through a pluggable adapter, normalizes it into one standard data model, and generates every output format from that model.

## Target users

- **Corey first**: a senior engineer whose canonical story lives on coreystruzan.com/about, who wants a CV that always matches the site.
- **Developers with their own sources**: people comfortable writing a small adapter (or a declarative extraction profile) for their own site or export format.
- **Later, less technical users** pointing the tool at a LinkedIn export and a published design system (see "Open questions").

## Value proposition

- **One source of truth.** Edit the website; rebuild the CV.
- **Any source.** The adapter layer is the only source-specific code, and a declarative web-extraction engine means many sites need only a YAML profile, not code.
- **Every format from one model.** Word, Markdown, plain text and JSON for people and machines (ATS parsers, LLMs, scripts); HTML and PDF styled by a design system in a standard token format.
- **Private stays private.** Personal adapters, profiles and configs live outside the public repository.

## Goals and success criteria

- `cv-gen build` turns Corey's live About page into DOCX, Markdown, text, JSON, HTML and PDF in one command, with no hand edits.
- A new adapter can be written from the documentation and the example alone, without reading the engine's source.
- A different visual design is a different tokens file, not a code change.
- Outputs are ATS-friendly: real headings, no layout tables, selectable text, consistent section names.

## Non-goals

- Not a resume *writer*: it does not invent, rewrite or embellish content (no LLM rewriting in this version).
- Not a WYSIWYG editor or a hosted service.
- Not a scraper of sites that forbid it: LinkedIn will be supported through its official data export, not by scraping.
- Not a design tool: it consumes design tokens; it does not author them.

## Core user journeys

1. **Build from config**: copy `cv-gen.config.example.yaml` to `cv-gen.config.yaml`, point it at a source and a design, run `cv-gen build`, open `out/`.
2. **Extract, inspect, render**: `cv-gen extract` to the standard JSON, inspect or hand-overlay it, `cv-gen render` to any format.
3. **Write an adapter**: copy the example adapter package, implement one method, register an entry point, `cv-gen adapters list` shows it.
4. **Restyle**: point `--design` at another DTCG tokens file (local or URL) and rebuild the HTML/PDF.

## Market and competitive context

JSON Resume (jsonresume.org) is the de facto open schema with a theme ecosystem, and cv-gen's model is a compatible superset of it, so its outputs work with those tools. RenderCV and resume-builder tools render from a hand-written YAML/JSON file; cv-gen's difference is the *source adapter* step (extracting from where the data already lives) plus standard design tokens for styling.

## Constraints and context

- Solo developer project, Windows-first (Corey's machine) but cross-platform.
- The coreystruzan.com content rules (NDA, anonymous work, never-named products) apply to anything derived from the site. Extracting only what the public page already says keeps the CV inside them.

## Open questions for later

- LinkedIn adapter: official "Download your data" export (CSV) is the recommended route; confirm before building.
- "Design systems from a public online repository": a registry of DTCG token files (e.g. a GitHub repo addressed by URL with a pinned hash) is the assumed shape.
- Whether tailored variants (a short CV, a games-focused CV) are wanted beyond section selection.
