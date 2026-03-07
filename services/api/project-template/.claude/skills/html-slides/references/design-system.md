# Design System Reference

For colours, typography, icons, and semantic rules, see the shared design system: [../../../shared/design-system.md](../../../shared/design-system.md)

This file covers slide-specific layout and typography sizing.

## Canvas Architecture

The template uses a fixed 1280x720px canvas that scales uniformly via CSS `transform: scale()` to fit any screen.

- All sizes must be in `px` — never use `vw`, `vh`, or `rem` inside slides
- Content is authored for a 1280x720 "virtual screen"
- Non-16:9 displays get centred letterboxing (dark bars on body)
- Print/PDF export removes the transform so slides flow naturally

## Typography Scale (CSS tokens)

All sizes in `px` units (the fixed 1280x720 canvas scales uniformly — px values behave identically to a 1280x720 design tool).

| Token | Value | Use for |
|-------|-------|---------|
| `--text-xs` | 11px | Footnotes — **smallest allowed text** |
| `--text-sm` | 13px | Labels, captions, tags |
| `--text-base` | 15px | Body / paragraph text (slide default) |
| `--text-lg` | 20px | Sub-headings |
| `--text-xl` | 28px | Content headings |
| `--text-2xl` | 42px | Section divider headings |
| `--text-3xl` | 54px | Title slide heading |

**Minimum font size:** No text inside slides should be smaller than `var(--text-xs)` (11px).

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

## Slide Layout Rules

- All slides use `position: absolute; inset: 0; top: 3px;` (3px for progress bar)
- Slides are `display: flex; flex-direction: column;` when active
- Padding: `28–50px` vertical, `50–76px` horizontal
- Never set `position: relative` on slide-type classes (breaks base `position: absolute` sizing)
- `justify-content: center` for vertically centred content
- `justify-content: flex-end` for bottom-aligned content (section dividers)

## Important CSS Patterns

```css
/* Never set position: relative on slide-type classes — it overrides the base position: absolute */
.slide-title { justify-content: center; align-items: center; text-align: center; padding: 28px 64px; }
.slide-section { justify-content: flex-end; padding: 43px 64px 86px; }

/* Cards that contain content should NOT stretch to fill available space */
.grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; }
/* No flex: 1 or max-height on grid containers */
```
