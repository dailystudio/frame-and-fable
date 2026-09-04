# Storybook Craft Viewer 📖🎨

An interactive Material Design 3 (MD3) web application built with Vue 3 and Vite to review and inspect output workspaces produced by `storybook-craft`.

## Features

- **Material Design 3 (MD3) Design System**:
  - Full color token system supporting dynamic Light & Dark themes.
  - Surface elevations, rounded shapes (`var(--shape-corner-*)`), outlined/tonal/elevated cards, chips, and top app bar.
  - Responsive navigation rail for desktop & bottom navigation for mobile viewports.
- **Story Reader**:
  - Markdown presentation of the generated story (`<stem>-output.md`).
  - Automatic replacement of scene media tags (`<!-- storybook-media -->`) with interactive visual cards and video players.
  - Adjustable reading font size and toggleable raw markdown viewer with one-click copy.
- **Character Visual DNA Gallery**:
  - Grid of character profiles with roles, source indicators, and visual DNA.
  - Refined portrait prompts with one-click clipboard copying for quick iteration.
  - Gallery of reference photos (`ref_001.png`, `ref_002.png`, etc.) with full-resolution inspection.
- **Art Style & Reference Profile**:
  - Visual art direction prompt and environment reference generator prompts.
  - Moodboard gallery showing style reference images.
- **Generated Media Gallery**:
  - Grid of generated scene images (`images/`) and video clips (`videos/`).
  - Filters for All, Images, and Videos with file sizes and scene prompt metadata.
- **Scene Breakdown & Tag Inspector**:
  - Structured list of all scene tags from markdown.
  - Real-time status detection: `Generated` vs `Pending`.
- **Native Modal Lightbox**:
  - Built with `<dialog closedby="any">` and light-dismiss backdrop fallback per modern web standards.
  - Full-resolution preview of images and videos with prompt inspector.

---

## Quick Start

### Method 1: Launch via `storybook.py` (Recommended)

You can launch the viewer directly from the CLI root:

```bash
# From common/storybook-craft
python storybook.py view
```

Options:
- `--port 5173`: Specify a custom port (default: 5173)
- `--no-open`: Do not automatically open default web browser
- `--output-dir outputs`: Custom outputs directory

### Method 2: Launch via Python Server

```bash
cd viewer
python server.py
```

### Method 3: Run with Vite Dev Server (Hot-Reloading)

```bash
cd viewer
npm install
npm run dev
```

Visit [http://localhost:5173](http://localhost:5173) in your browser.

---

## Build for Production

To produce an optimized static production build in `viewer/dist/`:

```bash
cd viewer
npm run build
```

The Python server (`server.py` and `python storybook.py view`) will automatically serve the built static bundle from `dist/`.
