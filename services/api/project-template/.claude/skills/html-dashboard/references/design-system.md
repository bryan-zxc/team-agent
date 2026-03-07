# Dashboard Design System Reference

For colours, typography font, icons, and semantic rules, see the shared design system: [../../../shared/design-system.md](../../../shared/design-system.md)

This file covers dashboard-specific layout and component guidelines.

## Page Layout

Dashboards use a **responsive scrollable page** — no fixed canvas, no CSS transform scaling. Content flows naturally and scrolls vertically.

- `max-width: 1200px`, centred with `margin: 0 auto`
- `padding: 32px 40px` on the page container
- Sections stack vertically with `40px` gap between them
- All sizes in `px` — no `vw`/`vh` units (page is responsive, not scaled)

## Typography Scale

| Token | Value | Use for |
|-------|-------|---------|
| `--text-xs` | 11px | Footnotes — **smallest allowed** |
| `--text-sm` | 13px | Labels, captions, table headers, change badges |
| `--text-base` | 14px | Body text, table cells, paragraphs |
| `--text-lg` | 18px | Section titles |
| `--text-xl` | 24px | Dashboard title |
| `--text-2xl` | 32px | KPI values |

Font: **Outfit** (same as slides). Weights: 400 (body), 500 (labels), 600 (headings), 700 (titles), 800 (KPI values).

## Section Layout Classes

Each section uses a CSS grid layout. The layout name maps directly to a CSS class on the section's component container.

| Layout | Grid | Use for |
|--------|------|---------|
| `row` | `auto-fit, minmax(200px, 1fr)` | KPI cards — auto-wraps to available width |
| `grid-2` | `1fr 1fr` | Two equal panels |
| `grid-3` | `1fr 1fr 1fr` | Three equal panels |
| `grid-4` | `1fr 1fr 1fr 1fr` | Four equal panels |
| `grid-2-wide` | `2fr 1fr` | Primary visualisation + sidebar |
| `grid-3-wide` | `2fr 1fr 1fr` | Primary visualisation + two sidebars |
| `full` | `1fr` | Tables, large charts needing full width |

All grids use `gap: 16px`.

## Component Styles

### KPI Cards
- Background: `var(--surface)`, border: `1px solid var(--border)`, border-radius: `12px`
- Padding: `20px 24px`
- Icon: 40x40px circle with `var(--accent-tint)` background, Material Symbol inside
- Value: `--text-2xl` (32px), weight 800, colour `var(--heading)`
- Label: `--text-sm` (13px), weight 500, colour `var(--muted)`
- Change badge: `--text-xs` (11px), weight 600, pill shape
  - Up: `var(--green)` text on `var(--green-tint)` background
  - Down: `var(--rose)` text on `var(--rose-tint)` background
  - Neutral: `var(--muted)` text on `var(--surface)` background

### Chart Cards
- Background: `var(--surface)`, border: `1px solid var(--border)`, border-radius: `12px`
- Padding: `20px 24px`
- Title: `--text-base` (14px), weight 600, colour `var(--heading)`
- Canvas height: `240px` default, adjustable via component data
- Chart.js themed to match design tokens (grid lines, tooltips, font)

### Tables
- Background: `var(--surface)`, border: `1px solid var(--border)`, border-radius: `12px`, overflow hidden
- Header: `var(--elevated)` background, `--text-sm` uppercase, weight 600, colour `var(--muted)`
- Cells: `--text-base`, colour `var(--body)`, padding `12px 16px`
- First column: weight 600, colour `var(--subheading)`
- Row borders: `1px solid var(--border)`
- Status pills: `pill-green`, `pill-amber`, `pill-rose` with semantic tint backgrounds
- Sortable: clickable headers with sort indicator arrow

### Text Blocks
- Title: `--text-lg` (18px), weight 600, colour `var(--heading)`
- Body: `--text-base` (14px), weight 400, colour `var(--body)`, line-height 1.6

## Chart.js Theming

Charts must visually match the design system. The template sets Chart.js defaults:

- `Chart.defaults.font.family`: `'Outfit', system-ui, sans-serif`
- `Chart.defaults.color`: `var(--muted)` for axis labels
- `Chart.defaults.borderColor`: `var(--border)` for grid lines
- Tooltip: `var(--elevated)` background, `var(--heading)` text, `12px` border-radius
- Dataset colours: use `--accent` as primary, then `--green`, `--amber`, `--rose` only when semantically appropriate. For multi-series without semantic meaning, use opacity variants of `--accent`.

## Theme Toggle

- Dark mode: default (`:root` tokens)
- Light mode: `.light` class on `<html>` (overrides tokens to light palette)
- Toggle button in header, same icon swap as slides (moon/sun)
- Charts must be destroyed and re-created on theme change to pick up new token values
