# storybook-craft

A powerful, precision Markdown processor and visual media pipeline for storybooks and illustrated narratives in **Frame & Fable**.

`storybook` analyzes narrative text, computes language-aware reading units (Chinese characters & equivalent English words), inserts structured visual media tags (`image` and `video`), generates context-aware AI prompts, and automates asset generation.

---

## Setup & Virtual Environment

`storybook-craft` uses an isolated virtual environment (`.venv`) with the Google GenAI SDK:

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Set your Gemini API Key for AI media generation
export GEMINI_API_KEY="your-gemini-api-key"
```

---

## Command Overview

The CLI provides clean, modular commands for every phase of storybook production:

| Command | Description |
|---|---|
| `python storybook.py media <story.md>` | **End-to-End Pipeline**: Runs **tag -> prompt -> generate** in one seamless flow. |
| `python storybook.py media tag <story.md>` | **Tag Only**: Inserts image tags (every N chars) and video tags (`# Title`). |
| `python storybook.py media prompt <story.md>` | **Prompt Only**: Generates/updates context-aware prompts for media tags. |
| `python storybook.py media generate <story.md>` | **Generate Only**: Generates image and video assets via Google GenAI and updates Markdown. |
| `python storybook.py media stats <story.md>` | **Stats**: Displays character counts, paragraph counts, and media tags. |
| `python storybook.py media extract <story.md>` | **Extract**: Outputs all extracted media tags in structured JSON format. |
| `python storybook.py media clean <story.md>` | **Clean**: Strips all storybook media comment tags from the file. |
| `python storybook.py create "<prompt>"` | **Create**: Scaffolds story content and chapter drafts from an idea or prompt. |
| `python storybook.py test` | **Test**: Runs the embedded 16-test unit test suite. |

---

## Key Features

- **End-to-End Visual Pipeline (`media <file>`)**:
  - Automatically tags the Markdown with image placeholders every N characters (default: 200 units) and video placeholders under chapter `# Title` headings.
  - Automatically analyzes surrounding narrative text to write context-aware visual prompts.
  - Automatically invokes Google GenAI (`gemini-3.1-flash-image`, Imagen 3, or Veo) to generate assets into `./outputs/` and updates the Markdown with relative asset paths.

- **Paragraph-Aligned Image Spacing (`media tag -g <gap>`)**:
  - Automatically measures reading units (1 CJK character = 1 unit; 1 English word = 1 unit).
  - **Never splits a paragraph or sentence**: tags always land cleanly between paragraphs.
  - First paragraph opening image support (`--first-insert` / `--no-first-insert`).

- **Context-Aware Prompt Generation (`media prompt`)**:
  - Priority-based narrative context extraction:
    - **Under heading / section start**: Paragraph after tag is 1st priority.
    - **In the middle of a section**: Paragraph after tag is primary scene; preceding paragraph is background context.
    - **End of section**: Preceding paragraph is 1st priority.
  - Optional AI prompt enhancement with `--ai` (uses Gemini LLM for cinematic prompt detailing).

- **Automated Media Generation (`media generate`)**:
  - Generates images via Gemini 3 / Nano Banana Image (`gemini-3.1-flash-image`) or Imagen 3.
  - Submits video operations via Google Veo (`veo-2.0-generate-001`).
  - Supports `--dry-run` to preview all pending prompts and output asset filenames without making API calls.
  - Updates Markdown tags with `"asset": "outputs/img_001.png"` and `"status": "generated"`.

---

## Tag Format Specification

### 1. Image Tag (`json-comment` default)
```markdown
<!-- storybook-media: {"type": "image", "id": "img_001", "index": 1, "section": "Chapter 1", "context_hint": "Snippet of surrounding narrative...", "prompt": "【Chapter 1】主要画面：...（前情背景：...）", "asset": "outputs/img_001.png", "status": "generated"} -->
```

### 2. Video Tag (`json-comment` default)
```markdown
<!-- storybook-media: {"type": "video", "id": "vid_001", "index": 1, "title": "Chapter 1", "section": "Chapter 1", "prompt": "【Chapter 1】开篇视频画面：...", "asset": "outputs/vid_001.mp4", "status": "generated"} -->
```

---

## Usage Examples

### 1. Full End-to-End Media Pipeline
```bash
# Tag story, generate context prompts, and preview generation:
python storybook.py media examples/forest_adventure_zh.md -o story_crafted.md --dry-run

# Run full pipeline with live image generation:
python storybook.py media examples/forest_adventure_zh.md -o story_crafted.md
```

### 2. Step-by-Step Media Workflow
```bash
# Step A: Insert media tags into story
python storybook.py media tag story.md -g 150 -o story_tagged.md

# Step B: Generate & enrich prompts from narrative context
python storybook.py media prompt story_tagged.md -o story_prompted.md

# Step C: Generate images and videos with custom art style
python storybook.py media generate story_prompted.md \
  --style-prompt "watercolor picture book illustration, soft morning light" \
  --style-image "reference_art.png" \
  --output-dir outputs -w
```

### 3. In-Place Update & Cleaning
```bash
# Update file in place with end-to-end styling
python storybook.py media story.md --style-prompt "pixar 3D animation style" -w

# Strip tags to restore original clean markdown
python storybook.py media clean story.md -o story_clean.md
```

### 4. Extract Tags as JSON for Downstream Scripts
```bash
python storybook.py media extract story_crafted.md -o tags.json
```

### 5. View Story & Media Statistics
```bash
python storybook.py media stats story_crafted.md
```

### 6. Create Story Scaffold from Prompt
```bash
python storybook.py create "A young wizard exploring a hidden crystal cave" -o wizard_story.md
```

### 7. Run Built-in Unit Tests
```bash
python storybook.py test -v
```
