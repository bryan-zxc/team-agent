# Design System Reference

## Aesthetic

Soft Contemporary — warm, refined, approachable. Light rounded corners, generous spacing, subtle depth through layered surfaces.

## Icons

**Google Material Symbols Outlined** — loaded from Google Fonts (same CDN as Outfit). The template includes the font link.

- Use the **Outlined** variant only (weight 400, fill 0, grade 0, optical size 24)
- Icons inherit `currentColor` — set colour via the parent element's `color` property
- **Never use emoji** (e.g. charts emoji) as icons — they are coloured, inconsistent across platforms, and cannot be styled
- Usage: `<span class="material-symbols-outlined">icon_name</span>`
- Browse available icons at https://fonts.google.com/icons?icon.set=Material+Symbols

### Icon Containers

When placing icons inside circular containers (common for card headers):

```css
.icon-circle {
  width: 52px; height: 52px; border-radius: 50%;
  border: 2px solid var(--heading);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; /* prevent squishing */
}
.icon-circle .material-symbols-outlined {
  font-size: 26px; color: var(--heading); line-height: 1;
}
```

## Typography

Font: **Outfit** (Google Fonts) — weights 300 (Light), 400 (Regular), 500 (Medium), 600 (Semibold), 700 (Bold), 800 (ExtraBold).

Fallback stack: `'Outfit', system-ui, sans-serif`

All sizes use `px` units. The viewport is a fixed 1280x720 canvas that scales uniformly via CSS `transform: scale()` to fit any screen, so px values behave identically to how they would in a 1280x720 design tool. Never use `vw`, `vh`, or `rem` inside slides.

### Typography Scale (CSS tokens)

The template defines CSS custom properties for a consistent type scale. **Always use these tokens** instead of hard-coding px values where possible:

| Token | Value | Use for |
|-------|-------|---------|
| `--text-xs` | 11px | Footnotes — **smallest allowed text** |
| `--text-sm` | 13px | Labels, captions, tags |
| `--text-base` | 15px | Body / paragraph text (slide default) |
| `--text-lg` | 20px | Sub-headings |
| `--text-xl` | 28px | Content headings |
| `--text-2xl` | 42px | Section divider headings |
| `--text-3xl` | 54px | Title slide heading |

**Minimum font size:** No text inside slides should be smaller than `var(--text-xs)` (11px). The `.slide` element defaults to `font-size: var(--text-base)` (15px) and `color: var(--body)`, so unstyled text will be readable by default.

### Reference Sizes

| Role | Size | Weight |
|------|------|--------|
| Title slide heading | 90px | 800 |
| Section divider heading | 76px | 700 |
| Big stat number | 230px | 800 |
| Content heading | 36–44px | 700 |
| Body / paragraph | 14–20px | 400 |
| Labels / captions | 11–13px | 500–600 |
| Nav dock text | 10–11px | 500–600 |

## Colour Palette

### Dark mode (default, `:root`)

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#171719` | Page background |
| `--surface` | `#1f1f24` | Card / elevated surface |
| `--elevated` | `#26262c` | Higher elevation |
| `--border` | `#2a2a2f` | Standard border |
| `--heading` | `#f0eff5` | Primary headings |
| `--subheading` | `#c8c8d0` | Secondary headings |
| `--body` | `#8a8a95` | Body text |
| `--muted` | `#6b6b78` | Subdued text |
| `--disabled` | `#44444f` | Inactive elements |
| `--accent` | `#7c8ae5` | Primary accent (indigo) |
| `--accent-tint` | `rgba(124,138,229,0.1)` | Accent background |
| `--accent-border` | `rgba(124,138,229,0.18)` | Accent border |
| `--green` | `#5b9a7a` | Positive / success |
| `--amber` | `#e0a05f` | Warning / in-progress |
| `--rose` | `#d46b6b` | Negative / at-risk |

Each semantic colour has a `-tint` variant (low-opacity background) and optionally a `-border` variant.

### Light mode (`html.light`)

| Token | Value |
|-------|-------|
| `--bg` | `#faf9f7` |
| `--surface` | `#ffffff` |
| `--heading` | `#1a1a1f` |
| `--accent` | `#5560c0` |
| `--green` | `#3d8a5e` |
| `--amber` | `#c49040` |
| `--rose` | `#c44e4e` |

## Layout Rules

- The viewport is a fixed 1280x720px canvas. JavaScript applies `transform: scale(Math.min(innerWidth/1280, innerHeight/720))` on load and resize. Non-16:9 screens get centered letterboxing.
- All slides use `position: absolute; inset: 0; top: 3px;` (3px for progress bar)
- Slides are `display: flex; flex-direction: column;` when active
- Padding: `28–50px` vertical, `50–76px` horizontal
- Cards / surfaces: `border-radius: 12–14px`, `1px solid var(--border)`
- Cards should fit their content — do NOT use `flex: 1` to stretch cards to fill space
- Use `justify-content: center` to vertically centre content, `flex-end` for bottom-aligned (section dividers)
- Pill badges: `border-radius: 100px`, accent-tint background, accent-border border

## Semantic Colour Usage

- `--accent` (indigo): primary emphasis, links, active indicators, decorative accents
- `--green`: positive metrics, success status, growth indicators
- `--amber`: warnings, in-progress status, caution indicators
- `--rose`: negative metrics, at-risk status, decline indicators
- Apply via inline `style` attribute: `style="color:var(--accent)"` or use utility classes like `.pill-green`, `.sc-up`, `.sc-down`

### Traffic Light Rule (mandatory)

**`--green`, `--amber`, and `--rose` are reserved for semantic meaning only** — use them to indicate status (success/warning/risk), performance (positive/neutral/negative), or urgency. **Never** use traffic light colours purely to differentiate categories that carry no inherent risk or status meaning. For category differentiation, use `--accent` or neutral colours instead.

## Important CSS Patterns

```css
/* Never set position: relative on slide-type classes — it overrides the base position: absolute */
.slide-title { justify-content: center; align-items: center; text-align: center; padding: 28px 64px; }
.slide-section { justify-content: flex-end; padding: 43px 64px 86px; }

/* Cards that contain content should NOT stretch to fill available space */
.grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; }
/* No flex: 1 or max-height on grid containers */
```
