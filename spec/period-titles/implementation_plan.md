---
status: approved
---

# Job titles per period

A job held in separate stretches at one employer can have a different title in each, for example "QA" for 2006–2007 and "Software Engineer" for 2010–2013. Today the model records the periods but only one position for the whole entry. This change lets each period carry its own title. Every output then shows each title beside its own dates, as in **QA** · 2006 – 2007, **Software Engineer** · 2010 – 2013. The entry keeps its overall `position` (for example "QA, then Software Engineer") for JSON Resume tools and applicant-tracking systems.

**Related documents**
- [Product](../cv-gen/product.md)

## User Review Required

> [!IMPORTANT]
> The standard model gains an optional `position` on each period (`work[].periods[].position`, `projects[].periods[].position`). The change is additive: existing files stay valid, and `cv-gen schema` gains one optional field. Model files written with it are still valid JSON Resume, because `periods` is already a cv-gen extension that JSON Resume tools ignore.

> [!NOTE]
> - **Which title shows:** when an entry has two or more periods and at least one of them has a title, the meta line shows the periods with their titles instead of the entry-level position. The entry-level position stays in the JSON output but is not shown in the rendered formats, so the titles don't appear twice.
> - **A period without a title** shows its dates alone.
> - **One period or no period titles:** entries render exactly as they do now.
> - **No engine change.** The web engine can already read the titles: a `periods` field with `each` builds one record per period element, and a field listed after `"."` replaces the periods that `date_range` produced.

## Open Questions

- **Site markup is not live yet.** The private profile change depends on the site change being deployed: one title attribute on each period element of a multi-period entry. That work is in progress in the site repository. If the attribute or element names differ from what is planned, only the private profile changes, not cv-gen.

## Proposed Changes

### Model

#### [MODIFY] `src/cv_gen/model.py`
- [x] **TASK-1:** Add `position: str | None = None` to `Period`, with its docstring updated to say a period may name the title held during it. Confirm `json_schema()` exposes the field and that a document using it round-trips through `Resume.from_data` / `to_data`.

### Shared view

#### [MODIFY] `src/cv_gen/generators/view.py`
- [x] **TASK-2:** Add a `Stint` dataclass (`position: str | None`, `dates: str | None`) and an `Entry.stints: list[Stint]` field. Add `stints(periods) -> list[Stint]`. It returns stints only when there are two or more periods and at least one has a `position`, and an empty list otherwise.
  - In `_builtin`, `work` and `projects` fill `stints` from their periods.
  - When `stints` is non-empty, the entry's `subtitle` and `dates` are left empty, so the existing `Entry.meta` (used by Markdown and text) carries only the location. Each renderer writes the stints itself, before that.

### Renderers

#### [MODIFY] `src/cv_gen/generators/markdown.py`
- [ ] **TASK-3:** In `_entry`, when `entry.stints` is set, write the meta line as `**QA** · 2006 – 2007, **Software Engineer** · 2010 – 2013`, followed by ` · <location>` when present. Positions are escaped and bold, dates escaped; an untitled stint writes its dates only.

#### [MODIFY] `src/cv_gen/generators/text.py`
- [ ] **TASK-4:** In `_entry`, when `entry.stints` is set, write `QA | 2006 – 2007, Software Engineer | 2010 – 2013`, plus ` | <location>`, wrapped at the configured width like every other meta line.

#### [MODIFY] `src/cv_gen/generators/docx.py`
- [ ] **TASK-5:** In `_Builder.entry`, when `entry.stints` is set, write one meta paragraph with a bold run for each position and a muted run for each period's dates, separated by `, `, then ` · <location>` muted. Keep `keep_with_next`. The read-back text used by the guard (`docx_text`) must contain every position and date.

#### [MODIFY] `src/cv_gen/generators/templates/entry.html.j2` and `styles.css.j2`
- [ ] **TASK-6:** When `entry.stints` is set, the `cv-meta` paragraph holds one `<span class="cv-stint">` per stint, containing `<span class="cv-subtitle">` and `<span class="cv-dates">`, then the location span. In `styles.css.j2`, the `·` separator applies between a stint's title and dates and before the location, and `, ` goes between stints. The PDF follows from the HTML.

### Tests and documentation

#### [MODIFY] `tests/test_model.py`, `tests/test_generators_text.py`, `tests/test_docx.py`, `tests/test_html.py`
- [ ] **TASK-7:** Add tests with a fictional two-period job. Cover:
  - Each format shows each title beside its own dates, and the entry-level position doesn't appear on the meta line.
  - A period without a title shows its dates alone.
  - A one-period entry, or periods with no titles, render exactly as before.
  - The JSON output validates against `cv-gen schema` and keeps both the entry-level and period positions.

#### [MODIFY] `docs/model.md`, `docs/web-profiles.md`, `CHANGELOG.md`
- [ ] **TASK-8:** Document `periods[].position` in the model guide and how it renders. Add a web-profile example that reads one record per period element, with dates from `date_range` and the title from an attribute, listed after `"."`. Add an `Added` entry under `[Unreleased]`.

### Private adapter (cv-gen-corey, its own repository)

#### [MODIFY] `cv-gen-corey/src/cv_gen_corey/profiles/about.yaml`, `cv-gen-corey/tests/fixtures/about.html`, `cv-gen-corey/tests/test_about.py`
- [ ] **TASK-9:** Once the site change is live, update the profile and tests:
  - Add a `periods` field after `"."` in `work` that reads only the period elements carrying a title attribute: dates through `date_range`, title from the attribute.
  - Re-save the page fixture.
  - Assert the multi-period entry has the period titles QA and Software Engineer, the entry-level position "QA, then Software Engineer", and unchanged overall dates; single-period entries gain no `periods`.
  - Rebuild the CV and check all six formats.

## Verification Plan

### Automated Tests
This repository already uses pytest with an 80% coverage gate, so the checks go into the existing suite (TASK-7, TASK-9) rather than a separate scratch script:
1. `uv run pytest`: the new period-title tests pass, every existing test still passes, and coverage stays at or above 80%.
2. `uv run ruff check src tests examples` and `uv run ruff format --check src tests examples` are clean.
3. `uv run pytest cv-gen-corey/tests`: the private tests pass against the re-saved page.

### Manual Verification
1. After the site change is deployed, run `uv run cv-gen build`.
2. Open `out/corey/corey-struzan-cv.pdf` and find the last Experience entry. Under the employer, the line reads **QA** · 2006 – 2007, **Software Engineer** · 2010 – 2013, with each title in the same weight as other entries' titles.
3. Open the `.docx` in Word and confirm the same line, with the titles bold.
4. Open the `.md` and `.txt` and confirm the same content in their own formats.
5. Check that every other entry looks as it did in the previous build.
