# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Standard resume model: JSON Resume 1.0 plus `headline`, `periods`, `tags`, custom
  `sections` and `meta.sources`; JSON Schema export and validation.
- Adapter layer: typed options, discovery through built-ins, the `cv_gen.adapters` entry
  point group, and `module:Class` references on plugin paths.
- `file` adapter for JSON Resume and YAML/JSON in the standard model.
- `web` adapter: a generic engine that reads any page (URL or saved file) through a YAML
  profile of CSS selectors, with records, exclusions, schema.org Person JSON-LD, named
  transforms (date ranges, lead sentences, regex, mapping and more) and plugin transforms.
- Multiple sources merged in order, with replace or append list semantics.
- Generators for Markdown, plain text, Word, JSON, HTML and PDF from one shared section
  view; PDF through headless Chrome/Edge, Playwright or WeasyPrint.
- Design systems in the W3C Design Tokens format, from files or pinned HTTPS URLs, with
  validated values, aliases, custom CSS and font imports for local design systems.
- Forbidden-terms guard that writes nothing when a CV contains a listed word.
- `cv-gen` command line: `build`, `extract`, `render`, `validate`, `schema`, `formats`,
  `adapters list|show`, `design validate`.
- Example adapter package, sample resume, sample design systems, example configuration
  and documentation.
