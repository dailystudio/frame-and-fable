#!/usr/bin/env python3
"""
storybook_craft.py: Markdown processor for storybooks and illustrated narratives.

Inserts structured visual media tags (images and videos) into story Markdown:
- Image tags: Inserted every N Chinese characters (or equivalent English words),
  aligned cleanly to paragraph boundaries.
- Video tags: Inserted under every Level 1 Markdown heading (# Title).
- First insert: Automatically supports placing an opening image for the first section.
- Tag format: Standardized, parseable JSON/HTML comments preserving clean Markdown rendering.
"""

import sys
import os
import re
import json
import argparse
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union


# ==============================================================================
# Constants & Defaults
# ==============================================================================

DEFAULT_IMAGE_GAP = 200
DEFAULT_IMG_PREFIX = "img_"
DEFAULT_VID_PREFIX = "vid_"
DEFAULT_ID_DIGITS = 3

SUPPORTED_TYPES = ["image", "video", "all", "both"]
SUPPORTED_FORMATS = ["json-comment", "kv-comment", "block-comment", "visible"]

# Regex for matching existing storybook tags in various formats
TAG_JSON_REGEX = re.compile(r'<!--\s*storybook-media:\s*(\{.*?\})\s*-->', re.DOTALL)
TAG_KV_REGEX = re.compile(r'<!--\s*storybook-media\s+(.*?)\s*-->')
TAG_BLOCK_REGEX = re.compile(r'<!--\s*STORYBOOK:MEDIA\s*\n(.*?)\n\s*-->', re.DOTALL)
TAG_VISIBLE_REGEX = re.compile(r'>\s*🎨\s*\*\*\[Media:\s*([^\]]+)\]\*\*')


# ==============================================================================
# Text & Word Counting Utilities
# ==============================================================================

def strip_markdown_decorations(text: str) -> str:
    """
    Remove markdown formatting markers (headers, bold, italic, links, code blocks, tags)
    while preserving narrative text words.
    """
    # 1. Remove HTML comments (including existing storybook tags)
    s = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # 2. Remove visible storybook markers if present
    s = TAG_VISIBLE_REGEX.sub('', s)
    # 3. Remove fenced code blocks (multi-line code)
    s = re.sub(r'```.*?```', '', s, flags=re.DOTALL)
    s = re.sub(r'~~~.*?~~~', '', s, flags=re.DOTALL)
    # 4. Unwrap inline code: `code` -> code
    s = re.sub(r'`([^`]+)`', r'\1', s)
    # 5. Remove standalone images: ![alt](url) -> ""
    s = re.sub(r'!\[.*?\]\(.*?\)', '', s)
    # 6. Unwrap links: [text](url) -> text
    s = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', s)
    # 7. Remove markdown headers: # ## ###
    s = re.sub(r'^\s*#+\s*', '', s, flags=re.MULTILINE)
    # 8. Remove blockquote markers: >
    s = re.sub(r'^\s*>\s*', '', s, flags=re.MULTILINE)
    # 9. Remove list markers: - * + 1.
    s = re.sub(r'^\s*[-*+]\s+', '', s, flags=re.MULTILINE)
    s = re.sub(r'^\s*\d+\.\s+', '', s, flags=re.MULTILINE)
    # 10. Remove bold / italic markers: ** * __ _ ~~
    s = re.sub(r'(\*\*|__|\*|_|~~)', '', s)
    return s.strip()


def count_story_units(
    text: str,
    cjk_weight: float = 1.0,
    word_weight: float = 1.0
) -> Tuple[int, int, int]:
    """
    Count narrative units in text.
    Returns:
        (total_units, cjk_count, english_word_count)
    - Chinese/CJK characters & full-width symbols count as 1.0 * cjk_weight
    - English/Latin words count as 1.0 * word_weight
    """
    clean_text = strip_markdown_decorations(text)
    if not clean_text:
        return 0, 0, 0

    cjk_count = 0
    non_cjk_chars: List[str] = []

    for ch in clean_text:
        w = unicodedata.east_asian_width(ch)
        # Wide ('W') and Fullwidth ('F') are CJK ideographs, kana, hangul, full-width punctuation
        if w in ('W', 'F') and not ch.isspace():
            cjk_count += 1
        else:
            non_cjk_chars.append(ch)

    non_cjk_str = "".join(non_cjk_chars)
    words = re.findall(r'\b[a-zA-Z0-9]+(?:[\'-][a-zA-Z0-9]+)*\b', non_cjk_str)
    word_count = len(words)

    total_units = int(round(cjk_count * cjk_weight + word_count * word_weight))
    return total_units, cjk_count, word_count


def build_prompt(
    tag_type: str,
    section_title: str,
    before_text: str = "",
    after_text: str = ""
) -> str:
    """
    Build a context-aware prompt based on narrative text surrounding the media tag.

    Priority Rules:
    1. If tag is just under #title (start of section): only text after it exists -> text after is 1st priority.
    2. If tag is in the middle of a section: text after it is 1st priority, text before is secondary.
    3. If tag is after the last paragraph of a section: only text before it exists -> text before is 1st priority.
    """
    clean_before = strip_markdown_decorations(before_text).replace("\n", " ").strip()
    clean_after = strip_markdown_decorations(after_text).replace("\n", " ").strip()
    clean_section = strip_markdown_decorations(section_title).replace("\n", " ").strip()

    # Determine primary vs secondary
    if clean_after and not clean_before:
        # Just under #title / start of section: only has paragraph after it (1st priority)
        primary = clean_after
        secondary = ""
    elif clean_before and not clean_after:
        # Last paragraph of the section: only text before it (1st priority)
        primary = clean_before
        secondary = ""
    elif clean_after and clean_before:
        # In the middle: text after is 1st priority, text before is secondary
        primary = clean_after
        secondary = clean_before
    else:
        primary = clean_section
        secondary = ""

    # Check if narrative is predominantly CJK or English
    units, cjk_count, word_count = count_story_units(primary + " " + secondary)
    is_cjk = cjk_count >= word_count

    if is_cjk:
        if tag_type == "video":
            prompt = f"【{clean_section}】开篇视频画面：{primary}"
            if secondary:
                prompt += f"（背景脉络：{secondary}）"
        else:
            prompt = f"【{clean_section}】主要画面：{primary}"
            if secondary:
                prompt += f"（前情背景：{secondary}）"
    else:
        if tag_type == "video":
            prompt = f"Video scene for '{clean_section}': {primary}"
            if secondary:
                prompt += f" (Context: {secondary})"
        else:
            prompt = f"[{clean_section}] Main scene: {primary}"
            if secondary:
                prompt += f" (Background context: {secondary})"

    return prompt


# ==============================================================================
# Tag Generation & Formatting
# ==============================================================================

def format_tag(
    tag_data: Dict[str, Any],
    tag_format: str = "json-comment"
) -> str:
    """
    Format media metadata dictionary into the specified tag format string.
    """
    if tag_format == "json-comment":
        # Standard format: Single line HTML comment with compact JSON
        json_str = json.dumps(tag_data, ensure_ascii=False)
        return f"<!-- storybook-media: {json_str} -->"

    elif tag_format == "kv-comment":
        # Key-Value HTML comment: <!-- storybook-media type="image" id="img_001" ... -->
        kv_pairs = []
        for k, v in tag_data.items():
            if isinstance(v, (dict, list)):
                val_str = json.dumps(v, ensure_ascii=False).replace('"', '&quot;')
            else:
                val_str = str(v).replace('"', '&quot;')
            kv_pairs.append(f'{k}="{val_str}"')
        return f"<!-- storybook-media {' '.join(kv_pairs)} -->"

    elif tag_format == "block-comment":
        # Multi-line YAML/KV block comment
        lines = ["<!-- STORYBOOK:MEDIA"]
        for k, v in tag_data.items():
            if isinstance(v, (dict, list)):
                lines.append(f"  {k}: {json.dumps(v, ensure_ascii=False)}")
            else:
                lines.append(f"  {k}: {v}")
        lines.append("-->")
        return "\n".join(lines)

    elif tag_format == "visible":
        # Markdown visible callout box
        media_type = tag_data.get("type", "media")
        media_id = tag_data.get("id", "")
        sec = tag_data.get("section") or tag_data.get("title") or ""
        sec_str = f" | section: {sec}" if sec else ""
        return f"> 🎨 **[Media: {media_type} | id: {media_id}{sec_str}]**"

    else:
        # Fallback to json-comment
        json_str = json.dumps(tag_data, ensure_ascii=False)
        return f"<!-- storybook-media: {json_str} -->"


# ==============================================================================
# Markdown Parsing & Tag Insertion
# ==============================================================================

class MarkdownBlock:
    """Represents a discrete Markdown structural element."""
    TYPE_FRONTMATTER = "frontmatter"
    TYPE_H1 = "h1"
    TYPE_HEADING = "heading"
    TYPE_PARAGRAPH = "paragraph"
    TYPE_CODE_BLOCK = "code_block"
    TYPE_THEMATIC_BREAK = "thematic_break"
    TYPE_EXISTING_TAG = "existing_tag"
    TYPE_BLANK = "blank"

    def __init__(self, block_type: str, raw_text: str, content: str = ""):
        self.block_type = block_type
        self.raw_text = raw_text
        self.content = content or raw_text

    def __repr__(self):
        return f"<MarkdownBlock type={self.block_type} len={len(self.raw_text)}>"


def split_markdown_into_blocks(text: str) -> List[MarkdownBlock]:
    """
    Parse markdown into high-level blocks (frontmatter, headings, paragraphs,
    code blocks, thematic breaks, existing tags).
    """
    lines = text.splitlines(keepends=True)
    blocks: List[MarkdownBlock] = []
    i = 0
    n = len(lines)

    # 1. Check for YAML Frontmatter at the beginning
    if n > 0 and lines[0].strip() == "---":
        fm_lines = [lines[0]]
        i = 1
        fm_closed = False
        while i < n:
            fm_lines.append(lines[i])
            if lines[i].strip() == "---":
                fm_closed = True
                i += 1
                break
            i += 1
        if fm_closed:
            fm_text = "".join(fm_lines)
            blocks.append(MarkdownBlock(MarkdownBlock.TYPE_FRONTMATTER, fm_text))

    # 2. Iterate through remaining lines
    current_para_lines: List[str] = []

    def flush_paragraph():
        if current_para_lines:
            para_text = "".join(current_para_lines)
            stripped = para_text.strip()
            # Check if this paragraph is solely an existing storybook tag
            if (TAG_JSON_REGEX.match(stripped) or 
                TAG_KV_REGEX.match(stripped) or 
                TAG_BLOCK_REGEX.match(stripped) or 
                TAG_VISIBLE_REGEX.match(stripped)):
                blocks.append(MarkdownBlock(MarkdownBlock.TYPE_EXISTING_TAG, para_text, stripped))
            else:
                blocks.append(MarkdownBlock(MarkdownBlock.TYPE_PARAGRAPH, para_text, stripped))
            current_para_lines.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Check for Fenced Code Block: ``` or ~~~
        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush_paragraph()
            fence = stripped[:3]
            code_lines = [line]
            i += 1
            while i < n:
                code_lines.append(lines[i])
                if lines[i].strip().startswith(fence):
                    i += 1
                    break
                i += 1
            blocks.append(MarkdownBlock(MarkdownBlock.TYPE_CODE_BLOCK, "".join(code_lines)))
            continue

        # Check for Blank lines
        if not stripped:
            if current_para_lines:
                flush_paragraph()
            blocks.append(MarkdownBlock(MarkdownBlock.TYPE_BLANK, line))
            i += 1
            continue

        # Check for Existing Storybook Tag
        if (TAG_JSON_REGEX.match(stripped) or 
            TAG_KV_REGEX.match(stripped) or 
            TAG_BLOCK_REGEX.match(stripped) or 
            TAG_VISIBLE_REGEX.match(stripped)):
            flush_paragraph()
            blocks.append(MarkdownBlock(MarkdownBlock.TYPE_EXISTING_TAG, line, stripped))
            i += 1
            continue

        # Check for Headings
        # ATX Headings: # Title
        if stripped.startswith("#"):
            flush_paragraph()
            m = re.match(r'^(#{1,6})\s+(.*)$', stripped)
            if m:
                level = len(m.group(1))
                h_text = m.group(2).strip()
                b_type = MarkdownBlock.TYPE_H1 if level == 1 else MarkdownBlock.TYPE_HEADING
                blocks.append(MarkdownBlock(b_type, line, h_text))
                i += 1
                continue

        # Check for Thematic Break (---, ***, ___ on a single line)
        if re.match(r'^(\*{3,}|-{3,}|_{3,})$', stripped):
            flush_paragraph()
            blocks.append(MarkdownBlock(MarkdownBlock.TYPE_THEMATIC_BREAK, line))
            i += 1
            continue

        # Regular line belonging to a paragraph
        current_para_lines.append(line)
        i += 1

    flush_paragraph()
    return blocks


def insert_media_tags(
    markdown_text: str,
    media_types: List[str],
    image_gap: int = DEFAULT_IMAGE_GAP,
    first_insert: bool = True,
    first_insert_pos: str = "after-first-paragraph",
    reset_on_h1: bool = False,
    generate_prompts: bool = False,
    clean_media: Optional[Union[str, List[str]]] = None,
    img_prefix: str = DEFAULT_IMG_PREFIX,
    vid_prefix: str = DEFAULT_VID_PREFIX,
    id_digits: int = DEFAULT_ID_DIGITS,
    tag_format: str = "json-comment",
    remove_existing: bool = True
) -> str:
    """
    Inserts image and video tags into the given markdown text.

    Args:
        markdown_text: Original markdown source string.
        media_types: Types of media to insert (['image'], ['video'], or ['image', 'video']).
        image_gap: Number of Chinese chars (or equivalent English words) between image tags.
        first_insert: Whether to guarantee a first image insert for the opening.
        first_insert_pos: 'after-first-paragraph' or 'at-story-start'.
        reset_on_h1: Reset accumulated character counter on each Level 1 heading.
        generate_prompts: Whether to auto-generate context-aware visual prompts for tags.
        clean_media: Remove existing Markdown/HTML media (images/videos) before inserting tags.
        img_prefix: Prefix for image IDs (e.g. 'img_').
        vid_prefix: Prefix for video IDs (e.g. 'vid_').
        id_digits: Zero-padding width for IDs (e.g. 3 -> '001').
        tag_format: 'json-comment', 'kv-comment', 'block-comment', or 'visible'.
        remove_existing: If True, strips existing storybook tags before inserting new ones.
    """
    # Normalize media types
    types_set = set()
    for t in media_types:
        t_low = t.strip().lower()
        if t_low in ["all", "both"]:
            types_set.add("image")
            types_set.add("video")
        elif t_low in ["image", "img", "images"]:
            types_set.add("image")
        elif t_low in ["video", "vid", "videos"]:
            types_set.add("video")

    # If requested, clean existing markdown media (images/videos) first
    if clean_media:
        markdown_text = remove_markdown_media(markdown_text, media_types=clean_media)

    # If requested, clean existing storybook tags first
    if remove_existing:
        markdown_text = remove_media_tags(markdown_text)

    blocks = split_markdown_into_blocks(markdown_text)

    # Group blocks into structural sections based on headings
    class SectionData:
        def __init__(self, heading: Optional[MarkdownBlock]):
            self.heading = heading
            self.blocks: List[MarkdownBlock] = []
            self.narrative_paras: List[MarkdownBlock] = []

    sections: List[SectionData] = []
    current_sec = SectionData(None)
    sections.append(current_sec)

    for b in blocks:
        if b.block_type in (MarkdownBlock.TYPE_H1, MarkdownBlock.TYPE_HEADING):
            current_sec = SectionData(b)
            sections.append(current_sec)
        else:
            current_sec.blocks.append(b)
            if b.block_type == MarkdownBlock.TYPE_PARAGRAPH:
                u, _, _ = count_story_units(b.raw_text)
                if u > 0:
                    current_sec.narrative_paras.append(b)

    output_lines: List[str] = []
    current_h1 = ""
    current_section = ""
    image_index = 1
    video_index = 1
    h1_count = 0
    accumulated_units = 0
    first_image_inserted = False

    def make_image_tag(idx: int, section: str, prompt: str = "", context_hint: str = "") -> str:
        tag_id = f"{img_prefix}{idx:0{id_digits}d}"
        tag_data = {
            "type": "image",
            "id": tag_id,
            "index": idx,
            "section": section,
            "context_hint": context_hint[:60].replace("\n", " ").strip() if context_hint else "",
            "prompt": prompt,
            "asset": "",
            "status": "pending"
        }
        return format_tag(tag_data, tag_format)

    def make_video_tag(idx: int, title: str, prompt: str = "", context_hint: str = "") -> str:
        tag_id = f"{vid_prefix}{idx:0{id_digits}d}"
        tag_data = {
            "type": "video",
            "id": tag_id,
            "index": idx,
            "title": title,
            "section": title,
            "context_hint": context_hint[:60].replace("\n", " ").strip() if context_hint else "",
            "prompt": prompt,
            "asset": "",
            "status": "pending"
        }
        return format_tag(tag_data, tag_format)

    # Process sections
    for sec in sections:
        # 1. Process Section Heading
        if sec.heading:
            h_block = sec.heading
            title_text = h_block.content.strip()
            current_section = title_text

            if h_block.block_type == MarkdownBlock.TYPE_H1:
                h1_count += 1
                current_h1 = title_text
                output_lines.append(h_block.raw_text)

                if reset_on_h1:
                    accumulated_units = 0

                # Video Tag: Always skip the first # Title (overall document title), insert for subsequent chapter titles
                if h1_count > 1 and "video" in types_set:
                    first_para_text = sec.narrative_paras[0].content if sec.narrative_paras else ""
                    prompt_str = build_prompt("video", title_text, before_text="", after_text=first_para_text) if generate_prompts else ""
                    vid_tag_str = make_video_tag(video_index, title_text, prompt=prompt_str, context_hint=first_para_text)
                    video_index += 1
                    if not h_block.raw_text.endswith("\n"):
                        output_lines.append("\n")
                    output_lines.append(f"{vid_tag_str}\n\n")

                # Story-start first image (if configured for at-story-start)
                if "image" in types_set and first_insert and not first_image_inserted and first_insert_pos == "at-story-start":
                    first_para_text = sec.narrative_paras[0].content if sec.narrative_paras else ""
                    prompt_str = build_prompt("image", current_section, before_text="", after_text=first_para_text) if generate_prompts else ""
                    img_tag_str = make_image_tag(image_index, current_section, prompt=prompt_str, context_hint=first_para_text)
                    image_index += 1
                    first_image_inserted = True
                    accumulated_units = 0
                    output_lines.append(f"{img_tag_str}\n\n")
            else:
                # Other heading (##, ###)
                output_lines.append(h_block.raw_text)

        # 2. Process Section Blocks (paragraphs, blanks, code blocks, etc.)
        for block in sec.blocks:
            if block.block_type != MarkdownBlock.TYPE_PARAGRAPH:
                output_lines.append(block.raw_text)
                continue

            para_text = block.raw_text
            output_lines.append(para_text)

            units, _, _ = count_story_units(para_text)
            if units == 0:
                continue

            if "image" in types_set:
                # Find position of this paragraph in the section
                k = sec.narrative_paras.index(block) if block in sec.narrative_paras else 0
                is_last_in_section = (k == len(sec.narrative_paras) - 1)
                before_text = block.content
                after_text = sec.narrative_paras[k + 1].content if not is_last_in_section else ""

                should_insert = False
                if first_insert and not first_image_inserted and first_insert_pos == "after-first-paragraph":
                    should_insert = True
                    first_image_inserted = True
                    accumulated_units = 0
                else:
                    accumulated_units += units
                    if accumulated_units >= image_gap:
                        should_insert = True
                        accumulated_units = 0

                if should_insert:
                    prompt_str = build_prompt("image", current_section, before_text=before_text, after_text=after_text) if generate_prompts else ""
                    context_hint_str = after_text if after_text else before_text
                    img_tag_str = make_image_tag(image_index, current_section, prompt=prompt_str, context_hint=context_hint_str)
                    image_index += 1

                    if not para_text.endswith("\n\n") and not para_text.endswith("\n"):
                        output_lines.append("\n\n")
                    elif para_text.endswith("\n") and not para_text.endswith("\n\n"):
                        output_lines.append("\n")
                    output_lines.append(f"{img_tag_str}\n\n")

    # Combine and clean up excess trailing blank lines
    result = "".join(output_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip() + "\n"


# ==============================================================================
# Tag Extraction, Removal & Modification
# ==============================================================================

def extract_media_tags(markdown_text: str) -> List[Dict[str, Any]]:
    """
    Extract all storybook media tags from markdown text into structured dicts.
    Supports JSON comments, KV comments, Block comments, and Visible markers.
    """
    tags: List[Dict[str, Any]] = []

    # 1. Search JSON comments: <!-- storybook-media: {...} -->
    for m in TAG_JSON_REGEX.finditer(markdown_text):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict):
                data["_raw_tag"] = m.group(0)
                data["_span"] = m.span()
                tags.append(data)
        except Exception:
            pass

    # 2. Search KV comments: <!-- storybook-media type="image" ... -->
    for m in TAG_KV_REGEX.finditer(markdown_text):
        raw = m.group(0)
        if any(t.get("_raw_tag") == raw for t in tags):
            continue
        content = m.group(1).strip()
        if content.startswith("{"):
            continue
        kv_dict: Dict[str, Any] = {}
        for match in re.finditer(r'(\w+)=["\'](.*?)["\']', content):
            k, v = match.group(1), match.group(2)
            if v.isdigit():
                kv_dict[k] = int(v)
            else:
                kv_dict[k] = v
        if kv_dict:
            kv_dict["_raw_tag"] = raw
            kv_dict["_span"] = m.span()
            tags.append(kv_dict)

    # 3. Search Block comments: <!-- STORYBOOK:MEDIA ... -->
    for m in TAG_BLOCK_REGEX.finditer(markdown_text):
        raw = m.group(0)
        if any(t.get("_raw_tag") == raw for t in tags):
            continue
        lines = m.group(1).splitlines()
        b_dict: Dict[str, Any] = {}
        for l in lines:
            if ":" in l:
                k, v = l.split(":", 1)
                k = k.strip()
                v = v.strip()
                if v.isdigit():
                    b_dict[k] = int(v)
                else:
                    b_dict[k] = v
        if b_dict:
            b_dict["_raw_tag"] = raw
            b_dict["_span"] = m.span()
            tags.append(b_dict)

    # 4. Search Visible markers: > 🎨 **[Media: ...]**
    for m in TAG_VISIBLE_REGEX.finditer(markdown_text):
        raw = m.group(0)
        if any(t.get("_raw_tag") == raw for t in tags):
            continue
        info_str = m.group(1)
        v_dict: Dict[str, Any] = {}
        parts = [p.strip() for p in info_str.split("|")]
        for p in parts:
            if ":" in p:
                k, v = p.split(":", 1)
                v_dict[k.strip().lower()] = v.strip()
        if v_dict:
            v_dict["_raw_tag"] = raw
            v_dict["_span"] = m.span()
            tags.append(v_dict)

    # Sort tags by their appearance in the text
    tags.sort(key=lambda x: x.get("_span", (0, 0))[0])
    return tags


def remove_media_tags(markdown_text: str) -> str:
    """
    Strip all storybook media tags from markdown text, returning clean text.
    """
    text = TAG_JSON_REGEX.sub('', markdown_text)
    text = TAG_KV_REGEX.sub('', text)
    text = TAG_BLOCK_REGEX.sub('', text)
    text = TAG_VISIBLE_REGEX.sub('', text)
    # Clean up double blank lines created by removal
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def remove_markdown_media(
    markdown_text: str,
    media_types: Union[str, List[str]] = "all"
) -> str:
    """
    Remove existing standard Markdown and HTML media elements (images and/or videos)
    from the article, preserving storybook comment tags.

    Args:
        markdown_text: Input markdown text.
        media_types: 'image', 'video', 'all', 'both', or list of types.

    Returns:
        Cleaned markdown text with existing Markdown/HTML media elements removed.
    """
    if isinstance(media_types, str):
        types_list = [media_types]
    else:
        types_list = list(media_types)

    types_set = set()
    for t in types_list:
        if not t:
            continue
        t_low = t.strip().lower()
        if t_low in ["all", "both"]:
            types_set.add("image")
            types_set.add("video")
        elif t_low in ["image", "img", "images"]:
            types_set.add("image")
        elif t_low in ["video", "vid", "videos"]:
            types_set.add("video")

    text = markdown_text

    if "video" in types_set:
        # Remove HTML video elements
        text = re.sub(r'<video\b[^>]*>.*?</video>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<video\b[^>]*\/?>', '', text, flags=re.IGNORECASE)
        # Remove video iframes / embeds
        text = re.sub(r'<iframe\b[^>]*(youtube|vimeo|bilibili|video|player)[^>]*>.*?</iframe>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove linked video thumbnails [![alt](img)](video_url)
        text = re.sub(r'\[!\[.*?\]\([^\)]*\)\]\([^\)]*\)', '', text)

    if "image" in types_set:
        # Remove Markdown inline images: ![alt](url) and ![alt](url "title")
        text = re.sub(r'!\[.*?\]\([^\)]*\)', '', text)
        # Remove Markdown reference images: ![alt][ref]
        text = re.sub(r'!\[.*?\]\[[^\]]*\]', '', text)
        # Remove HTML img tags: <img ... />
        text = re.sub(r'<img\b[^>]*\/?>', '', text, flags=re.IGNORECASE)
        # Remove HTML picture tags: <picture>...</picture>
        text = re.sub(r'<picture\b[^>]*>.*?</picture>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Clean up leftover blank lines and whitespace
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + "\n"


def get_storybook_stats(markdown_text: str) -> Dict[str, Any]:
    """
    Compute storybook metrics:
    - Character counts (CJK, English words, Total units)
    - Heading and paragraph counts
    - Media tags counts (images, videos)
    """
    clean_text = remove_media_tags(markdown_text)
    blocks = split_markdown_into_blocks(clean_text)

    total_units, total_cjk, total_words = count_story_units(clean_text)
    tags = extract_media_tags(markdown_text)

    image_tags = [t for t in tags if t.get("type") == "image"]
    video_tags = [t for t in tags if t.get("type") == "video"]
    h1_count = len([b for b in blocks if b.block_type == MarkdownBlock.TYPE_H1])
    para_count = len([b for b in blocks if b.block_type == MarkdownBlock.TYPE_PARAGRAPH])

    return {
        "cjk_characters": total_cjk,
        "english_words": total_words,
        "total_story_units": total_units,
        "h1_headings": h1_count,
        "paragraphs": para_count,
        "total_media_tags": len(tags),
        "image_tags_count": len(image_tags),
        "video_tags_count": len(video_tags),
        "tags": tags
    }


# ==============================================================================
# CLI Argument Parser & Entry Point
# ==============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        prog="storybook_craft",
        description="Insert and manage structured visual media tags (images & videos) in story Markdown.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
  # 1. Insert both image (every 200 chars) and video tags (# Title) into a story:
  python storybook_craft.py story.md -o story_crafted.md

  # 2. Insert only image tags with a custom 150-character interval:
  python storybook_craft.py story.md -t image -g 150 -o story_images.md

  # 3. Insert only video tags under each Level 1 '# Title':
  python storybook_craft.py story.md -t video -o story_video.md

  # 4. Modify a markdown file in-place:
  python storybook_craft.py story.md -w

  # 5. Extract all media tags as JSON (for downstream AI image/video generation):
  python storybook_craft.py story_crafted.md --extract-tags

  # 6. View detailed story & tag statistics:
  python storybook_craft.py story_crafted.md --stats

  # 7. Strip all tags to restore original clean markdown:
  python storybook_craft.py story_crafted.md --clean -o story_clean.md
"""
    )

    parser.add_argument(
        "positional_file",
        nargs="?",
        default=None,
        help="Input story markdown file path. If omitted or '-', reads from stdin."
    )
    parser.add_argument(
        "-i", "--input",
        dest="input_file",
        help="Input story markdown file path."
    )
    parser.add_argument(
        "-o", "--output",
        help="Output markdown file path. Defaults to stdout."
    )
    parser.add_argument(
        "-w", "--in-place",
        action="store_true",
        help="Overwrite the input file in place with generated tags."
    )
    parser.add_argument(
        "-t", "--type",
        dest="media_types",
        action="append",
        choices=SUPPORTED_TYPES,
        help="Media type(s) to insert: 'image', 'video', 'all' (default: all). Can be specified multiple times."
    )
    parser.add_argument(
        "-g", "--gap", "--image-gap",
        dest="image_gap",
        type=int,
        default=DEFAULT_IMAGE_GAP,
        help=f"Character / word count interval for image insertion, aligned to paragraphs (default: {DEFAULT_IMAGE_GAP})."
    )
    parser.add_argument(
        "--first-insert",
        dest="first_insert",
        action="store_true",
        default=True,
        help="Automatically insert an opening image after the first paragraph (default: True)."
    )
    parser.add_argument(
        "--no-first-insert",
        dest="first_insert",
        action="store_false",
        help="Do not insert a guaranteed first image; wait for the first full character gap."
    )
    parser.add_argument(
        "--first-insert-pos",
        choices=["after-first-paragraph", "at-story-start"],
        default="after-first-paragraph",
        help="Placement location for the opening first image (default: after-first-paragraph)."
    )
    parser.add_argument(
        "--reset-on-h1",
        action="store_true",
        help="Reset accumulated image character counter on each Level 1 heading."
    )
    parser.add_argument(
        "--img-prefix",
        default=DEFAULT_IMG_PREFIX,
        help=f"Prefix for generated image IDs (default: '{DEFAULT_IMG_PREFIX}')."
    )
    parser.add_argument(
        "--vid-prefix",
        default=DEFAULT_VID_PREFIX,
        help=f"Prefix for generated video IDs (default: '{DEFAULT_VID_PREFIX}')."
    )
    parser.add_argument(
        "--id-digits",
        type=int,
        default=DEFAULT_ID_DIGITS,
        help=f"Zero-padding width for media tag IDs (default: {DEFAULT_ID_DIGITS} -> '001')."
    )
    parser.add_argument(
        "--format", "--tag-format",
        dest="tag_format",
        choices=SUPPORTED_FORMATS,
        default="json-comment",
        help="Tag formatting style: 'json-comment' (default), 'kv-comment', 'block-comment', 'visible'."
    )
    parser.add_argument(
        "--generate-prompts", "--generate-prompt",
        dest="generate_prompts",
        action="store_true",
        help="Auto-generate context-aware visual prompts based on narrative text surrounding each tag."
    )
    parser.add_argument(
        "-c", "--clean-media", "--remove-md-media",
        dest="clean_media",
        nargs="?",
        const="all",
        choices=["image", "video", "all", "both"],
        default=None,
        help="Remove existing Markdown/HTML media elements (images and/or videos; default: all) from the article."
    )
    parser.add_argument(
        "--clean-media-only",
        action="store_true",
        help="Only remove existing Markdown/HTML media elements from the article, without inserting new storybook tags."
    )
    parser.add_argument(
        "--extract-tags", "--list-tags",
        action="store_true",
        help="Extract and print all media tags found in the markdown file as JSON."
    )
    parser.add_argument(
        "--clean", "--remove-tags",
        action="store_true",
        help="Strip all storybook media tags from the markdown file."
    )
    parser.add_argument(
        "--stats", "--info",
        action="store_true",
        help="Display story character count, paragraph breakdown, and media tag statistics."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed execution progress."
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Determine input source
    input_path = args.input_file or args.positional_file
    input_text = ""

    if input_path and input_path != "-":
        p = Path(input_path)
        if not p.exists():
            print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
            sys.exit(1)
        try:
            with open(p, "r", encoding="utf-8") as f:
                input_text = f.read()
        except Exception as e:
            print(f"Error reading '{input_path}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Read from stdin
        if sys.stdin.isatty() and not input_path:
            print("storybook_craft: Reading from stdin (press Ctrl+D when finished, or run with --help)...", file=sys.stderr)
        input_text = sys.stdin.read()

    if not input_text.strip():
        print("Error: Input content is empty.", file=sys.stderr)
        sys.exit(1)

    # 0. Mode: Clean Existing Markdown Media Only
    if args.clean_media_only:
        clean_target = args.clean_media or "all"
        cleaned_text = remove_markdown_media(input_text, media_types=clean_target)
        if args.in_place and input_path and input_path != "-":
            with open(input_path, "w", encoding="utf-8") as f:
                f.write(cleaned_text)
            print(f"Successfully cleaned markdown media in-place: {input_path}")
        elif args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(cleaned_text)
            print(f"Successfully wrote cleaned markdown to {args.output}")
        else:
            sys.stdout.write(cleaned_text)
        sys.exit(0)

    # 1. Mode: Display Statistics
    if args.stats:
        stats = get_storybook_stats(input_text)
        print("=" * 60)
        print("Storybook Markdown Statistics")
        print("=" * 60)
        print(f"  Chinese (CJK) Characters : {stats['cjk_characters']}")
        print(f"  English Words            : {stats['english_words']}")
        print(f"  Total Story Units        : {stats['total_story_units']}")
        print(f"  Paragraphs               : {stats['paragraphs']}")
        print(f"  Level 1 Titles (#)       : {stats['h1_headings']}")
        print(f"  Total Media Tags         : {stats['total_media_tags']}")
        print(f"    - Image Tags           : {stats['image_tags_count']}")
        print(f"    - Video Tags           : {stats['video_tags_count']}")
        print("=" * 60)
        if stats['tags']:
            print("\nExtracted Tags Preview:")
            for t in stats['tags']:
                t_copy = {k: v for k, v in t.items() if not k.startswith("_")}
                print(f"  [{t_copy.get('type', '').upper():5s}] ID: {t_copy.get('id', ''):8s} Section: {t_copy.get('section', '') or t_copy.get('title', '')}")
        sys.exit(0)

    # 2. Mode: Extract Tags as JSON
    if args.extract_tags:
        tags = extract_media_tags(input_text)
        # Strip internal keys
        clean_tags = [{k: v for k, v in t.items() if not k.startswith("_")} for t in tags]
        json_output = json.dumps({"count": len(clean_tags), "tags": clean_tags}, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_output + "\n")
            print(f"Successfully extracted {len(clean_tags)} tags to {args.output}")
        else:
            print(json_output)
        sys.exit(0)

    # 3. Mode: Clean / Remove Tags
    if args.clean:
        cleaned_text = remove_media_tags(input_text)
        if args.in_place and input_path and input_path != "-":
            with open(input_path, "w", encoding="utf-8") as f:
                f.write(cleaned_text)
            print(f"Successfully cleaned tags in-place: {input_path}")
        elif args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(cleaned_text)
            print(f"Successfully wrote cleaned markdown to {args.output}")
        else:
            sys.stdout.write(cleaned_text)
        sys.exit(0)

    # 4. Mode: Insert Media Tags (Standard Crafting)
    media_types = args.media_types or ["all"]

    crafted_text = insert_media_tags(
        markdown_text=input_text,
        media_types=media_types,
        image_gap=args.image_gap,
        first_insert=args.first_insert,
        first_insert_pos=args.first_insert_pos,
        reset_on_h1=args.reset_on_h1,
        generate_prompts=args.generate_prompts,
        clean_media=args.clean_media,
        img_prefix=args.img_prefix,
        vid_prefix=args.vid_prefix,
        id_digits=args.id_digits,
        tag_format=args.tag_format,
        remove_existing=True
    )

    if args.verbose:
        stats = get_storybook_stats(crafted_text)
        print(f"[storybook_craft] Processed {stats['total_story_units']} story units across {stats['paragraphs']} paragraphs.", file=sys.stderr)
        print(f"[storybook_craft] Inserted {stats['image_tags_count']} image tags and {stats['video_tags_count']} video tags.", file=sys.stderr)

    # Output results
    if args.in_place and input_path and input_path != "-":
        with open(input_path, "w", encoding="utf-8") as f:
            f.write(crafted_text)
        print(f"Successfully updated markdown with tags in-place: {input_path}")
    elif args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(crafted_text)
        print(f"Successfully wrote crafted markdown to {args.output}")
    else:
        sys.stdout.write(crafted_text)


if __name__ == "__main__":
    main()
