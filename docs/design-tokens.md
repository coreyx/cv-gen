# Design systems (design tokens)

The HTML and PDF outputs, and the fonts and accent color of the Word output, are styled
by a **design system**: a file of design tokens in the W3C Design Tokens Community Group
format ([DTCG](https://www.designtokens.org/)). It is the format Figma's Tokens Studio,
Style Dictionary and other design tools exchange, so a design system made elsewhere can be
used directly.

```sh
cv-gen build --design examples/designs/serif.tokens.json
cv-gen design validate examples/designs/serif.tokens.json   # what will be used
```

or in the configuration:

```yaml
design: designs/mine.tokens.json
# or pinned, from a URL:
design:
  ref: https://example.com/designs/clean.tokens.json
  sha256: 3b1f…          # refuse it if the content ever changes
```

Any token not supplied keeps its built-in default
([`default.tokens.json`](../src/cv_gen/design/default.tokens.json)), so a design system can
be as small as one accent color.

## The format in brief

```json
{
  "color": {
    "$type": "color",
    "brand": { "$value": "#ff3ea5" },
    "accent": { "$value": "{color.brand}" },
    "text": { "$value": { "colorSpace": "srgb", "components": [0.94, 0.9, 0.96] } }
  },
  "font": {
    "body": { "$type": "fontFamily", "$value": ["Chivo", "system-ui", "sans-serif"] }
  }
}
```

- A node with `$value` is a token; other nodes are groups.
- `$type` on a group applies to every token beneath it.
- `{group.token}` as a whole value is an alias for another token, including the built-in
  defaults; aliases chain, and a cycle is an error. Overriding `color.accent` also changes
  `color.link`, which the defaults alias to it.
- YAML works as well as JSON.

## Tokens cv-gen reads

| Token | Type | Default | Used for |
|---|---|---|---|
| `color.text` | color | `#1f2328` | Body text |
| `color.muted` | color | `#57606a` | Dates, locations, contact line |
| `color.heading` | color | `#1f2328` | Name and entry titles |
| `color.accent` | color | `#0b5cad` | Label and section titles |
| `color.link` | color | `{color.accent}` | Links |
| `color.background` | color | `#ffffff` | Page |
| `color.rule` | color | `#d0d7de` | Rules under section titles |
| `font.body` | fontFamily | Calibri, Carlito, Segoe UI, Helvetica Neue, Arial, sans-serif | Body; Word's Normal style |
| `font.heading` | fontFamily | `{font.body}` | Headings; Word's heading styles |
| `font.mono` | fontFamily | Consolas, Menlo, DejaVu Sans Mono, monospace | Reserved for code |
| `font-size.base` | dimension | `10.5pt` | Body |
| `font-size.small` | dimension | `9pt` | Meta lines |
| `font-size.name` | dimension | `22pt` | Name |
| `font-size.section` | dimension | `12pt` | Section titles |
| `font-size.entry` | dimension | `10.5pt` | Entry titles |
| `font-weight.heading` | fontWeight | `700` | Headings |
| `line-height.base` | number | `1.4` | Body |
| `space.section` | dimension | `14pt` | Space above a section |
| `space.entry` | dimension | `8pt` | Space above an entry |
| `rule.width` | dimension | `1px` | Section rule |
| `page.size` | page size | `Letter` | `A3`, `A4`, `A5`, `B4`, `B5`, `Letter`, `Legal`, `Ledger`, optionally `landscape`, or two dimensions (`8.5in 11in`) |
| `page.margin` | dimension | `0.6in` | Page margin |

Tokens with other names are allowed (a design system usually has many) and are listed as
ignored by `cv-gen design validate`.

Accepted values:

- **color**: `#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa`, `rgb()`/`rgba()`, `hsl()`/`hsla()`, or
  the DTCG object form (`colorSpace: srgb`, `components` from 0 to 1, optional `alpha`, or
  `hex`). Named colors are not accepted.
- **dimension**: a number with one of `px rem em pt pc mm cm in %`, as `"12pt"` or
  `{value: 12, unit: pt}`. Word uses absolute units; `rem`, `em` and `%` fall back to its
  defaults there.
- **fontFamily**: a name, a comma-separated string, or a list. Names may contain letters,
  digits, spaces, `_`, `-` and `.`. Word uses the first name, so put the font you want in
  Word first.
- **fontWeight**: 1–1000, or a DTCG keyword (`regular`, `semi-bold`, `bold`, …).
- **number**: a plain number (line height).

## Extensions: custom CSS and web fonts

A local design system may add a stylesheet and web fonts through its root
`$extensions`:

```json
{
  "$extensions": {
    "com.cv-gen": {
      "customCss": "cv-extra.css",
      "fontImports": ["https://fonts.googleapis.com/css2?family=Chivo:wght@400;700&display=swap"]
    }
  }
}
```

`customCss` is a path relative to the tokens file, appended after cv-gen's styles; target
the `cv-*` classes in the [HTML templates](../src/cv_gen/generators/templates). Web fonts
need the network when the PDF is printed, and Word cannot use them: give `font.body` a
fallback list.

## Safety

Every token value is parsed by its type and written back out by cv-gen, so the
stylesheet only ever contains text a validator produced: a value such as
`red; } body { display: none` is rejected, naming the token. A design system loaded from a
URL may not add custom CSS or font imports (they are ignored, and reported), and must be
`https`. Pin a remote design system with `sha256` to refuse any change you haven't
reviewed.

## Templates

For changes tokens can't express, copy any of the templates in
[`src/cv_gen/generators/templates`](../src/cv_gen/generators/templates) into a folder and
set `render.templates` to it. Templates you don't copy fall back to the built-ins. Keep
autoescaping intact: print values with `{{ value }}`, never `| safe`, and links through the
`safe_url` filter.
