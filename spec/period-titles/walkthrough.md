# Walkthrough: Job titles per period

A job held in separate stints can now name the title held in each one. Every format shows
each title beside its own dates, as in **QA** · 2006 – 2007, **Software Engineer** · 2010 –
2013, while the entry keeps one overall `position` for JSON Resume tools and
applicant-tracking systems. The web engine can read the titles from per-period markup.

**Related documents**
- [Implementation plan](implementation_plan.md)
- [Product](../cv-gen/product.md)

## What Was Implemented

### 1. Model
- **`src/cv_gen/model.py`**: `Period` gains an optional `position`. The JSON Schema exposes
  it, and documents using it round-trip through `Resume.from_data` / `to_data`.

### 2. Shared section view
- **`src/cv_gen/generators/view.py`**: a `Stint` (position, dates) and `Entry.stints`.
  `stints(periods)` returns stints only when an entry has two or more periods and at least
  one names a title. In that case the entry's single subtitle and date range are left
  empty, because the stints replace them. Work and projects both use it.

### 3. Generators
- **`markdown.py`**: `**QA** · 2006 – 2007, **Software Engineer** · 2010 – 2013 · location`,
  with positions escaped.
- **`text.py`**: `QA | 2006 – 2007, Software Engineer | 2010 – 2013 | location`, wrapped
  like every other meta line.
- **`docx.py`**: one meta paragraph with a bold run per title and muted runs for dates,
  still kept with the next paragraph.
- **`entry.html.j2` and `styles.css.j2`**: one `cv-stint` span per stint, holding
  `cv-subtitle` and `cv-dates`. CSS puts ` · ` between a title and its dates and `, `
  between stints. The PDF follows from the HTML.

### 4. Web engine
- **`src/cv_gen/adapters/web/engine.py`**: an `each` that matches nothing now gives the
  field's `default` (nothing), like a missing selector, instead of an empty list. The
  plan said no engine change was needed. In practice, listing `periods` after `"."` made
  an entry with no titled periods lose the periods `date_range` had already found.
  Covered by `test_each_without_matches_keeps_earlier_value`.

### 5. Documentation
- **`docs/model.md`**: a "Titles per period" section, and the extensions table updated.
- **`docs/web-profiles.md`**: "A title for each period", an example profile that reads
  one record per period element, with dates from `date_range` and the title from an
  attribute.
- **`CHANGELOG.md`**: an `Added` entry.

### 6. Private profile (separate, git-ignored package)
- The private profile now reads titled periods. It also follows the site's new markup,
  which marks each entry's title in its own element: the title becomes the `position` and
  the rest of the description becomes the summary. The saved page and the tests were
  refreshed to match.

## Verification & Test Results

### Automated Tests
The plan uses the existing pytest suite rather than a scratch script:
- `uv run pytest`: **Passed**, 208 tests. Coverage 97.4%, above the 80% gate.
- `uv run ruff check` and `ruff format --check` on `src tests examples`: **Passed**.
- New tests use a fictional CV (`tests/fixtures/two-stints.yaml`): a job with two titled
  stints, a job with one titled and one untitled stint, a job with two untitled stints,
  and a single-period job. Model round-trip, Markdown, text, Word and HTML: **Passed**.
- Private package tests against the re-saved page: **Passed**, 8 tests. They check the
  multi-period entry's two titles and dates, its overall position, that no other entry
  lists periods, and that no phone-only wording leaks in. Ruff reports an import-order
  difference in the private test file that predates this change. The main and private
  configurations sort that import differently, so it was left as is.

### Regression Testing
- Before the site change, a rebuild of the real CV gave Markdown and JSON byte-identical
  to the previous build, so entries without titled periods render as before.
- After the site change, `cv-gen build` wrote all six formats. The multi-period entry reads
  as above in Markdown, text, Word (titles bold), HTML, PDF, and JSON, where both
  `periods[].position` values are present.

## Manual Verification
1. Run `uv run cv-gen build`.
2. Open the PDF in `out/` and find the last Experience entry. The line under the employer
   reads **QA** · 2006 – 2007, **Software Engineer** · 2010 – 2013, with each title in the
   same weight as other entries' titles.
3. Open the `.docx` in Word and confirm the same line, with the titles bold.

## Follow-ups
- None outstanding for this spec. Projects support stints through the shared view, but no
  source uses them yet.
