# Design System Reference

## Aesthetic

Soft Contemporary — warm, refined, approachable. Light rounded corners, generous spacing, subtle depth through layered surfaces.

## Typography

Font: **Cabinet Grotesk** (Google Fonts) — weights 400, 500, 600, 700, 800.

All sizes use viewport-relative units (`vw`) so slides scale to any screen size.

| Role | Size | Weight |
|------|------|--------|
| Title slide heading | 7vw | 800 |
| Section divider heading | 6vw | 700 |
| Big stat number | 18vw | 800 |
| Content heading | 2.8–3.5vw | 700 |
| Body / paragraph | 1.1–1.5vw | 400 |
| Labels / captions | 0.85–1vw | 500 |
| Nav dock text | 0.65–0.7rem | 500–600 |

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

- All slides use `position: absolute; inset: 0; top: 3px;` (3px for progress bar)
- Slides are `display: flex; flex-direction: column;` when active
- Padding: `4–6vh` vertical, `4–6vw` horizontal
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

## Important CSS Patterns

```css
/* Never set position: relative on slide-type classes — it overrides the base position: absolute */
.slide-title { justify-content: center; align-items: center; text-align: center; padding: 4vh 5vw; }
.slide-section { justify-content: flex-end; padding: 6vh 5vw 12vh; }

/* Cards that contain content should NOT stretch to fill available space */
.grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.2vw; }
/* No flex: 1 or max-height on grid containers */
```
