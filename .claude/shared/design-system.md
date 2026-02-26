# Shared Design System

Soft Contemporary — warm, refined, approachable. Light rounded corners, generous spacing, subtle depth through layered surfaces.

## Icons

**Google Material Symbols Outlined** — loaded from Google Fonts CDN (same link as Outfit).

- Use the **Outlined** variant only (weight 400, fill 0, grade 0, optical size 24)
- Icons inherit `currentColor` — set colour via the parent element's `color` property
- **Never use emoji** as icons — they are coloured, inconsistent across platforms, and cannot be styled
- Usage: `<span class="material-symbols-outlined">icon_name</span>`
- Browse available icons at https://fonts.google.com/icons?icon.set=Material+Symbols

### Icon Containers

When placing icons inside circular containers:

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

## Colour Palette

### Dark mode (default, `:root`)

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#171719` | Page background |
| `--surface` | `#1f1f24` | Card / elevated surface |
| `--elevated` | `#26262c` | Higher elevation |
| `--border` | `#2a2a2f` | Standard border |
| `--border-subtle` | `#35353c` | Subtle borders |
| `--heading` | `#f0eff5` | Primary headings |
| `--subheading` | `#c8c8d0` | Secondary headings |
| `--body` | `#8a8a95` | Body text |
| `--muted` | `#6b6b78` | Subdued text |
| `--disabled` | `#44444f` | Inactive elements |
| `--accent` | `#7c8ae5` | Primary accent (indigo) |
| `--accent-tint` | `rgba(124,138,229,0.1)` | Accent background |
| `--accent-border` | `rgba(124,138,229,0.18)` | Accent border |
| `--green` | `#5b9a7a` | Positive / success |
| `--green-tint` | `rgba(91,154,122,0.1)` | Green background |
| `--green-border` | `rgba(91,154,122,0.15)` | Green border |
| `--amber` | `#e0a05f` | Warning / in-progress |
| `--amber-tint` | `rgba(224,160,95,0.12)` | Amber background |
| `--rose` | `#d46b6b` | Negative / at-risk |
| `--rose-tint` | `rgba(212,107,107,0.12)` | Rose background |

Each semantic colour has a `-tint` variant (low-opacity background) and optionally a `-border` variant.

### Light mode (`html.light`)

| Token | Value |
|-------|-------|
| `--bg` | `#faf9f7` |
| `--surface` | `#ffffff` |
| `--elevated` | `#f5f4f2` |
| `--border` | `#e8e6e3` |
| `--border-subtle` | `#d5d3d0` |
| `--heading` | `#1a1a1f` |
| `--subheading` | `#4a4a55` |
| `--body` | `#6b6b78` |
| `--muted` | `#9a9aa5` |
| `--accent` | `#5560c0` |
| `--accent-tint` | `rgba(85,96,192,0.08)` |
| `--accent-border` | `rgba(85,96,192,0.15)` |
| `--green` | `#3d8a5e` |
| `--green-tint` | `rgba(61,138,94,0.08)` |
| `--amber` | `#c49040` |
| `--amber-tint` | `rgba(196,144,64,0.1)` |
| `--rose` | `#c44e4e` |
| `--rose-tint` | `rgba(196,78,78,0.08)` |

## Semantic Colour Usage

- `--accent` (indigo): primary emphasis, links, active indicators, decorative accents
- `--green`: positive metrics, success status, growth indicators
- `--amber`: warnings, in-progress status, caution indicators
- `--rose`: negative metrics, at-risk status, decline indicators
- Apply via inline `style` attribute: `style="color:var(--accent)"` or use utility classes

### Traffic Light Rule (mandatory)

**`--green`, `--amber`, and `--rose` are reserved for semantic meaning only** — use them to indicate status (success/warning/risk), performance (positive/neutral/negative), or urgency. **Never** use traffic light colours purely to differentiate categories that carry no inherent risk or status meaning. For category differentiation, use `--accent` or neutral colours instead.

## Surface & Card Rules

- Cards / surfaces: `border-radius: 12–14px`, `1px solid var(--border)`
- Cards should fit their content — do NOT use `flex: 1` to stretch cards to fill space
- Pill badges: `border-radius: 100px`, accent-tint background, accent-border border
