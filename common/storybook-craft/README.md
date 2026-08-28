# storybook-craft

A powerful, precision Markdown processor for storybooks and illustrated narratives in **Frame & Fable**.

`storybook-craft` analyzes narrative text, computes language-aware reading units (Chinese characters & equivalent English words), and automatically inserts structured visual media tags (`image` and `video`) with exact paragraph alignment and heading triggers.

---

## Key Features

- **Media Type Support (`-t` / `--type`)**:
  - `image`: Inserts image placeholder tags spaced evenly by character count.
  - `video`: Inserts video placeholder tags directly beneath `# Title` headings.
  - `all` / `both` (default): Inserts both image and video placeholder tags.

- **Paragraph-Aligned Image Insertion (`-g` / `--gap`)**:
  - Automatically calculates narrative unit intervals (default: **200 Chinese characters** or equivalent English words).
  - **Never splits a paragraph or sentence**: Tags are always cleanly placed between complete paragraphs.
  - Interval / gap is fully customizable (e.g. `-g 150` or `-g 300`).

- **First Insert Support (`--first-insert` / `--no-first-insert`)**:
  - By default, automatically guarantees an opening scene image for the first paragraph before subsequent interval counting.
  - Supports positioning options: `after-first-paragraph` (default) or `at-story-start`.

- **Heading 1 (`# Title`) Video Trigger**:
  - Automatically skips the document title (the first `# Title` in the file).
  - Automatically places a structured video placeholder tag under subsequent chapter headings (`# Heading`).

- **Context-Aware Prompt Generation (`--generate-prompts`)**:
  - Automatically crafts rich visual generation prompts from the narrative surrounding each tag:
    - **Under heading / start of section**: Paragraph after tag is 1st priority.
    - **In the middle of a section**: Paragraph after tag is 1st priority (primary scene); paragraph before tag is secondary priority (background context).
    - **End of section**: Paragraph before tag is 1st priority.

- **Multi-Language Counting Engine**:
  - Accurately counts CJK ideographs & full-width typography (1 character = 1 unit).
  - Accurately tokenizes and counts English words (1 word = 1 unit).
  - Automatically strips Markdown formatting, code fences, inline syntax, and comments so only story content is measured.

- **Structured, Standardized Tag Format**:
  - Clean HTML comment containing JSON metadata (`<!-- storybook-media: {...} -->`).
  - Completely invisible in rendered Markdown previews (GitHub, VS Code, Obsidian, Typora).
  - Machine-readable by downstream AI generation pipelines (e.g. `gemini-image.py` or video generators).
  - Also supports alternative formats: `kv-comment`, `block-comment`, and `visible` callouts.

- **Downstream Pipeline Utilities**:
  - `--extract-tags`: Extract all media tags into structured JSON.
  - `--stats`: Print character count, word count, paragraphs, and tag summary.
  - `--clean`: Strip existing tags to restore pristine Markdown.
  - `-w` / `--in-place`: Update markdown files in place.

---

## Tag Format Specification

### 1. Image Tag (`json-comment` default)
```markdown
<!-- storybook-media: {"type": "image", "id": "img_001", "index": 1, "section": "Chapter 1", "context_hint": "Snippet of surrounding narrative...", "prompt": "【Chapter 1】主要画面：...（前情背景：...）", "asset": "", "status": "pending"} -->
```

### 2. Video Tag (`json-comment` default)
```markdown
<!-- storybook-media: {"type": "video", "id": "vid_001", "index": 1, "title": "Chapter 1: The Beginning", "section": "Chapter 1: The Beginning", "prompt": "【Chapter 1: The Beginning】开篇视频画面：...", "asset": "", "status": "pending"} -->
```

### Tag Fields

| Field | Type | Description |
|---|---|---|
| `type` | `string` | Media type: `"image"` or `"video"` |
| `id` | `string` | Unique identifier (e.g. `img_001`, `vid_001`) |
| `index` | `integer` | 1-based sequential media index |
| `section` / `title` | `string` | Title of the enclosing `# Title` section |
| `context_hint` | `string` | Narrative snippet from the accompanying paragraph |
| `prompt` | `string` | Auto-generated or custom prompt for AI generation |
| `asset` | `string` | Placeholder for generated file path (e.g. `outputs/img_001.png`) |
| `status` | `string` | Lifecycle status: `"pending"`, `"generated"`, etc. |

---

## Usage Examples

### 1. Standard Tagging with Context-Aware Prompt Generation
```bash
python storybook_craft.py story.md --generate-prompts -o story_crafted.md
```

### 2. Custom Image Gap (e.g., 150 Characters)
```bash
python storybook_craft.py story.md -t image -g 150 -o story_images.md
```

### 3. Video Tags Only (under chapter `# Title` headings)
```bash
python storybook_craft.py story.md -t video -o story_videos.md
```

### 4. In-Place File Update
```bash
python storybook_craft.py story.md --generate-prompts -w
```

### 5. Extract Media Tags as JSON (for AI Generation Scripts)
```bash
python storybook_craft.py story_crafted.md --extract-tags
```

**Example JSON Output:**
```json
{
  "count": 2,
  "tags": [
    {
      "type": "video",
      "id": "vid_001",
      "index": 1,
      "title": "魔法森林的秘密",
      "section": "魔法森林的秘密",
      "prompt": "【魔法森林的秘密】开篇视频画面：很久很久以前，在群山环抱的一片古老森林里...",
      "asset": "",
      "status": "pending"
    },
    {
      "type": "image",
      "id": "img_001",
      "index": 1,
      "section": "魔法森林的秘密",
      "context_hint": "清晨的第一缕阳光穿透薄雾，将金色的光斑洒在潮湿的苔藓上...",
      "prompt": "【魔法森林的秘密】主要画面：清晨的第一缕阳光穿透薄雾...（前情背景：很久很久以前，在群山环抱的一片古老森林里...）",
      "asset": "",
      "status": "pending"
    }
  ]
}
```

### 6. View Story & Media Statistics
```bash
python storybook_craft.py story_crafted.md --stats
```

### 7. Clean Existing Markdown Media (-c) & Tag Story
```bash
python storybook_craft.py story.md -c --generate-prompts -o story_crafted.md
```

### 8. Clean / Remove All Storybook Tags
```bash
python storybook_craft.py story_crafted.md --clean -o story_clean.md
```

---

## Command Line Reference

| Flag | Short | Description | Default |
|---|---|---|---|
| `positional_file` | | Path to input story markdown file (or `-` for stdin) | `None` (stdin) |
| `-i`, `--input` | `-i` | Explicit input markdown file path | `None` |
| `-o`, `--output` | `-o` | Target output file path | `stdout` |
| `-w`, `--in-place` | `-w` | Overwrite input file in place | `False` |
| `-t`, `--type` | `-t` | Media type: `image`, `video`, `all` | `all` |
| `-c`, `--clean-media` | `-c` | Strip existing Markdown/HTML media (`image`, `video`, `all`) | `None` (`all` when passed) |
| `--clean-media-only` | | Only strip existing Markdown/HTML media without inserting tags | `False` |
| `-g`, `--gap`, `--image-gap` | `-g` | Interval in CJK chars / English words between images | `200` |
| `--first-insert` / `--no-first-insert` | | Guarantee opening scene image on first paragraph | `True` |
| `--first-insert-pos` | | First image position (`after-first-paragraph`, `at-story-start`) | `after-first-paragraph` |
| `--reset-on-h1` | | Reset image character accumulation at each `# Title` | `False` |
| `--generate-prompts` | | Auto-generate context-aware visual prompts for media tags | `False` |
| `--img-prefix` | | Prefix for image IDs | `img_` |
| `--vid-prefix` | | Prefix for video IDs | `vid_` |
| `--id-digits` | | Zero padding width for IDs | `3` (`001`) |
| `--format` | | Tag format (`json-comment`, `kv-comment`, `block-comment`, `visible`) | `json-comment` |
| `--extract-tags` | | Output all extracted tags in JSON format | `False` |
| `--stats` | | Display character, word, heading, and media tag metrics | `False` |
| `--clean`, `--remove-tags` | | Remove all storybook media tags from markdown | `False` |
| `-v`, `--verbose` | `-v` | Output detailed progress | `False` |

---

## Downstream Pipeline Integration

Downstream content generation tools (like `common/image-craft/gemini-image.py`) can easily automate media creation using `storybook-craft`:

```python
import json
import subprocess
from storybook_craft import extract_media_tags

# 1. Read crafted storybook markdown
with open("story_crafted.md", "r", encoding="utf-8") as f:
    content = f.read()

# 2. Extract media targets
tags = extract_media_tags(content)

# 3. Process each pending image
for tag in tags:
    if tag["type"] == "image":
        prompt = f"Storybook illustration for '{tag['section']}': {tag['context_hint']}"
        output_file = f"outputs/{tag['id']}.png"
        # Call gemini-image CLI or API:
        # subprocess.run(["python", "../image-craft/gemini-image.py", prompt, "-r", "16:9", "-o", output_file])
```
