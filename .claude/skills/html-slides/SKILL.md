---
name: html-slides
description: Build standalone, shareable HTML slide presentations with a confirmed design system (Soft Contemporary aesthetic, Outfit font, Indigo accent palette). Use when the user asks to create a presentation, slide deck, slide pack, or report as HTML. Triggers on: "create a presentation", "build slides", "make a deck", "HTML slides", "presentation about X", "slide pack for Y". Do NOT use for .pptx — only for HTML output.
---

# HTML Slide Presentations

Build standalone HTML presentations using the confirmed design system. Output is a single shareable `.html` file with light/dark mode, keyboard navigation, and print-to-PDF support.

## Workflow

### 1. Analyse Content

Determine what slides are needed. Read [assets/template.html](assets/template.html) for all built-in CSS patterns, [../../shared/design-system.md](../../shared/design-system.md) for the colour palette, icons, and semantic rules, and [references/design-system.md](references/design-system.md) for slide-specific typography scale and layout rules.

### 2. Write calculate.py (if needed)

If the presentation requires data processing from source files (CSV, spreadsheets, etc.), write a `calculate.py` that reads, processes, and outputs results to feed into the presentation. Skip if content is purely narrative or data is already prepared.

### 3. Build the presentation HTML

Write the presentation as a complete HTML file, using [assets/template.html](assets/template.html) as the base. Copy the template and replace the `{{TITLE}}`, `{{SLIDES_HTML}}`, and `{{CUSTOM_CSS}}` placeholders:

- `{{TITLE}}`: the `<title>` tag value
- `{{SLIDES_HTML}}`: all `<div class="slide ...">` elements. First slide must include the `active` class. Every slide div needs class `slide` plus a layout class, and `data-title="Slide Name"`.
- `{{CUSTOM_CSS}}`: any additional CSS for custom slide layouts

The template includes the full design system CSS, floating nav dock (prev/next arrows, slide title, page count, pips, light/dark toggle), progress bar, keyboard/click navigation, and print styles.

### 4. Validate with Playwright

**Always use the `/playwright-cli` skill to visually verify output.** Start a local server and screenshot key slides:

```bash
python3 -m http.server 8787 &
playwright-cli open http://localhost:8787/presentation.html
playwright-cli screenshot
playwright-cli press ArrowRight
playwright-cli screenshot
```

Check: font sizes fill the screen, content is well-positioned, colours match the design system, cards fit their content without unnecessary stretching.

### 5. Export to standalone file (optional, on request)

Once the presentation is confirmed, the user can optionally create a standalone shareable version using build.py. Write a `slides.json` file:

```json
{
  "title": "Presentation Title",
  "slides_html": "...",
  "custom_css": ""
}
```

Then build:

```bash
python {skill_path}/scripts/build.py slides.json -o presentation.html
```

### 6. Export to PDF (if requested)

Follow the steps in [references/printing-pdf.md](references/printing-pdf.md).

## Design Rules (mandatory)

### Colour Palette

Use ONLY the CSS custom property tokens defined in the template. See [references/design-system.md](references/design-system.md) for full values.

- Primary accent: `var(--accent)` (indigo)
- Semantic: `var(--green)`, `var(--amber)`, `var(--rose)` — each with `-tint` and `-border` variants
- Text: `var(--heading)` > `var(--subheading)` > `var(--body)` > `var(--muted)`
- Surfaces: `var(--bg)` > `var(--surface)` > `var(--elevated)`

**Traffic Light Rule (mandatory):** `--green`, `--amber`, and `--rose` are reserved for **semantic meaning only** — status (success/warning/risk), performance (positive/neutral/negative), or urgency. **Never** use traffic light colours to differentiate categories that carry no inherent risk or status meaning. For category differentiation, use `--accent` or neutral colours instead.

### Icons

- **Google Material Symbols Outlined** — loaded from Google Fonts in the template
- **Never use emoji as icons.** Always use Material Symbols for monochrome, styleable line-art icons
- Usage: `<span class="material-symbols-outlined">icon_name</span>`
- Colour via parent `color` property — icons inherit `currentColor`
- For circular icon containers, use `flex-shrink: 0` to prevent squishing

### Typography

- Font: Outfit (loaded from Google Fonts in the template)
- All sizes in `px` units — the 1280x720 fixed canvas scales uniformly via CSS transform. Never use `vw`, `vh`, or `rem` inside slides.
- **Use the typography scale tokens** (`--text-xs` through `--text-3xl`) for consistent sizing. The `.slide` element defaults to `font-size: var(--text-base)` (15px).
- **Minimum font size is 11px** (`--text-xs`). Never use smaller text inside slides.
- See [references/design-system.md](references/design-system.md) for the full type scale and token values

### Navigation Panel

Built into the template — do not modify its structure.

- **Regular slides** appear as round dots (7px) that expand into a wider pill (18px) when active
- **Section divider slides** (`slide-section` class) appear as vertical pipes (3px x 16px) — visually separating content sections in the nav
- This is automatic: the JS detects `slide-section` on the slide div and renders the correct pip type

### Layout

- Cards/surfaces fit their content — never use `flex: 1` to stretch cards
- Never set `position: relative` on slide-type classes (breaks base `position: absolute` sizing)
- `justify-content: center` for vertically centred content
- `justify-content: flex-end` for bottom-aligned content (section dividers)
- Padding: `28-50px` vertical, `50-76px` horizontal

### Canvas Architecture

The template uses a fixed 1280x720px canvas that scales uniformly to fit any screen via CSS `transform: scale()`. This means:
- All sizes must be in `px` — never use `vw`, `vh`, or `rem` inside the viewport
- Content is authored for a 1280x720 "virtual screen"
- Non-16:9 displays get centered letterboxing (dark bars on body)
- Print/PDF export removes the transform so slides flow naturally

## Slide Patterns

Review [assets/template.html](assets/template.html) for all base CSS and HTML structure. Built-in patterns:

- `slide-title` — centred title with inner frame and accent dot
- `slide-section` — section divider with large background number, bottom-aligned
- `slide-stat` — hero stat number centred with label and description
- `slide-text-image` — two-column: text left, image/visual right
- `slide-bullets` — heading + bullet list
- `slide-quote` — blockquote with attribution and accent bar
- `slide-compare` — two-column comparison cards
- `slide-cards` — grid of summary cards
- `slide-dashboard` — KPI row + detail cards
- `slide-mixed` — stats grid + narrative panel
- `slide-table` — styled data table with status pills
- `slide-multi` — multi-column breakdown with header stats

For custom layouts, define new CSS classes via `custom_css` in slides.json. These are examples — create whatever layout best serves the content.
