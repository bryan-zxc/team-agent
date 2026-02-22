---
name: fe-dev
description: Frontend development guidelines for the Team Agent project. Use when making any changes to frontend code in services/frontend/, including components, pages, styles, hooks, types, or configuration. Provides the design system, styling rules, component patterns, accessibility requirements, and animation guidelines.
---

# Frontend Development Guide

Read `services/frontend/frontend-design.md` for UX/navigation design context.

Verify all frontend changes in the browser using `/playwright-cli` before committing.

## Aesthetic Direction

Soft/ambient — warm, approachable, rounded. Think Arc browser meets Campfire. Supports dark and light modes.

## Design Tokens

All tokens live as CSS custom properties in `src/app/globals.css`, scoped to `[data-theme="light"]` and `[data-theme="dark"]`. Use these variables for all visual values.

### Colour Variables

| Variable | Light | Dark | Purpose |
|---|---|---|---|
| `--bg` | `#F5F2ED` | `#161514` | Page background |
| `--bg-subtle` | `#EDE9E3` | `#1C1B19` | Subtle background |
| `--surface` | `#FFFFFF` | `#222120` | Cards, sidebar |
| `--surface-hover` | `#F8F6F2` | `#2A2928` | Hover state |
| `--surface-active` | `#F0EDE8` | `#323130` | Active/pressed |
| `--accent` | `#7B9E87` | `#8FB39A` | Primary actions (sage green) |
| `--accent-hover` | `#6A8B75` | `#A3C4AE` | Accent hover |
| `--accent-text` | `#FFFFFF` | `#161514` | Text on accent bg |
| `--accent-light` | `#E4EDE7` | `rgba(143,179,154,0.12)` | Accent backgrounds |
| `--warm` | `#C4956A` | `#D4A574` | AI elements (amber) |
| `--warm-light` | `#F5EDE4` | `rgba(212,165,116,0.12)` | AI backgrounds |
| `--text-primary` | `#2C2A27` | `#E0DCD6` | Main text |
| `--text-secondary` | `#7A756D` | `#8E8983` | Secondary text |
| `--text-muted` | `#B0AAA0` | `#555250` | Muted/placeholder |
| `--border` | `#E4E0D8` | `#2E2D2B` | Borders |
| `--border-light` | `#EEEAE4` | `#262524` | Subtle borders |
| `--error` | `#c44` | `#d66` | Error messages |
| `--overlay` | `rgba(44,42,39,0.3)` | `rgba(0,0,0,0.5)` | Modal overlays |

Shadow levels (warm-tinted, not pure black): `--shadow-sm` (rest), `--shadow-md` (hover), `--shadow-lg` (modals).

Chat bubbles: `--bubble-self`, `--bubble-other`, `--bubble-ai`. Spinners: `--spinner-track`, `--spinner-head`.

### Typography

| Role | Font | Variable | Weight |
|---|---|---|---|
| Headings | Bricolage Grotesque | `--font-heading` | 500–700 |
| Body / UI | Plus Jakarta Sans | `--font-body` | 400–600 |
| Code | SF Mono / Fira Code | `--font-mono` | 400 |

Loaded via `next/font/google` in `layout.tsx`.

### Spacing & Radius

4px base unit. Common: 4, 8, 12, 16, 20, 24, 32, 40, 48. Generous padding is part of the aesthetic.

| Element | Radius |
|---|---|
| Buttons, inputs, cards | 12–14px |
| Message bubbles | 16px (6px on tail corner) |
| Avatars | 50% |
| Badges/pills | 4–6px |
| Logo mark | 10px |

## Styling

Use **CSS Modules** — one `.module.css` file colocated with each component.

- Global variables and resets in `src/app/globals.css`
- Component styles in colocated `ComponentName.module.css` files
- Extract shared components (in `src/components/`) when styles duplicate across pages
- Use `clsx` for conditional class names with ternaries
- Put all visual values in CSS using design token variables — keep inline styles out of JSX
- Third-party library stylesheets (dockview, Monaco) are imported globally. Theme overrides for these libraries live in dedicated CSS files that map design tokens to the library's theming API. All custom component styles remain CSS Modules.

```tsx
import clsx from "clsx";

<div className={clsx(styles.avatar, isAi ? styles.avatarAi : styles.avatarHuman)} />
<button className={clsx(styles.tab, isActive && styles.tabActive)} />
```

## Component Patterns

```
src/components/chat/
  MessageList.tsx
  MessageList.module.css
```

- Functional components with TypeScript
- `"use client"` only on components using browser APIs (WebSocket, localStorage, event handlers)
- Named exports for components, default exports for page/layout files
- Shared types in `src/types/`, custom hooks in `src/hooks/`
- Local state with `useState` / `useReducer`. No global state library.

## Icons

Never use emoji characters or text symbols as icons. All icons must be inline SVGs using `stroke="currentColor"` so they inherit colour from the parent and respond to theme changes. Use Feather-style icons (24×24 viewBox, `strokeWidth="1.8"`, `strokeLinecap="round"`, `strokeLinejoin="round"`). Size icons via `width`/`height` props (common sizes: 14px for tab icons, 18–20px for activity bar, 16px for inline actions). When a new icon is needed that doesn't match an existing one, discuss the design before implementing.

## Accessibility

Global `:focus-visible` ring is defined in `globals.css` (3px accent outline). For inputs with custom border-based focus:

```css
.input:focus-visible {
  outline: none;
  border-color: var(--accent);
}
```

Use `aria-label` on icon-only buttons:

```tsx
<button onClick={toggle} aria-label="Toggle theme">{icon}</button>
```

Use semantic HTML: `<header>` for headers, `<nav>` for navigation, `<main>` for primary content, `<aside>` for sidebar.

## Animation

Use **Motion** (`motion/react`) for orchestrated sequences (page transitions, staggered reveals, modal entry/exit). Use CSS transitions for simple state changes (hover, focus, theme toggle).

```css
transition: all 0.2s ease;           /* hover/focus */
transition: background 0.4s ease;    /* theme toggle */
```

150–300ms for micro-interactions, 300–500ms for transitions.

## Libraries

| Package | Purpose |
|---|---|
| `next` | Framework |
| `react` / `react-dom` | UI |
| `motion` | Animation |
| `clsx` | Conditional class names |
| `react-markdown` + `remark-gfm` | Markdown rendering |
| `dockview` | Workbench layout — tabbed, splittable editor area |
| `react-arborist` | File tree with expand/collapse, DnD, rename, CRUD |
| `@monaco-editor/react` | Code editor/viewer with syntax highlighting |

No UI component libraries (Material UI, Chakra, shadcn). Specialised infrastructure libraries (layout, tree, code editor) are used where building from scratch is impractical — wrap them in custom components.

## Theme Switching

Theme stored in localStorage under key `theme`. Applied as `data-theme` on `<html>`. Defaults to system preference via `prefers-color-scheme`. Toggle logic in `useTheme` hook. Monaco editor theme must be synced separately via `monaco.editor.setTheme()` when the app theme changes — custom Monaco themes (`team-agent-light`, `team-agent-dark`) mirror our design tokens.
