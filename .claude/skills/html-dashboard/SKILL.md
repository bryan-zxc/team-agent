---
name: html-dashboard
description: >
  Build standalone, shareable HTML dashboards with charts, tables, KPI cards, and
  interactive features. Uses the shared design system (Soft Contemporary aesthetic,
  Outfit font, Indigo accent palette) with Chart.js for visualisations. Data lives
  in JSON; the template is a rendering engine. Triggers on: "create a dashboard",
  "build a dashboard", "HTML dashboard", "dashboard for X", "data dashboard".
  Do NOT use for slide presentations — use html-slides instead.
---

# HTML Dashboards

Build standalone HTML dashboards using the shared design system. Output is a single shareable `.html` file with dark/light mode, interactive charts (Chart.js), sortable tables, and KPI summary cards. Data is defined in JSON; the template renders it automatically.

## Workflow

### 1. Analyse Requirements

Determine what sections the dashboard needs — KPIs, charts, tables, narrative text. Read [../../shared/design-system.md](../../shared/design-system.md) for the colour palette, icons, and semantic rules, and [references/design-system.md](references/design-system.md) for dashboard-specific layout patterns, typography, and component guidelines.

### 2. Write calculate.py (if needed)

If the dashboard requires data processing from source files (CSV, spreadsheets, APIs, etc.), write a `calculate.py` that reads, processes, and outputs a `data.json` file. Skip if data is already prepared or purely illustrative.

### 3. Write data.json

Structure the dashboard data following the JSON schema below. The template's JavaScript rendering engine reads this and builds the entire dashboard.

### 4. Build the dashboard

```bash
python {skill_path}/scripts/build.py data.json -o dashboard.html
```

This embeds the JSON data into the template, producing a standalone HTML file.

### 5. Validate with Playwright

**Always use the `/playwright-cli` skill to visually verify output.** Start a local server and screenshot:

```bash
python3 -m http.server 8787 &
playwright-cli open http://localhost:8787/dashboard.html
playwright-cli screenshot
playwright-cli eval "window.scrollTo(0, 500)"
playwright-cli screenshot
```

Check: KPI values visible, charts render with data, tables populated, dark/light toggle works, layout matches the intended grid.

## JSON Schema

```json
{
  "title": "Dashboard Title",
  "subtitle": "Optional subtitle",
  "theme": "dark",
  "sections": [
    {
      "title": "Section Title",
      "layout": "row | grid-2 | grid-3 | grid-4 | grid-2-wide | grid-3-wide | full",
      "components": [ ... ]
    }
  ]
}
```

### Sections

Each section has a `title` (displayed as an uppercase label), a `layout` (CSS grid pattern), and an array of `components`.

### Layout Patterns

All layout patterns are baked into the template CSS. Choose the one that fits the content:

| Layout | Grid | Use for |
|--------|------|---------|
| `row` | `auto-fit, minmax(200px, 1fr)` | KPI cards — auto-wraps |
| `grid-2` | `1fr 1fr` | Two equal panels |
| `grid-3` | `1fr 1fr 1fr` | Three equal panels |
| `grid-4` | `1fr 1fr 1fr 1fr` | Four equal panels |
| `grid-2-wide` | `2fr 1fr` | Primary chart + sidebar |
| `grid-3-wide` | `2fr 1fr 1fr` | Primary chart + two sidebars |
| `full` | `1fr` | Tables, large charts |

### Component Types

#### KPI

```json
{
  "type": "kpi",
  "label": "Revenue",
  "value": "$1.24M",
  "change": "+12.3%",
  "direction": "up",
  "icon": "payments"
}
```

- `direction`: `"up"` (green), `"down"` (rose), or omit for neutral
- `icon`: Material Symbols icon name (optional)

#### Chart

```json
{
  "type": "chart",
  "title": "Revenue Over Time",
  "height": 280,
  "chart": {
    "type": "line",
    "data": {
      "labels": ["Jan", "Feb", "Mar"],
      "datasets": [{
        "label": "Revenue",
        "data": [100, 150, 200],
        "borderColor": "#7c8ae5",
        "backgroundColor": "rgba(124,138,229,0.1)",
        "fill": true,
        "tension": 0.3
      }]
    },
    "options": {}
  }
}
```

- `chart` is a standard Chart.js configuration object (type, data, options)
- The template applies design-system-aware defaults (font, grid colours, tooltip styling)
- Supported chart types: `line`, `bar`, `doughnut`, `pie`, `radar`, `polarArea`
- `height`: optional canvas max-height in px (default 280)

#### Table

```json
{
  "type": "table",
  "title": "Recent Transactions",
  "sortable": true,
  "columns": [
    { "key": "date", "label": "Date" },
    { "key": "amount", "label": "Amount", "align": "right" },
    { "key": "status", "label": "Status", "pill": true }
  ],
  "rows": [
    { "date": "27 Feb", "amount": "$12,400", "status": "Completed", "status_color": "green" },
    { "date": "26 Feb", "amount": "$8,750", "status": "Pending", "status_color": "amber" }
  ]
}
```

- `sortable`: enables click-to-sort on column headers
- `align`: `"right"` for numeric columns
- `pill`: when `true`, renders the cell value as a coloured pill; pair with `<key>_color` field in row data (`"green"`, `"amber"`, `"rose"`, `"accent"`)

#### Text

```json
{
  "type": "text",
  "title": "Summary",
  "body": "Analysis text here."
}
```

- `body`: string or array of strings (each becomes a `<p>`)

## Design Rules (mandatory)

### Colour Palette

Use ONLY the CSS custom property tokens defined in the template. See [../../shared/design-system.md](../../shared/design-system.md) for full values.

- Primary accent: `var(--accent)` (indigo)
- Semantic: `var(--green)`, `var(--amber)`, `var(--rose)` — each with `-tint` and `-border` variants
- Text: `var(--heading)` > `var(--subheading)` > `var(--body)` > `var(--muted)`
- Surfaces: `var(--bg)` > `var(--surface)` > `var(--elevated)`

**Traffic Light Rule (mandatory):** `--green`, `--amber`, and `--rose` are reserved for **semantic meaning only** — status (success/warning/risk), performance (positive/neutral/negative), or urgency. **Never** use traffic light colours to differentiate categories. For category differentiation, use opacity variants of `--accent`.

### Chart Colours

- Primary dataset: `#7c8ae5` (accent) / `rgba(124,138,229,0.1)` (fill)
- Multi-series without semantic meaning: use opacity variants of accent (`rgba(124,138,229,0.8)`, `rgba(124,138,229,0.5)`, `rgba(124,138,229,0.3)`)
- Semantic series (revenue vs costs, success vs failure): use `--green`, `--rose`, `--amber` appropriately

### Icons

- **Google Material Symbols Outlined** — loaded from Google Fonts in the template
- **Never use emoji as icons.** Always use Material Symbols
- Usage in JSON: pass the icon name string (e.g. `"payments"`, `"group"`, `"trending_up"`)
- Browse: https://fonts.google.com/icons?icon.set=Material+Symbols

### Typography

- Font: Outfit (loaded from Google Fonts in the template)
- All sizes in `px` — the dashboard is responsive (not a fixed canvas)
- **Minimum font size is 11px** (`--text-xs`)
- See [references/design-system.md](references/design-system.md) for the full type scale
