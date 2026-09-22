---
name: storybook-craft
description: Processes Markdown narratives and automates visual media production for illustrated storybooks and stories via the storybook CLI. Use when asked to format, analyze, or enrich storybook Markdown files, automatically insert image and video placeholders between paragraphs, generate context-aware AI illustration prompts, extract visual metadata, or batch-generate storybook media assets.
metadata:
  author: Frame & Fable
  keywords:
    - storybook-craft
    - storybook
    - markdown-processing
    - illustrated-book
    - visual-storytelling
    - prompt-engineering
    - media-pipeline
---

# Storybook Craft (`storybook-craft` / `storybook`)

`storybook-craft` is a precision Markdown processor and visual storytelling engine. It analyzes narrative text, computes language-aware reading units (handling Chinese characters and English words equally), inserts structured visual placeholders without breaking paragraphs, synthesizes context-aware GenAI prompts, and automates asset generation.

---

## 1. Quick Command Overview

When installed system-wide, the CLI is accessible anywhere via `storybook` or `storybook-craft`:

```bash
# Global CLI command (in PATH):
storybook <COMMAND> [OPTIONS]
# or
storybook-craft <COMMAND> [OPTIONS]

# System-wide venv fallback:
~/.local/share/frame-and-fable/venvs/storybook-craft/bin/python \
  /Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/common/storybook-craft/storybook.py <COMMAND> [OPTIONS]
```

### Environment Setup
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

---

## 2. Production Workflows

### A. End-to-End Media Pipeline (`storybook media <file.md>`)

Executes the entire lifecycle (**Tag $\rightarrow$ Prompt $\rightarrow$ Generate**) in a single automated pass:
```bash
# Tag narrative, generate context prompts, create AI assets, and update Markdown:
storybook media my_story.md

# With custom reading unit gap between illustrations:
storybook media my_story.md -g 250
```

---

### B. Modular Production Stages

#### 1. Insert Media Tags (`storybook media tag <file.md>`)
Inserts structured image placeholders between paragraphs at measured intervals (default: 200 reading units) and video placeholders under `# Chapter Title` headers:
```bash
# Tag file cleanly (never splits sentences or paragraphs):
storybook media tag my_story.md -g 300

# Include opening image before the first paragraph:
storybook media tag my_story.md --first-insert
```

#### 2. Synthesize Contextual Prompts (`storybook media prompt <file.md>`)
Extracts surrounding story context (primary scene following the tag + background context preceding the tag) to write rich visual prompts:
```bash
storybook media prompt my_story.md
```

#### 3. Batch Generate Assets (`storybook media generate <file.md>`)
Generates images (`gemini-3.1-flash-image`) and videos (`veo-3.1-generate-preview`) via Google GenAI into `./outputs/` and updates the Markdown with relative links:
```bash
storybook media generate my_story.md
```

#### 4. Story Metrics & Stats (`storybook media stats <file.md>`)
Inspect reading unit distribution, word/character counts, and media placeholder density:
```bash
storybook media stats my_story.md
```

#### 5. Structured Data Export & Tag Cleansing
```bash
# Export all tags and visual prompts as JSON:
storybook media extract my_story.md

# Strip all storybook comment tags to restore clean plain text:
storybook media clean my_story.md
```

---

### C. Character & Style Reference Management

Maintain visual consistency across chapters and illustration sets:
```bash
# Scaffold workspace and extract character/style metadata without image generation:
storybook assets my_story.md

# Scaffold workspace and generate AI reference portraits & style moodboards:
storybook assets my_story.md -g

# Sync character assets:
storybook char-ref my_story.md

# Sync style assets:
storybook style-ref my_story.md
```

---

### D. Scaffold New Story Content (`storybook create`)

Draft new story arcs or chapter frameworks:
```bash
storybook create "A young apprentice clockmaker in 19th-century Prague discovers an automaton with a mechanical soul"
```

---

## 3. Tag Format Reference

`storybook-craft` uses non-destructive HTML comment markers:
```markdown
<!-- storybook:image prompt="A golden mechanical owl perched on a mahogany desk surrounded by brass gears" -->
![Illustration](./outputs/owl_illustration.png)

<!-- storybook:video prompt="Cinematic camera pan across the clockmaker's dimly lit workshop at midnight" -->
<video src="./outputs/workshop_intro.mp4" controls></video>
```

---

## 4. Agent Best Practices

1. **Stepwise vs One-Shot**: For rapid asset generation, `storybook media <file.md>` does everything. For collaborative workflows where the user wants to review or edit the illustration prompts before generating images, run `storybook media tag` $\rightarrow$ `storybook media prompt`, allow review, and then run `storybook media generate`.
2. **Reading Unit Rule**: 1 Chinese character = 1 unit; 1 English word = 1 unit. Adjust `-g` (e.g. `-g 150` for picture books, `-g 400` for longer novels).
