---
name: html-slides
description: >
  Build standalone, shareable HTML slide presentations with a confirmed design system
  (Soft Contemporary aesthetic, Cabinet Grotesk font, Indigo accent palette). Use when
  the user asks to create a presentation, slide deck, slide pack, or report as HTML.
  Triggers on: "create a presentation", "build slides", "make a deck", "HTML slides",
  "presentation about X", "slide pack for Y". Do NOT use for .pptx — only for HTML output.
---

# HTML Slide Presentations

Build HTML presentations using the confirmed design system. Output is an `.html` file with light/dark mode, keyboard navigation, and print-to-PDF support.

## Architecture

```
calculate.py  (optional — only when source data needs processing)
     |
     v
slides.json   (structured content — the primary output)
     |
     v
presentation.html  (built from template + JSON, validated with Playwright)
     |
     v
build.py      (optional — creates a static standalone HTML for sharing)
```

## Workflow

### 1. Analyse Content

Determine what slides are needed. Read [references/design-system.md](references/design-system.md) for the colour palette, typography scale, and layout rules that must be followed.

### 2. Write calculate.py (if needed)

If the presentation requires complex data processing from source files (CSV, spreadsheets, databases, APIs), write a `calculate.py` that:
- Reads and processes the source data
- Performs calculations, aggregations, or transformations
- Outputs processed results that feed into slides.json

Skip this step if content is purely narrative or data is already prepared.

### 3. Generate slides.json

Write a JSON file:

```json
{
  "title": "Presentation Title",
  "slides_html": "...",
  "custom_css": ""
}
```

- `title`: the `<title>` tag value
- `slides_html`: all `<div class="slide ...">` elements as a single HTML string. First slide must include the `active` class. Every slide div needs class `slide` plus a layout class, and `data-title="Slide Name"`.
- `custom_css`: any additional CSS for custom slide layouts (inserted after base styles in the template)

### 4. Build and Validate

Build the presentation HTML from the template and JSON, then **always use the `/playwright-cli` skill to visually verify output.** Start a local server and screenshot key slides:

```bash
python {skill_path}/scripts/build.py slides.json -o presentation.html
python3 -m http.server 8787 &
playwright-cli open http://localhost:8787/presentation.html
playwright-cli screenshot
playwright-cli press ArrowRight
playwright-cli screenshot
```

The template at [assets/template.html](assets/template.html) contains the full design system CSS, floating nav dock (centred, with prev/next arrows, slide title, page count, pips, light/dark toggle), progress bar, keyboard/click navigation, and print styles.

Check: font sizes fill the screen, content is well-positioned, colours match the design system, cards fit their content without unnecessary stretching. Iterate on slides.json and rebuild until the presentation is confirmed.

### 5. Package for Sharing (optional)

Once the presentation is confirmed, the user can optionally create a static standalone HTML for easy sharing:

```bash
python {skill_path}/scripts/build.py slides.json -o presentation.html
```

The output is a single self-contained `.html` file that works in any browser with no dependencies (except Google Fonts).

### 6. Export to PDF (if requested)

The template has built-in `@media print` styles that ensure the PDF output:
- Renders **one slide per page** (each slide gets a page break)
- **Hides the navigation dock and progress bar** — only slide content is printed
- **Defaults to light mode** — all colour tokens are overridden to the light palette regardless of the current theme

To generate a PDF:

```bash
playwright-cli pdf
```

Or the user can open the HTML in a browser and use `Cmd+P` / `Ctrl+P` to print to PDF.

## Design Rules (mandatory)

### Colour Palette

Use ONLY the CSS custom property tokens defined in the template. See [references/design-system.md](references/design-system.md) for full values.

- Primary accent: `var(--accent)` (indigo)
- Semantic: `var(--green)`, `var(--amber)`, `var(--rose)` — each with `-tint` and `-border` variants
- Text: `var(--heading)` > `var(--subheading)` > `var(--body)` > `var(--muted)`
- Surfaces: `var(--bg)` > `var(--surface)` > `var(--elevated)`

### Typography

- Font: Cabinet Grotesk (loaded from Google Fonts in the template)
- All sizes in `vw` units — see [references/design-system.md](references/design-system.md) for the full scale
- Maximise font sizes to use screen real estate effectively

### Navigation Panel

Built into the template — do not modify its structure.

### Layout

- Cards/surfaces fit their content — never use `flex: 1` to stretch cards
- Never set `position: relative` on slide-type classes (breaks base `position: absolute` sizing)
- `justify-content: center` for vertically centred content
- `justify-content: flex-end` for bottom-aligned content (section dividers)
- Padding: `4–6vh` vertical, `4–6vw` horizontal

## Slide Patterns

The template CSS includes these base types. Use as starting points — adapt freely:

- `slide-title` — centred title with inner frame and accent dot
- `slide-section` — section divider with large background number, bottom-aligned
- `slide-stat` — hero stat number (18vw)
- `slide-text-image` — two-column: text left, image/visual right
- `slide-bullets` — heading + bullet list
- `slide-quote` — blockquote with attribution
- `slide-compare` — two-column comparison cards
- `slide-cards` — grid of summary cards
- `slide-dashboard` — KPI row + detail cards
- `slide-mixed` — stats grid + narrative panel
- `slide-table` — styled data table
- `slide-multi` — multi-column breakdown with header stats

For custom layouts, define new CSS classes via `custom_css` in slides.json. These are examples — create whatever layout best serves the content.
