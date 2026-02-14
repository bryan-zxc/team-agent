# Frontend Development Guidelines

Read this file before making any frontend changes.

Always use the `/playwright-cli` skill to verify frontend changes work correctly in the browser before committing.

## Aesthetic Direction

Soft/ambient — warm, approachable, rounded. Think Arc browser meets Campfire. Supports dark and light modes. See `design-prototype.html` in the repo root for the visual reference.

## Design Tokens

All design tokens live as CSS custom properties in a global stylesheet. Components never hardcode colours, shadows, or radii — always reference variables.

### Colour Palette

Both themes use warm, muted tones. Sage green for primary accent, honey/amber for AI-related elements.

```css
/* Light */
--bg: #F5F2ED;
--surface: #FFFFFF;
--accent: #7B9E87;        /* sage green — primary actions, active states */
--accent-light: #E4EDE7;  /* accent backgrounds */
--warm: #C4956A;           /* amber — AI elements */
--warm-light: #F5EDE4;    /* AI backgrounds */
--text-primary: #2C2A27;
--text-secondary: #7A756D;
--text-muted: #B0AAA0;

/* Dark */
--bg: #161514;
--surface: #222120;
--accent: #8FB39A;
--warm: #D4A574;
--text-primary: #E0DCD6;
```

Full variable set is in the design prototype. Transfer to `src/app/globals.css` using `[data-theme="light"]` and `[data-theme="dark"]` selectors on the root element.

### Typography

| Role | Font | Weight | Notes |
|---|---|---|---|
| Headings | Bricolage Grotesque | 500–700 | Distinctive, friendly. Google Fonts. |
| Body / UI | Plus Jakarta Sans | 400–600 | Rounded terminals, warm and readable. Google Fonts. |

Load via Google Fonts in `layout.tsx` using `next/font/google` for self-hosting and performance.

Never use generic fonts (Inter, Roboto, Arial, system-ui).

### Spacing

Use a 4px base unit. Common values: 4, 8, 12, 16, 20, 24, 32, 40, 48. Generous padding is part of the aesthetic — don't compress.

### Border Radius

| Element | Radius |
|---|---|
| Buttons, inputs, cards | 12–14px |
| Message bubbles | 16px (6px on the tail corner) |
| Avatars | 50% (circle) |
| Small badges/pills | 4–6px |
| Logo mark | 10px |

### Shadows

Three levels, all warm-tinted (not pure black):
- `--shadow-sm`: subtle lift (cards at rest)
- `--shadow-md`: hover state
- `--shadow-lg`: elevated elements (modals, popovers)

## Styling

Use **CSS Modules** (built into Next.js). One `.module.css` file per component.

- Global variables and resets go in `src/app/globals.css`
- Component styles go in colocated `ComponentName.module.css` files
- Use `composes` for shared patterns rather than duplicating styles
- Use the `clsx` package for conditional class names

No CSS-in-JS. No Tailwind. The design system is specific enough that utility classes add noise.

## Component Patterns

### File Structure

Colocate component files:
```
src/components/chat/
  MessageList.tsx
  MessageList.module.css
  MessageInput.tsx
  MessageInput.module.css
```

### Conventions

- All components are functional components with TypeScript
- Use Next.js App Router conventions — `"use client"` only on components that need browser APIs (WebSocket, localStorage, event handlers)
- Keep server components as the default where possible
- Props types defined inline for simple components, extracted to `src/types/` when shared across components
- Prefer named exports over default exports for components (except page/layout files which require default)

### State Management

- Local state with `useState` / `useReducer` for UI state
- Custom hooks in `src/hooks/` for reusable logic (e.g. WebSocket connection, theme toggle)
- No global state library for now — prop drilling and context are sufficient at this scale

## Animation

Use **Motion** (`motion` package, formerly Framer Motion) for:
- Page transitions and staggered reveals
- Message entry animations
- Hover micro-interactions on cards

Use CSS transitions for simple state changes (hover, focus, theme toggle). Reserve Motion for orchestrated sequences.

Key animation values:
- Duration: 150–300ms for micro-interactions, 300–500ms for transitions
- Easing: `ease` or `ease-out` for most interactions
- Message entry: fade up from 8px, 300ms

## Accessibility

- All interactive elements must be keyboard accessible
- Use semantic HTML (`button`, `nav`, `main`, `aside`, not `div` with onClick)
- Colour contrast must meet WCAG AA in both themes
- Focus states must be visible — use the accent colour with a 3px ring
- ARIA labels on icon-only buttons

## Libraries

| Package | Purpose |
|---|---|
| `next` | Framework |
| `react` / `react-dom` | UI |
| `motion` | Animation |
| `clsx` | Conditional class names |

Do not add component libraries (Material UI, Chakra, shadcn, etc.). All components are custom-built to match the design system.

## Theme Switching

Store theme preference in localStorage under key `theme`. Apply as `data-theme` attribute on the `<html>` element. Default to system preference via `prefers-color-scheme` media query on first visit.

Wrap the toggle logic in a `useTheme` hook.
