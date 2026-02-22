# ADR-0005: Workbench infrastructure using dockview, react-arborist, and Monaco

## Context

The app needed a VS Code-style workbench shell — an activity bar to switch side panel views, a file tree browser, a code editor/viewer, and a tabbed/splittable main area where rooms and files can be opened as draggable tabs. The existing layout was a simple two-column grid (fixed sidebar + chat) with no support for multiple open views.

Two broad approaches were evaluated: extracting components from the VS Code source, or using purpose-built libraries.

## Alternatives Considered

**Extract from VS Code source (Code-OSS)**
The full repo is 1.3GB. Key components (tree widget ~7,500 lines, workbench layout, tab management) are deeply coupled to VS Code's dependency injection, service layer, and custom DOM framework. Extraction would require significant refactoring with ongoing maintenance burden as upstream changes. Rejected as impractical.

**Build entirely from scratch**
Custom drag-and-drop tab management, split views, virtualised tree, and code editor would each be substantial engineering efforts. The combined scope would dwarf the actual feature work. Rejected as disproportionate effort.

## Decision

Use three specialised infrastructure libraries:

- **dockview** — zero-dependency layout manager for the tabbed, splittable editor area. Provides drag-and-drop tab reordering, split views, and serialisable layout state. Custom themed via CSS variable overrides to match the design system.
- **react-arborist** — file tree component with expand/collapse, drag-and-drop reordering, inline rename/create, and virtualised rendering via react-window. Handles keyboard navigation out of the box.
- **@monaco-editor/react** — React wrapper for Monaco (VS Code's standalone editor). Provides syntax highlighting, line numbers, and language services. Themed via `monaco.editor.defineTheme()` with custom light/dark themes that mirror the app's design tokens.

These libraries handle the hard infrastructure problems (split layout serialisation, virtualised tree rendering, code parsing) while all surrounding UI — activity bar, side panels, tab content, room views — remains custom-built with CSS Modules.

The fe-dev skill was updated to distinguish specialised infrastructure libraries (acceptable) from UI component libraries like Material UI or Chakra (still prohibited). Third-party stylesheets are imported globally with theme overrides in dedicated CSS files; all custom component styles remain CSS Modules.

Room-internal tabs (e.g. Chat | Workloads within a room) are fixed — simple React state, not managed by dockview. Only workspace-level tabs (rooms, files) are draggable/splittable.

## Consequences

- Workspace layout, file tree, and code editing get production-quality UX without building from scratch
- dockview and Monaco bring their own theming APIs that sit outside CSS custom properties — theme overrides must be maintained separately
- react-arborist internally depends on react-dnd and redux, adding transitive dependencies (though these don't leak into app code)
- Future panel types (search results, settings, member profiles) can be added as dockview panels with minimal boilerplate
