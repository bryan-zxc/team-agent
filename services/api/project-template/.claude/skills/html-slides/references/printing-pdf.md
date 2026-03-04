# PDF Printing Reference

## Overview

The template has built-in `@media print` styles that produce landscape PDF output matching the 1280x720 slide canvas:

- **One slide per page** with `page-break-after: always`
- **Landscape orientation** via `@page { size: 1280px 720px; margin: 0 }`
- **Navigation hidden** — nav dock, progress bar, and pips are removed
- **Backgrounds preserved** — `print-color-adjust: exact` forces backgrounds and colours to print
- **Light mode by default** — all colour tokens are overridden to the light palette
- **Video slides excluded** — slides containing `<video>` elements are automatically hidden

## Quick Start

### Light mode PDF (default)

```bash
playwright-cli run-code "<rasterise-icons snippet from below>"
playwright-cli pdf
```

### Dark mode PDF

```bash
playwright-cli eval "setPrintMode('dark')"
playwright-cli run-code "<rasterise-icons snippet from below>"
playwright-cli pdf
```

`setPrintMode('dark')` adds the `print-dark` class to `<html>`, activating dark-mode print styles. To revert: `setPrintMode('light')`.

## How It Works

The template print CSS has two layers inside `@media print`:

1. **Default light-mode rules** — override all CSS custom property tokens to light-mode values.

2. **Dark-mode override** — scoped to `html.print-dark`. When the `print-dark` class is present, these rules override with dark-mode tokens.

### Key CSS rules

| Rule | Purpose |
|------|---------|
| `@page { size: 1280px 720px; margin: 0 }` | Forces landscape pages matching canvas size |
| `* { print-color-adjust: exact !important }` | Forces backgrounds and colours to print |
| `.slide { width: 1280px; height: 720px }` | Fixed slide dimensions for consistent output |
| `.slide:has(video) { display: none !important }` | Hides unprintable video slides |

## Material Symbols Icons — CRITICAL

**Chromium's PDF renderer does NOT embed the Google Material Symbols font.** Icons render correctly on screen but appear as empty circles (or boxes) in PDF output — regardless of whether you use ligature text (`monitoring`) or Unicode codepoints (`&#xf190;`). Canvas `fillText` also fails because it can't access the CDN-loaded font.

### The fix: Playwright element screenshots

Before generating the PDF, use Playwright's `run-code` to screenshot each icon element and replace it with the captured image. This captures the exact on-screen rendering as a bitmap.

**You must run this before every `playwright-cli pdf`:**

```bash
playwright-cli run-code "async page => {
  await page.evaluateHandle(() => document.fonts.ready);
  await page.evaluate(() => {
    document.querySelectorAll('.slide').forEach(s => {
      s.style.display = 'flex';
      s.style.position = 'relative';
      s.style.width = '1280px';
      s.style.height = '720px';
    });
  });
  const icons = await page.locator('.material-symbols-outlined').all();
  for (const icon of icons) {
    try {
      const buf = await icon.screenshot({ type: 'png', scale: 'device' });
      const b64 = buf.toString('base64');
      const box = await icon.boundingBox();
      if (!box) continue;
      await icon.evaluate((el, data) => {
        const img = document.createElement('img');
        img.src = 'data:image/png;base64,' + data.b64;
        img.style.width = data.w + 'px';
        img.style.height = data.h + 'px';
        img.style.display = 'block';
        el.textContent = '';
        el.appendChild(img);
      }, { b64, w: box.width, h: box.height });
    } catch(e) {}
  }
  await page.evaluate(() => {
    document.querySelectorAll('.slide').forEach(s => {
      s.style.display = '';
      s.style.position = '';
      s.style.width = '';
      s.style.height = '';
    });
  });
  return 'Icons rasterised';
}"
```

### How it works

1. Makes all slides visible (icons may be on non-active slides)
2. Waits for fonts to fully load
3. Screenshots each `.material-symbols-outlined` element via Playwright
4. Replaces the span content with the screenshot as a base64 `<img>`
5. Restores slide visibility to normal

This is a one-way operation — once icons are rasterised, reload the page before further screen interaction.

### Icon authoring

Use standard Material Symbols markup in the HTML:

```html
<span class="material-symbols-outlined">monitoring</span>
```

No special HTML changes needed. The Playwright rasterisation step handles the PDF conversion.

## backdrop-filter Workaround

CSS `backdrop-filter: blur()` with semi-transparent backgrounds does **not** render in Chromium's print/PDF engine. Elements using this pattern will appear invisible in the PDF.

### The fix: add print-specific solid backgrounds

When building custom slide layouts that use `backdrop-filter`, add a corresponding print override in the `{{CUSTOM_CSS}}` section:

```css
/* Screen styles */
.my-glass-card {
  background: rgba(0,0,0,0.30);
  backdrop-filter: blur(4px);
}

/* Print override */
@media print {
  .my-glass-card {
    background: var(--surface) !important;
    backdrop-filter: none !important;
  }
}
```

Replace the semi-transparent background with the nearest solid colour from the design system tokens.

## Blank Trailing Page

A blank trailing page sometimes appears after the last slide.

### Post-processing fix

If a blank trailing page appears, strip it with PyMuPDF:

```python
import pymupdf
import os

doc = pymupdf.open("presentation.pdf")
last = doc[-1]
if not last.get_text().strip():
    doc.delete_page(-1)
    tmp = "presentation_tmp.pdf"
    doc.save(tmp)
    doc.close()
    os.replace(tmp, "presentation.pdf")
else:
    doc.close()
```

## Custom Print Overrides

For presentation-specific print adjustments, add `@media print { }` rules inside the `{{CUSTOM_CSS}}` section. Custom CSS appears after the template's print styles, so it will override them.

```css
@media print {
  .custom-glass-panel {
    background: var(--surface) !important;
    backdrop-filter: none !important;
  }
}
```

### Dark-mode-specific overrides

Prefix selectors with `html.print-dark` to target only dark-mode print:

```css
@media print {
  html.print-dark .custom-panel {
    background: #1f1f24 !important;
  }
}
```
