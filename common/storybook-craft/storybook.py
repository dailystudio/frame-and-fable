#!/usr/bin/env python3
"""
storybook.py: Modern story content craft and visual media pipeline.

Commands:
  python storybook.py create "<prompt>"      Create story content from prompt (placeholder for future release)
  python storybook.py media <file>          End-to-end media pipeline: tag -> prompt -> assets -> generate
  python storybook.py media tag <file>      Insert structured image and video tags into Markdown
  python storybook.py media prompt <file>   Generate/enrich visual prompts from narrative context
  python storybook.py media generate <file> Generate AI media assets (images/videos) in workspace
  python storybook.py assets <file>         Scaffold workspace and extract character/style metadata (no image generation)
  python storybook.py assets <file> -g      Scaffold workspace and generate AI reference images
  python storybook.py assets collect [file] Discover ref_xxx.png images and sync character/style JSON files
  python storybook.py char-ref <file>       Manage character reference assets (auto-extract or import)
  python storybook.py style-ref <file>      Manage style reference assets (auto-extract or import)
  python storybook.py test                  Run built-in test suite
"""

import sys
import os
import re
import json
import shutil
import argparse
import unicodedata
import unittest
import base64
import mimetypes
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

# Ensure Homebrew / system site-packages are available for google-genai on macOS
for _sp in [
    "/opt/homebrew/lib/python3.14/site-packages",
    "/opt/homebrew/lib/python3.13/site-packages",
    "/opt/homebrew/lib/python3.12/site-packages",
    "/usr/local/lib/python3.14/site-packages",
]:
    if Path(_sp).exists() and _sp not in sys.path:
        sys.path.append(_sp)


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
    words = re.findall(r"\b[a-zA-Z0-9]+(?:['\-][a-zA-Z0-9]+)*\b", non_cjk_str)
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
    # Clean internal keys before outputting
    clean_data = {k: v for k, v in tag_data.items() if not k.startswith("_")}

    if tag_format == "json-comment":
        json_str = json.dumps(clean_data, ensure_ascii=False)
        return f"<!-- storybook-media: {json_str} -->"

    elif tag_format == "kv-comment":
        kv_pairs = []
        for k, v in clean_data.items():
            if isinstance(v, (dict, list)):
                val_str = json.dumps(v, ensure_ascii=False).replace('"', '&quot;')
            else:
                val_str = str(v).replace('"', '&quot;')
            kv_pairs.append(f'{k}="{val_str}"')
        return f"<!-- storybook-media {' '.join(kv_pairs)} -->"

    elif tag_format == "block-comment":
        lines = ["<!-- STORYBOOK:MEDIA"]
        for k, v in clean_data.items():
            if isinstance(v, (dict, list)):
                lines.append(f"  {k}: {json.dumps(v, ensure_ascii=False)}")
            else:
                lines.append(f"  {k}: {v}")
        lines.append("-->")
        return "\n".join(lines)

    elif tag_format == "visible":
        media_type = clean_data.get("type", "media")
        media_id = clean_data.get("id", "")
        sec = clean_data.get("section") or clean_data.get("title") or ""
        sec_str = f" | section: {sec}" if sec else ""
        return f"> 🎨 **[Media: {media_type} | id: {media_id}{sec_str}]**"

    else:
        json_str = json.dumps(clean_data, ensure_ascii=False)
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

        # Check for Thematic Break
        if re.match(r'^(\*{3,}|-{3,}|_{3,})$', stripped):
            flush_paragraph()
            blocks.append(MarkdownBlock(MarkdownBlock.TYPE_THEMATIC_BREAK, line))
            i += 1
            continue

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
    generate_prompts: bool = True,
    clean_media: Optional[Union[str, List[str]]] = None,
    img_prefix: str = DEFAULT_IMG_PREFIX,
    vid_prefix: str = DEFAULT_VID_PREFIX,
    id_digits: int = DEFAULT_ID_DIGITS,
    tag_format: str = "json-comment",
    remove_existing: bool = True
) -> str:
    """
    Inserts image and video tags into the given markdown text.
    """
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

    if clean_media:
        markdown_text = remove_markdown_media(markdown_text, media_types=clean_media)

    if remove_existing:
        markdown_text = remove_media_tags(markdown_text)

    blocks = split_markdown_into_blocks(markdown_text)

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

    for sec in sections:
        if sec.heading:
            h_block = sec.heading
            title_text = h_block.content.strip()
            current_section = title_text

            if h_block.block_type == MarkdownBlock.TYPE_H1:
                h1_count += 1
                output_lines.append(h_block.raw_text)

                if reset_on_h1:
                    accumulated_units = 0

                # Video Tag: Skip the first # Title (document title), insert for chapter titles
                if h1_count > 1 and "video" in types_set:
                    first_para_text = sec.narrative_paras[0].content if sec.narrative_paras else ""
                    prompt_str = build_prompt("video", title_text, before_text="", after_text=first_para_text) if generate_prompts else ""
                    vid_tag_str = make_video_tag(video_index, title_text, prompt=prompt_str, context_hint=first_para_text)
                    video_index += 1
                    if not h_block.raw_text.endswith("\n"):
                        output_lines.append("\n")
                    output_lines.append(f"{vid_tag_str}\n\n")

                if "image" in types_set and first_insert and not first_image_inserted and first_insert_pos == "at-story-start":
                    first_para_text = sec.narrative_paras[0].content if sec.narrative_paras else ""
                    prompt_str = build_prompt("image", current_section, before_text="", after_text=first_para_text) if generate_prompts else ""
                    img_tag_str = make_image_tag(image_index, current_section, prompt=prompt_str, context_hint=first_para_text)
                    image_index += 1
                    first_image_inserted = True
                    accumulated_units = 0
                    output_lines.append(f"{img_tag_str}\n\n")
            else:
                output_lines.append(h_block.raw_text)

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

    result = "".join(output_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip() + "\n"


# ==============================================================================
# Tag Extraction, Removal & Modification
# ==============================================================================

def extract_media_tags(markdown_text: str) -> List[Dict[str, Any]]:
    """
    Extract all storybook media tags from markdown text into structured dicts.
    """
    tags: List[Dict[str, Any]] = []

    # 1. Search JSON comments
    for m in TAG_JSON_REGEX.finditer(markdown_text):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict):
                data["_raw_tag"] = m.group(0)
                data["_span"] = m.span()
                data["_format"] = "json-comment"
                tags.append(data)
        except Exception:
            pass

    # 2. Search KV comments
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
            kv_dict["_format"] = "kv-comment"
            tags.append(kv_dict)

    # 3. Search Block comments
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
            b_dict["_format"] = "block-comment"
            tags.append(b_dict)

    # 4. Search Visible markers
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
            v_dict["_format"] = "visible"
            tags.append(v_dict)

    tags.sort(key=lambda x: x.get("_span", (0, 0))[0])
    return tags


def remove_media_tags(markdown_text: str) -> str:
    """Strip all storybook media tags from markdown text."""
    text = TAG_JSON_REGEX.sub('', markdown_text)
    text = TAG_KV_REGEX.sub('', text)
    text = TAG_BLOCK_REGEX.sub('', text)
    text = TAG_VISIBLE_REGEX.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def remove_markdown_media(
    markdown_text: str,
    media_types: Union[str, List[str]] = "all"
) -> str:
    """Remove standard Markdown and HTML media elements (images/videos)."""
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
        text = re.sub(r'<video\b[^>]*>.*?</video>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<video\b[^>]*\/?>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<iframe\b[^>]*(youtube|vimeo|bilibili|video|player)[^>]*>.*?</iframe>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'\[!\[.*?\]\([^\)]*\)\]\([^\)]*\)', '', text)

    if "image" in types_set:
        text = re.sub(r'!\[.*?\]\([^\)]*\)', '', text)
        text = re.sub(r'!\[.*?\]\[[^\]]*\]', '', text)
        text = re.sub(r'<img\b[^>]*\/?>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<picture\b[^>]*>.*?</picture>', '', text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + "\n"


def get_storybook_stats(markdown_text: str) -> Dict[str, Any]:
    """Compute storybook metrics."""
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
# Context Prompt Generation & Tag Enrichment
# ==============================================================================

def update_media_tag_prompts(
    markdown_text: str,
    force: bool = False,
    use_ai: bool = False,
    api_key: Optional[str] = None
) -> str:
    """
    Examines media tags in markdown text, extracts context surrounding each tag,
    and updates/enriches the 'prompt' field of the tags.
    """
    tags = extract_media_tags(markdown_text)
    if not tags:
        return markdown_text

    blocks = split_markdown_into_blocks(markdown_text)
    
    # Track current section and paragraphs
    tag_replacements: List[Tuple[str, str]] = []

    # Map tag positions relative to narrative paragraphs
    current_section = ""
    last_para = ""

    # Optional AI Client
    ai_client = None
    if use_ai:
        try:
            from google import genai
            resolved_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if resolved_key:
                ai_client = genai.Client(api_key=resolved_key)
        except Exception:
            pass

    for i, b in enumerate(blocks):
        if b.block_type in (MarkdownBlock.TYPE_H1, MarkdownBlock.TYPE_HEADING):
            current_section = b.content.strip()
        elif b.block_type == MarkdownBlock.TYPE_PARAGRAPH:
            last_para = b.content.strip()
        elif b.block_type == MarkdownBlock.TYPE_EXISTING_TAG:
            # Find matching tag dict
            for t in tags:
                if t.get("_raw_tag") == b.raw_text.strip():
                    # Check if prompt should be updated
                    existing_prompt = t.get("prompt", "")
                    if not existing_prompt or force:
                        # Find next paragraph for after_text
                        next_para = ""
                        for j in range(i + 1, len(blocks)):
                            if blocks[j].block_type == MarkdownBlock.TYPE_PARAGRAPH:
                                next_para = blocks[j].content.strip()
                                break
                            elif blocks[j].block_type in (MarkdownBlock.TYPE_H1, MarkdownBlock.TYPE_HEADING):
                                break

                        sec = t.get("section") or t.get("title") or current_section
                        new_prompt = build_prompt(
                            t.get("type", "image"),
                            section_title=sec,
                            before_text=last_para,
                            after_text=next_para
                        )

                        # AI enrichment if enabled
                        if ai_client:
                            try:
                                resp = ai_client.models.generate_content(
                                    model="gemini-2.5-flash",
                                    contents=f"You are a master art director. Enhance this scene description into a vivid visual image generation prompt with art style, lighting, composition and emotional mood: '{new_prompt}'. Keep it to 2 concise sentences."
                                )
                                if resp and resp.text:
                                    new_prompt = resp.text.strip()
                            except Exception:
                                pass

                        t["prompt"] = new_prompt
                        tag_fmt = t.get("_format", "json-comment")
                        new_tag_str = format_tag(t, tag_format=tag_fmt)
                        tag_replacements.append((t["_raw_tag"], new_tag_str))
                    break

    # Apply tag replacements to the text
    updated_text = markdown_text
    for old_raw, new_raw in tag_replacements:
        updated_text = updated_text.replace(old_raw, new_raw, 1)

    return updated_text


# ==============================================================================
# AI Media Asset Generation Engine
# ==============================================================================

def find_gemini_image_script() -> Optional[Path]:
    """Find path to the gemini-image.py tool from image-craft."""
    # 1. Relative to this script: ../image-craft/gemini-image.py
    script_path = Path(__file__).resolve().parent.parent / "image-craft" / "gemini-image.py"
    if script_path.exists():
        return script_path
    # 2. Check candidate locations
    candidates = [
        Path("../image-craft/gemini-image.py"),
        Path("common/image-craft/gemini-image.py"),
        Path("../common/image-craft/gemini-image.py"),
        Path("../../common/image-craft/gemini-image.py"),
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    return None


# ==============================================================================
# Workspace & Reference Asset Management
# ==============================================================================

class StoryWorkspace:
    """
    Manages an isolated workspace for a storybook markdown file.
    Structure:
      <base_output_dir>/<stem>/
        ├── <stem>-output.md
        ├── images/
        ├── videos/
        ├── char-ref/
        │   ├── <CharacterA>/
        │   │   ├── ref_001.png
        │   │   └── character.json
        │   └── characters.json
        └── style-ref/
            ├── ref_001.png
            └── style.json
    """
    def __init__(
        self,
        input_file: Optional[Union[str, Path]] = None,
        base_output_dir: Union[str, Path] = "outputs"
    ):
        if input_file and str(input_file) != "-":
            p = Path(input_file)
            self.input_file: Optional[Path] = p
            self.stem = p.stem
        else:
            self.input_file = None
            self.stem = "story"

        base = Path(base_output_dir)
        # Avoid creating nested abc/abc if base already ends with stem
        if base.name == self.stem:
            self.workspace_dir = base
        else:
            self.workspace_dir = base / self.stem

        self.images_dir = self.workspace_dir / "images"
        self.videos_dir = self.workspace_dir / "videos"
        self.char_ref_dir = self.workspace_dir / "char-ref"
        self.style_ref_dir = self.workspace_dir / "style-ref"
        self.output_md = self.workspace_dir / f"{self.stem}-output.md"

    def ensure_dirs(self):
        """Ensure all required workspace directories exist."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.char_ref_dir.mkdir(parents=True, exist_ok=True)
        self.style_ref_dir.mkdir(parents=True, exist_ok=True)

    def get_char_dir(self, char_name: str, create: bool = True) -> Path:
        """Return and optionally create dedicated reference subdirectory for a character."""
        clean = re.sub(r'[\\/*?:"<>|]', '', str(char_name)).strip() or "character"
        cdir = self.char_ref_dir / clean
        if create:
            cdir.mkdir(parents=True, exist_ok=True)
        return cdir

    def get_relative_asset_path(self, asset_path: Union[str, Path]) -> str:
        """Calculate path relative to workspace root (e.g. images/img_001.png)."""
        p = Path(asset_path).resolve()
        try:
            return str(p.relative_to(self.workspace_dir.resolve()))
        except ValueError:
            return str(p)


def parse_char_refs_arg(char_refs_inputs: Optional[Union[List[str], str]]) -> Dict[str, List[str]]:
    """
    Parse character reference arguments into a mapping: {CharacterName: [image_path_1, ...]}.
    Supports formats:
      --char-refs A:XX.png, A:YY.png, B:ZZ.png
      --char-refs A:XX.png --char-refs B:ZZ.png
      --char-refs "A:XX.png, B:ZZ.png"
    """
    if not char_refs_inputs:
        return {}
    if isinstance(char_refs_inputs, str):
        char_refs_inputs = [char_refs_inputs]

    mapping: Dict[str, List[str]] = {}
    for raw in char_refs_inputs:
        if not raw:
            continue
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        for part in parts:
            tokens = part.split()
            sub_parts = tokens if (len(tokens) > 1 and all(":" in tok for tok in tokens)) else [part]
            for sp in sub_parts:
                if ":" in sp:
                    name, img_path = sp.split(":", 1)
                    name = name.strip()
                    img_path = img_path.strip().strip("'\"")
                    if name and img_path:
                        mapping.setdefault(name, []).append(img_path)
    return mapping


def parse_style_refs_arg(style_refs_inputs: Optional[Union[List[str], str]]) -> List[str]:
    """
    Parse style reference arguments into a list of image paths.
    Supports formats:
      --style-ref XX.png, YY.png, ZZ.png
      --style-ref XX.png --style-ref YY.png
    """
    if not style_refs_inputs:
        return []
    if isinstance(style_refs_inputs, str):
        style_refs_inputs = [style_refs_inputs]

    refs: List[str] = []
    for raw in style_refs_inputs:
        if not raw:
            continue
        parts = [p.strip().strip("'\"") for p in raw.split(",") if p.strip()]
        for part in parts:
            for sp in part.split():
                clean_p = sp.strip().strip("'\"")
                if clean_p and clean_p not in refs:
                    refs.append(clean_p)
    return refs


def extract_characters_from_story(
    markdown_text: str,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Automatically extract character information (names, visual DNA, portrait generation prompts)
    from story markdown text.
    Uses Gemini API if available, with intelligent heuristic fallback.
    """
    resolved_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    client = None
    if resolved_key:
        try:
            from google import genai
            client = genai.Client(api_key=resolved_key)
        except Exception:
            client = None

    clean_text = strip_markdown_decorations(markdown_text)
    sample_text = clean_text[:4000]

    # 1. Try Gemini API extraction
    if client:
        try:
            prompt = (
                "You are an expert storybook art director. Analyze the story below and identify the main characters (1 to 4 characters).\n"
                "For each character, output:\n"
                "- 'name': character's name (e.g. '布洛克·铁盾' or 'Nora')\n"
                "- 'role': their role or title in the story (e.g. 'Guardian Warrior' or 'Space Explorer')\n"
                "- 'visual_dna': detailed physical visual appearance (age, species/ethnicity, hair, eyes, facial features, clothing/armor, distinct marks). Describe ONLY their physical look on a plain background, without background scenes or actions.\n"
                "- 'portrait_prompt': prompt to generate a solo character concept art portrait on a clean neutral white or light gray background, studio lighting, highly detailed concept art sheet.\n\n"
                "Story text:\n"
                f"{sample_text}\n\n"
                "Return strictly valid JSON with key 'characters': [ { ... } ]"
            )
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            raw_content = getattr(resp, "text", "")
            match = re.search(r'\{.*\}', raw_content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                chars = data.get("characters", [])
                if chars:
                    return chars
        except Exception:
            pass

    # 2. Heuristic fallback extractor
    extracted: List[Dict[str, Any]] = []
    seen_names = set()
    no_comment_text = re.sub(r'<!--.*?-->', '', markdown_text, flags=re.DOTALL)

    # Pattern A: Bold character intros: **“磐石”——布洛克·铁盾（Brock Ironshield）** or **阿尔文·蓝焰**
    bold_matches = re.findall(r'\*\*(?:[“"”\']?[^”"\'—–\-\n]+[”"\'—–\-]*)?([^\*\n]{2,25})\*\*', no_comment_text)
    for b in bold_matches:
        b_clean = b.strip()
        if "——" in b_clean:
            b_clean = b_clean.split("——")[-1].strip()
        name_only = re.sub(r'[\(（].*?[\)）]', '', b_clean).strip('“"”\' ')
        if len(name_only) in range(2, 12) and name_only not in seen_names:
            if not name_only.startswith("的") and not any(p in name_only for p in ["。", "，", "！", "？", "、", "；", "：", ".", ",", "\"", "'"]):
                if not any(stop in name_only for stop in ["前代文明", "古代遗产", "飞行器", "这片大陆", "然而", "但是", "虚空崩塌", "共鸣", "碎片", "脉络", "部分", "衡器", "怪"]):
                    seen_names.add(name_only)
                    role = "Main Character"
                    visual_dna = f"Story protagonist '{name_only}', iconic costume and features, neutral studio lighting, isolated portrait."
                    portrait_prompt = f"Character concept portrait of {name_only}, neutral background, studio lighting, highly detailed storybook concept art"
                    extracted.append({
                        "name": name_only,
                        "role": role,
                        "visual_dna": visual_dna,
                        "portrait_prompt": portrait_prompt
                    })

    # Pattern B: Chinese naming: 名叫([^\s，。]+)
    for m in re.findall(r'名叫([^\s，。]{2,12})', no_comment_text):
        m_clean = m.strip()
        if "的" in m_clean:
            m_clean = m_clean.split("的")[0].strip()
        if len(m_clean) in range(2, 10) and m_clean not in seen_names:
            seen_names.add(m_clean)
            extracted.append({
                "name": m_clean,
                "role": "Adventurer",
                "visual_dna": f"Spirited young adventurer {m_clean}, curious expression, travel clothes, clean neutral background.",
                "portrait_prompt": f"Character concept portrait of {m_clean}, young adventurer, expressive face, neutral gray background, storybook character design"
            })

    # Pattern C: Check for magical companion / creatures (e.g. 小精灵)
    if "小精灵" in no_comment_text and "小精灵" not in seen_names:
        seen_names.add("小精灵")
        extracted.append({
            "name": "小精灵",
            "role": "Forest Spirit",
            "visual_dna": "Tiny translucent glowing forest fairy, delicate wings, luminous blue particle aura, friendly expression.",
            "portrait_prompt": "Concept art of a glowing miniature translucent forest fairy, delicate ethereal wings, luminous blue light, clean isolated background"
        })

    # Pattern D: English pilot / named ([A-Z][a-z]+)
    for m in re.findall(r'(?:named|pilot|hero)\s+([A-Z][a-z]+)', no_comment_text):
        if m not in seen_names and len(m) > 2:
            seen_names.add(m)
            extracted.append({
                "name": m,
                "role": "Explorer",
                "visual_dna": f"Adventurous explorer {m}, distinctive uniform, determined expression, isolated character sheet.",
                "portrait_prompt": f"Character design concept portrait of {m}, sci-fi / fantasy explorer, highly detailed, neutral gray background"
            })

    if not extracted:
        extracted.append({
            "name": "Protagonist",
            "role": "Story Protagonist",
            "visual_dna": "Heroic story protagonist with expressive features, iconic storybook travel attire, clean neutral studio lighting.",
            "portrait_prompt": "Storybook protagonist character concept sheet, isolated on neutral background, highly detailed 8k portrait"
        })

    return extracted[:4]


def extract_style_from_story(
    markdown_text: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Automatically extract the visual art style and reference prompts from story markdown text.
    Uses Gemini API if available, with intelligent heuristic fallback.
    """
    resolved_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    client = None
    if resolved_key:
        try:
            from google import genai
            client = genai.Client(api_key=resolved_key)
        except Exception:
            client = None

    clean_text = strip_markdown_decorations(markdown_text)
    sample_text = clean_text[:4000]

    if client:
        try:
            prompt = (
                "You are an expert storybook art director. Analyze the story below and determine the optimal visual illustration art style.\n"
                "Return strictly valid JSON with:\n"
                "- 'style_name': short style name (e.g. 'Warm Watercolor Storybook' or 'Epic Fantasy Digital Art')\n"
                "- 'style_prompt': detailed description of the art medium, brushwork, lighting, color palette, rendering quality (e.g. 'whimsical watercolor illustration, textured paper, warm pastel palette, soft volumetric lighting')\n"
                "- 'reference_prompt': a prompt to generate a scenery or landscape image demonstrating this exact art style without any characters.\n\n"
                "Story text:\n"
                f"{sample_text}\n"
            )
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            raw_content = getattr(resp, "text", "")
            match = re.search(r'\{.*\}', raw_content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if data.get("style_prompt"):
                    return data
        except Exception:
            pass

    # Heuristic fallback
    text_lower = markdown_text.lower()
    if any(k in text_lower or k in markdown_text for k in ["galaxy", "space", "pilot", "obelisk", "cosmic", "stars", "nebula"]):
        return {
            "style_name": "Cinematic Sci-Fi Digital Art",
            "style_prompt": "Cinematic sci-fi digital concept art, celestial lighting, glowing nebula hues, deep space atmosphere, painterly matte finish, highly detailed 8k",
            "reference_prompt": "A majestic glowing crystalline obelisk standing on a silent lunar crater, cosmic starry sky and emerald nebula in background, cinematic matte painting, scenic environment, no humans"
        }
    elif any(k in markdown_text for k in ["中世纪", "大陆", "城堡", "史前", "神殿", "战士", "法师", "巨盾", "战锤"]):
        return {
            "style_name": "Epic Fantasy Storybook Illustration",
            "style_prompt": "Epic medieval fantasy storybook illustration, rich textured brushstrokes, warm golden amber lighting, deep atmospheric depth, painterly storybook fantasy art",
            "reference_prompt": "Misty medieval rolling hills with distant castle spires and a winding silver river under golden sunrise, fantasy landscape, master painterly art style, scenic environment, no people"
        }
    else:
        return {
            "style_name": "Whimsical Watercolor Storybook",
            "style_prompt": "Whimsical hand-drawn watercolor storybook illustration, soft warm pastel palette, gentle wash textures, dappled natural light, enchanting fairy tale atmosphere",
            "reference_prompt": "An enchanted sunlit ancient forest with mossy stones, blooming wildflower meadow and a babbling crystal stream, whimsical watercolor art, no people"
        }


def natural_sort_key(s: str) -> List[Union[int, str]]:
    """Sort strings containing numbers in natural/human order (e.g. ref_1, ref_2, ref_10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def find_reference_images(directory: Union[str, Path]) -> List[str]:
    """
    Find reference images in directory.
    Prioritizes files matching ref_*.png (.jpg/.jpeg/.webp), followed by other images.
    Returns naturally sorted list of filenames.
    """
    p = Path(directory)
    if not p.exists() or not p.is_dir():
        return []

    valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
    ref_files = []
    other_files = []

    for f in p.iterdir():
        if f.is_file() and f.suffix.lower() in valid_exts:
            if f.name.lower().startswith("ref_"):
                ref_files.append(f.name)
            else:
                other_files.append(f.name)

    ref_files.sort(key=natural_sort_key)
    other_files.sort(key=natural_sort_key)
    return ref_files + other_files


def setup_workspace_assets(
    workspace: StoryWorkspace,
    markdown_text: str,
    char_refs_arg: Optional[Dict[str, List[str]]] = None,
    style_refs_arg: Optional[List[str]] = None,
    style_prompt: Optional[str] = None,
    image_model: str = "gemini-3.1-flash-image",
    api_key: Optional[str] = None,
    generate_images: bool = False,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Sets up character references (outputs/<stem>/char-ref/<char>/) and
    style references (outputs/<stem>/style-ref/).
    - Default behavior: scaffolds folders and extracts JSON metadata without generating images.
    - If generate_images=True: invokes AI model to generate reference images (ref_001.png).
    - If user provides references via CLI, imports and copies them.
    """
    if not dry_run:
        workspace.ensure_dirs()
    report: Dict[str, Any] = {
        "characters": [],
        "styles": []
    }

    if verbose:
        print(f"[storybook assets] Workspace directory: {workspace.workspace_dir}")
        print(f"  - Images directory    : {workspace.images_dir}")
        print(f"  - Videos directory    : {workspace.videos_dir}")
        print(f"  - Character references: {workspace.char_ref_dir}")
        print(f"  - Style references    : {workspace.style_ref_dir}")

    resolved_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    gemini_script = find_gemini_image_script()

    # --------------------------------------------------------------------------
    # 1. Character References Setup
    # --------------------------------------------------------------------------
    if char_refs_arg:
        if verbose:
            print(f"[storybook assets] Processing {len(char_refs_arg)} user-specified character(s)...")
        for char_name, img_paths in char_refs_arg.items():
            cdir = workspace.get_char_dir(char_name, create=not dry_run)
            saved_images = []
            for src_path_str in img_paths:
                src_path = Path(src_path_str)
                dest_file = cdir / src_path.name
                if src_path.exists():
                    if not dry_run:
                        shutil.copy2(src_path, dest_file)
                    saved_images.append(dest_file.name)
                    if verbose:
                        print(f"  -> Imported character reference for '{char_name}': {src_path} -> {dest_file}")
                else:
                    print(f"  Warning: Character reference image '{src_path}' not found.", file=sys.stderr)
                    saved_images.append(src_path.name)

            # Discover any other images already in cdir
            if not dry_run and cdir.exists():
                disk_imgs = find_reference_images(cdir)
                for di in disk_imgs:
                    if di not in saved_images:
                        saved_images.append(di)

            char_info = {
                "name": char_name,
                "role": "User Specified",
                "visual_dna": f"Character {char_name}",
                "images": saved_images,
                "source": "user_provided"
            }
            if not dry_run:
                with open(cdir / "character.json", "w", encoding="utf-8") as f:
                    json.dump(char_info, f, ensure_ascii=False, indent=2)
            report["characters"].append(char_info)
    else:
        existing_char_dirs = [d for d in workspace.char_ref_dir.iterdir() if d.is_dir()] if workspace.char_ref_dir.exists() else []
        if existing_char_dirs and not force:
            if verbose:
                print(f"[storybook assets] Reusing existing {len(existing_char_dirs)} character reference directory(ies).")
            for cdir in existing_char_dirs:
                cinfo_path = cdir / "character.json"
                c_info: Dict[str, Any] = {}
                if cinfo_path.exists():
                    try:
                        with open(cinfo_path, "r", encoding="utf-8") as f:
                            c_info = json.load(f)
                    except Exception:
                        pass
                if not c_info:
                    c_info = {
                        "name": cdir.name,
                        "role": "Character",
                        "visual_dna": f"Character {cdir.name}",
                        "portrait_prompt": f"Portrait of {cdir.name}",
                        "source": "auto_extracted"
                    }
                disk_imgs = find_reference_images(cdir)

                if generate_images and not disk_imgs:
                    ref_img_path = cdir / "ref_001.png"
                    if dry_run:
                        if verbose:
                            print(f"  [DRY RUN] Would generate reference portrait for '{cdir.name}' -> {ref_img_path}")
                        disk_imgs.append("ref_001.png")
                    else:
                        gen_prompt = f"{c_info.get('portrait_prompt', '')}. Isolated character concept art, clean plain neutral background, centered studio portrait."
                        if verbose:
                            print(f"  Generating portrait reference for '{cdir.name}' -> {ref_img_path}...")
                        success = False
                        if gemini_script and gemini_script.exists():
                            cmd = [
                                sys.executable, str(gemini_script),
                                gen_prompt,
                                "-o", str(ref_img_path),
                                "-m", image_model,
                                "-r", "1:1",
                                "-s", "1K"
                            ]
                            if resolved_key:
                                cmd.extend(["--api-key", resolved_key])
                            try:
                                res = subprocess.run(cmd, capture_output=True, text=True)
                                if res.returncode == 0 and ref_img_path.exists():
                                    success = True
                            except Exception as e:
                                print(f"  Error invoking gemini-image for character {cdir.name}: {e}", file=sys.stderr)
                        if success:
                            disk_imgs.append("ref_001.png")
                            if verbose:
                                print(f"  -> Successfully generated character reference: {ref_img_path}")

                c_info["images"] = disk_imgs
                if not dry_run and cinfo_path.parent.exists():
                    with open(cinfo_path, "w", encoding="utf-8") as f:
                        json.dump(c_info, f, ensure_ascii=False, indent=2)
                report["characters"].append(c_info)
        else:
            if verbose:
                print("[storybook assets] No character reference provided; extracting characters from story...")
            extracted_chars = extract_characters_from_story(markdown_text, api_key=resolved_key)
            if verbose:
                print(f"  Found {len(extracted_chars)} character(s): {', '.join(c['name'] for c in extracted_chars)}")

            for c in extracted_chars:
                cname = c["name"]
                cdir = workspace.get_char_dir(cname, create=not dry_run)
                ref_img_path = cdir / "ref_001.png"
                existing_disk_imgs = find_reference_images(cdir) if cdir.exists() else []
                img_list = list(existing_disk_imgs)

                if generate_images:
                    if not img_list or force:
                        if dry_run:
                            if verbose:
                                print(f"  [DRY RUN] Would generate reference portrait for '{cname}' -> {ref_img_path}")
                            img_list.append("ref_001.png")
                        else:
                            gen_prompt = f"{c.get('portrait_prompt', '')}. Isolated character concept art, clean plain neutral background, centered studio portrait."
                            if verbose:
                                print(f"  Generating portrait reference for '{cname}' -> {ref_img_path}...")
                            success = False
                            if gemini_script and gemini_script.exists():
                                cmd = [
                                    sys.executable, str(gemini_script),
                                    gen_prompt,
                                    "-o", str(ref_img_path),
                                    "-m", image_model,
                                    "-r", "1:1",
                                    "-s", "1K"
                                ]
                                if resolved_key:
                                    cmd.extend(["--api-key", resolved_key])
                                try:
                                    res = subprocess.run(cmd, capture_output=True, text=True)
                                    if res.returncode == 0 and ref_img_path.exists():
                                        success = True
                                except Exception as e:
                                    print(f"  Error invoking gemini-image for character {cname}: {e}", file=sys.stderr)

                            if success:
                                img_list.append("ref_001.png")
                                if verbose:
                                    print(f"  -> Successfully generated character reference: {ref_img_path}")
                            else:
                                if verbose:
                                    print(f"  (Note: Generation skipped or offline; saved character metadata for {cname})")
                else:
                    if verbose and not existing_disk_imgs:
                        print(f"  Scaffolded character folder for '{cname}' -> {cdir}")

                c_data = {
                    "name": cname,
                    "role": c.get("role", "Character"),
                    "visual_dna": c.get("visual_dna", ""),
                    "portrait_prompt": c.get("portrait_prompt", ""),
                    "images": img_list,
                    "source": "auto_extracted"
                }
                if not dry_run:
                    with open(cdir / "character.json", "w", encoding="utf-8") as f:
                        json.dump(c_data, f, ensure_ascii=False, indent=2)
                report["characters"].append(c_data)

    if not dry_run and workspace.char_ref_dir.exists():
        with open(workspace.char_ref_dir / "characters.json", "w", encoding="utf-8") as f:
            json.dump({"characters": report["characters"]}, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------------------------
    # 2. Style Reference Setup
    # --------------------------------------------------------------------------
    if style_refs_arg:
        if verbose:
            print(f"[storybook assets] Processing {len(style_refs_arg)} user-specified style reference(s)...")
        saved_style_imgs = []
        for src_path_str in style_refs_arg:
            src_path = Path(src_path_str)
            dest_file = workspace.style_ref_dir / src_path.name
            if src_path.exists():
                if not dry_run:
                    shutil.copy2(src_path, dest_file)
                saved_style_imgs.append(dest_file.name)
                if verbose:
                    print(f"  -> Imported style reference: {src_path} -> {dest_file}")
            else:
                print(f"  Warning: Style reference image '{src_path}' not found.", file=sys.stderr)
                saved_style_imgs.append(src_path.name)

        if not dry_run and workspace.style_ref_dir.exists():
            disk_style_imgs = find_reference_images(workspace.style_ref_dir)
            for di in disk_style_imgs:
                if di not in saved_style_imgs:
                    saved_style_imgs.append(di)

        style_info = {
            "style_name": "User Specified",
            "style_prompt": style_prompt or "",
            "images": saved_style_imgs,
            "source": "user_provided"
        }
        if not dry_run:
            with open(workspace.style_ref_dir / "style.json", "w", encoding="utf-8") as f:
                json.dump(style_info, f, ensure_ascii=False, indent=2)
        report["styles"].append(style_info)
    else:
        style_json_path = workspace.style_ref_dir / "style.json"
        if style_json_path.exists() and not force:
            if verbose:
                print("[storybook assets] Reusing existing style reference configuration.")
            s_data: Dict[str, Any] = {}
            try:
                with open(style_json_path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
            except Exception:
                pass

            disk_style_imgs = find_reference_images(workspace.style_ref_dir)
            if generate_images and not disk_style_imgs:
                ref_style_img = workspace.style_ref_dir / "ref_001.png"
                if dry_run:
                    if verbose:
                        print(f"  [DRY RUN] Would generate style reference image -> {ref_style_img}")
                    disk_style_imgs.append("ref_001.png")
                else:
                    gen_prompt = f"{s_data.get('reference_prompt', '')}. Visual style reference, scenic environment, no people."
                    if verbose:
                        print(f"  Generating style reference image -> {ref_style_img}...")
                    success = False
                    if gemini_script and gemini_script.exists():
                        cmd = [
                            sys.executable, str(gemini_script),
                            gen_prompt,
                            "-o", str(ref_style_img),
                            "-m", image_model,
                            "-r", "16:9",
                            "-s", "1K"
                        ]
                        if resolved_key:
                            cmd.extend(["--api-key", resolved_key])
                        try:
                            res = subprocess.run(cmd, capture_output=True, text=True)
                            if res.returncode == 0 and ref_style_img.exists():
                                success = True
                        except Exception as e:
                            print(f"  Error generating style image: {e}", file=sys.stderr)
                    if success:
                        disk_style_imgs.append("ref_001.png")
                        if verbose:
                            print(f"  -> Successfully generated style reference: {ref_style_img}")

            s_data["images"] = disk_style_imgs
            if not dry_run and style_json_path.parent.exists():
                with open(style_json_path, "w", encoding="utf-8") as f:
                    json.dump(s_data, f, ensure_ascii=False, indent=2)
            report["styles"].append(s_data)
        else:
            if verbose:
                print("[storybook assets] No style reference provided; extracting style from story...")
            extracted_style = extract_style_from_story(markdown_text, api_key=resolved_key)
            if style_prompt:
                extracted_style["style_prompt"] = style_prompt
            if verbose:
                print(f"  Extracted style: {extracted_style.get('style_name', 'Default')}")
                print(f"  Prompt: '{extracted_style.get('style_prompt', '')}'")

            ref_style_img = workspace.style_ref_dir / "ref_001.png"
            existing_style_imgs = find_reference_images(workspace.style_ref_dir) if workspace.style_ref_dir.exists() else []
            style_imgs = list(existing_style_imgs)

            if generate_images:
                if not style_imgs or force:
                    if dry_run:
                        if verbose:
                            print(f"  [DRY RUN] Would generate style reference image -> {ref_style_img}")
                        style_imgs.append("ref_001.png")
                    else:
                        gen_prompt = f"{extracted_style.get('reference_prompt', '')}. Visual style reference, scenic environment, no people."
                        if verbose:
                            print(f"  Generating style reference image -> {ref_style_img}...")
                        success = False
                        if gemini_script and gemini_script.exists():
                            cmd = [
                                sys.executable, str(gemini_script),
                                gen_prompt,
                                "-o", str(ref_style_img),
                                "-m", image_model,
                                "-r", "16:9",
                                "-s", "1K"
                            ]
                            if resolved_key:
                                cmd.extend(["--api-key", resolved_key])
                            try:
                                res = subprocess.run(cmd, capture_output=True, text=True)
                                if res.returncode == 0 and ref_style_img.exists():
                                    success = True
                            except Exception as e:
                                print(f"  Error generating style image: {e}", file=sys.stderr)
                        if success:
                            style_imgs.append("ref_001.png")
                            if verbose:
                                print(f"  -> Successfully generated style reference: {ref_style_img}")
            else:
                if verbose and not existing_style_imgs:
                    print(f"  Scaffolded style reference folder: {workspace.style_ref_dir} (no image generated)")

            extracted_style["images"] = style_imgs
            extracted_style["source"] = "auto_extracted"
            if not dry_run:
                with open(workspace.style_ref_dir / "style.json", "w", encoding="utf-8") as f:
                    json.dump(extracted_style, f, ensure_ascii=False, indent=2)
            report["styles"].append(extracted_style)

    return report


def align_character_with_reference_images(
    character_name: str,
    character_dir: Path,
    image_filenames: List[str],
    current_data: Dict[str, Any],
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash",
    use_ai: bool = True,
    verbose: bool = False
) -> Tuple[str, str, Optional[str]]:
    """
    Synthesizes and aligns character visual DNA and portrait prompt
    based on all collected reference images (ref_001.png, ref_002.png, ...).
    Uses Gemini Multimodal API if available, with intelligent fallback.
    Returns: (aligned_visual_dna, aligned_portrait_prompt, role)
    """
    if not image_filenames:
        return (
            current_data.get("visual_dna", f"Character {character_name}"),
            current_data.get("portrait_prompt", f"Character concept portrait of {character_name}"),
            current_data.get("role")
        )

    resolved_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    ref_list_str = ", ".join(image_filenames)

    # 1. AI Multimodal Vision Analysis (when enabled and API key is present)
    if use_ai and resolved_key:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=resolved_key)
            parts = []
            for fn in image_filenames[:8]:
                p = character_dir / fn
                if p.exists() and p.is_file():
                    mt = mimetypes.guess_type(str(p))[0] or "image/png"
                    with open(p, "rb") as f:
                        b = f.read()
                    if b:
                        parts.append(types.Part.from_bytes(data=b, mime_type=mt))

            if parts:
                prompt_text = (
                    f"You are an expert storybook art director and character designer.\n"
                    f"Analyze all {len(parts)} attached reference image(s) ({ref_list_str}) for character '{character_name}'.\n"
                    f"Existing context: role='{current_data.get('role', 'Character')}', notes='{current_data.get('visual_dna', '')}'.\n\n"
                    f"Your goal is to extract and align a consistent visual specification reflecting ALL reference images ({ref_list_str}).\n"
                    "Output strictly valid JSON with:\n"
                    "1. 'visual_dna': Detailed physical description based on the reference images (approximate age, species/build, facial features, hair color & style, eye color, skin tone, clothing/outfit, distinctive items/accessories). Plain studio look only, no background actions or scenery.\n"
                    "2. 'portrait_prompt': Production-ready text-to-image prompt to generate this exact character consistently in new scenes (centered solo portrait, neutral light gray background, cinematic studio lighting, detailed concept art sheet).\n"
                    "3. 'role': Refined character role/archetype based on visual cues (or keep existing).\n\n"
                    "Return ONLY valid JSON: { \"visual_dna\": \"...\", \"portrait_prompt\": \"...\", \"role\": \"...\" }"
                )
                if verbose:
                    print(f"    [AI Vision] Analyzing {len(parts)} reference image(s) for '{character_name}' using {model}...")
                resp = client.models.generate_content(
                    model=model,
                    contents=[prompt_text] + parts
                )
                raw_text = getattr(resp, "text", "")
                match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if match:
                    res_json = json.loads(match.group(0))
                    v_dna = res_json.get("visual_dna", "").strip()
                    p_prompt = res_json.get("portrait_prompt", "").strip()
                    role = res_json.get("role", "").strip() or current_data.get("role")
                    if v_dna and p_prompt:
                        return v_dna, p_prompt, role
        except Exception as e:
            if verbose:
                print(f"    (AI vision note for '{character_name}': {e}; falling back to local reference alignment)", file=sys.stderr)

    # 2. Local / Fallback Alignment
    base_dna = current_data.get("visual_dna", "").strip() or f"Character {character_name}"
    clean_dna = re.sub(r'\s*\(visually aligned with reference images: [^\)]+\)\.?$', '', base_dna).strip().rstrip('.')
    aligned_dna = f"{clean_dna} (visually aligned with reference images: {ref_list_str})."

    base_prompt = current_data.get("portrait_prompt", "").strip() or f"Character concept portrait of {character_name}"
    clean_prompt = re.sub(r'\s*,?\s*consistent character design aligned with reference images \([^\)]+\)[^,]*', '', base_prompt).strip().rstrip('.')
    aligned_prompt = f"{clean_prompt}, consistent character design aligned with reference images ({ref_list_str}), solo subject, clean neutral background."

    return aligned_dna, aligned_prompt, current_data.get("role")


def align_style_with_reference_images(
    style_dir: Path,
    image_filenames: List[str],
    current_data: Dict[str, Any],
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash",
    use_ai: bool = True,
    verbose: bool = False
) -> Tuple[str, str, str]:
    """
    Synthesizes and aligns visual style prompt and reference prompt
    based on all collected reference images in style-ref/.
    Uses Gemini Multimodal API if available, with intelligent fallback.
    Returns: (style_name, style_prompt, reference_prompt)
    """
    if not image_filenames:
        return (
            current_data.get("style_name", "Workspace Style"),
            current_data.get("style_prompt", ""),
            current_data.get("reference_prompt", "")
        )

    resolved_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    ref_list_str = ", ".join(image_filenames)

    # 1. AI Vision Analysis
    if use_ai and resolved_key:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=resolved_key)
            parts = []
            for fn in image_filenames[:8]:
                p = style_dir / fn
                if p.exists() and p.is_file():
                    mt = mimetypes.guess_type(str(p))[0] or "image/png"
                    with open(p, "rb") as f:
                        b = f.read()
                    if b:
                        parts.append(types.Part.from_bytes(data=b, mime_type=mt))

            if parts:
                prompt_text = (
                    f"You are a master storybook visual art director.\n"
                    f"Analyze all {len(parts)} attached style reference image(s) ({ref_list_str}).\n"
                    f"Current style notes: name='{current_data.get('style_name', '')}', prompt='{current_data.get('style_prompt', '')}'.\n\n"
                    "Extract and synthesize the unified artistic style across ALL reference images.\n"
                    "Output strictly valid JSON with:\n"
                    "1. 'style_name': Concise descriptive title for this visual art style.\n"
                    "2. 'style_prompt': Highly descriptive text prompt detailing the artistic medium, textures, brushwork, line quality, lighting, and color palette.\n"
                    "3. 'reference_prompt': Prompt to generate a scenic environment test image in this exact style with no people.\n\n"
                    "Return ONLY valid JSON: { \"style_name\": \"...\", \"style_prompt\": \"...\", \"reference_prompt\": \"...\" }"
                )
                if verbose:
                    print(f"    [AI Vision] Analyzing {len(parts)} style reference image(s) using {model}...")
                resp = client.models.generate_content(
                    model=model,
                    contents=[prompt_text] + parts
                )
                raw_text = getattr(resp, "text", "")
                match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if match:
                    res_json = json.loads(match.group(0))
                    s_name = res_json.get("style_name", "").strip() or current_data.get("style_name", "Workspace Style")
                    s_prompt = res_json.get("style_prompt", "").strip()
                    r_prompt = res_json.get("reference_prompt", "").strip()
                    if s_prompt:
                        return s_name, s_prompt, r_prompt or current_data.get("reference_prompt", "")
        except Exception as e:
            if verbose:
                print(f"    (AI vision note for style: {e}; falling back to local reference alignment)", file=sys.stderr)

    # 2. Local / Fallback Alignment
    s_name = current_data.get("style_name", "Workspace Style")
    base_sprompt = current_data.get("style_prompt", "").strip() or "Storybook art illustration"
    clean_sprompt = re.sub(r'\s*\(aligned with visual style references: [^\)]+\)\.?$', '', base_sprompt).strip().rstrip('.')
    aligned_sprompt = f"{clean_sprompt} (aligned with visual style references: {ref_list_str})."

    r_prompt = current_data.get("reference_prompt", "").strip() or "Scenic environment in reference art style, no people"
    return s_name, aligned_sprompt, r_prompt


def collect_workspace_assets(
    workspace: StoryWorkspace,
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash",
    use_ai: bool = True,
    dry_run: bool = False,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Scans the workspace directory for character and style reference images
    conforming to naming rules (e.g. ref_001.png, ref_002.png), and updates:
      - outputs/<stem>/char-ref/<Character>/character.json (images, visual_dna, portrait_prompt)
      - outputs/<stem>/char-ref/characters.json
      - outputs/<stem>/style-ref/style.json (images, style_prompt, reference_prompt)
    Returns a summary report of all discovered assets.
    """
    if verbose:
        print(f"[storybook collect] Scanning reference assets in workspace: {workspace.workspace_dir}")

    characters_report: List[Dict[str, Any]] = []
    styles_report: List[Dict[str, Any]] = []

    # 1. Scan Character References
    if workspace.char_ref_dir.exists():
        char_dirs = sorted([d for d in workspace.char_ref_dir.iterdir() if d.is_dir()], key=lambda d: d.name)
        for cdir in char_dirs:
            cname = cdir.name
            found_imgs = find_reference_images(cdir)
            cjson_path = cdir / "character.json"
            c_data: Dict[str, Any] = {}

            if cjson_path.exists():
                try:
                    with open(cjson_path, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                except Exception as e:
                    if verbose:
                        print(f"  Warning: Could not parse {cjson_path}: {e}", file=sys.stderr)

            if not c_data:
                c_data = {
                    "name": cname,
                    "role": "Character",
                    "visual_dna": f"Character {cname}",
                    "portrait_prompt": f"Concept portrait of {cname}",
                    "source": "collected"
                }

            c_data["images"] = found_imgs

            if found_imgs:
                new_dna, new_portrait, new_role = align_character_with_reference_images(
                    character_name=cname,
                    character_dir=cdir,
                    image_filenames=found_imgs,
                    current_data=c_data,
                    api_key=api_key,
                    model=model,
                    use_ai=use_ai,
                    verbose=verbose
                )
                c_data["visual_dna"] = new_dna
                c_data["portrait_prompt"] = new_portrait
                if new_role:
                    c_data["role"] = new_role

            if not dry_run:
                with open(cjson_path, "w", encoding="utf-8") as f:
                    json.dump(c_data, f, ensure_ascii=False, indent=2)

            characters_report.append(c_data)
            if verbose:
                status = f"{len(found_imgs)} image(s) -> {found_imgs}" if found_imgs else "no images found"
                print(f"  - Character '{cname}': {status}")
                if found_imgs:
                    dna_preview = c_data.get('visual_dna', '')[:80]
                    print(f"    Visual DNA     : {dna_preview}...")
                    prompt_preview = c_data.get('portrait_prompt', '')[:80]
                    print(f"    Portrait Prompt: {prompt_preview}...")

        # Update char-ref/characters.json
        if not dry_run and characters_report:
            with open(workspace.char_ref_dir / "characters.json", "w", encoding="utf-8") as f:
                json.dump({"characters": characters_report}, f, ensure_ascii=False, indent=2)
            if verbose:
                print(f"  -> Updated master index: {workspace.char_ref_dir / 'characters.json'}")

    # 2. Scan Style References
    if workspace.style_ref_dir.exists():
        style_imgs = find_reference_images(workspace.style_ref_dir)
        sjson_path = workspace.style_ref_dir / "style.json"
        s_data: Dict[str, Any] = {}

        if sjson_path.exists():
            try:
                with open(sjson_path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
            except Exception as e:
                if verbose:
                    print(f"  Warning: Could not parse {sjson_path}: {e}", file=sys.stderr)

        if not s_data:
            s_data = {
                "style_name": "Workspace Style",
                "style_prompt": "",
                "reference_prompt": "",
                "source": "collected"
            }

        s_data["images"] = style_imgs

        if style_imgs:
            new_sname, new_sprompt, new_rprompt = align_style_with_reference_images(
                style_dir=workspace.style_ref_dir,
                image_filenames=style_imgs,
                current_data=s_data,
                api_key=api_key,
                model=model,
                use_ai=use_ai,
                verbose=verbose
            )
            if new_sname:
                s_data["style_name"] = new_sname
            if new_sprompt:
                s_data["style_prompt"] = new_sprompt
            if new_rprompt:
                s_data["reference_prompt"] = new_rprompt

        if not dry_run:
            with open(sjson_path, "w", encoding="utf-8") as f:
                json.dump(s_data, f, ensure_ascii=False, indent=2)

        styles_report.append(s_data)
        if verbose:
            status = f"{len(style_imgs)} image(s) -> {style_imgs}" if style_imgs else "no images found"
            print(f"  - Style '{s_data.get('style_name', 'Style')}': {status}")
            if style_imgs:
                sprompt_preview = s_data.get('style_prompt', '')[:80]
                print(f"    Style Prompt   : {sprompt_preview}...")
            if not dry_run:
                print(f"  -> Updated style profile: {sjson_path}")

    report = {
        "workspace": str(workspace.workspace_dir),
        "stem": workspace.stem,
        "characters": characters_report,
        "styles": styles_report,
        "total_character_images": sum(len(c.get("images", [])) for c in characters_report),
        "total_style_images": sum(len(s.get("images", [])) for s in styles_report),
    }

    if verbose:
        action_desc = "Would collect and align" if dry_run else "Successfully collected and aligned"
        print(f"[storybook collect] {action_desc} {report['total_character_images']} character reference image(s) and {report['total_style_images']} style reference image(s).")

    return report


def resolve_workspaces_for_target(
    target: Optional[Union[str, Path]] = None,
    base_output_dir: Union[str, Path] = "outputs"
) -> List[StoryWorkspace]:
    """
    Resolve one or more StoryWorkspace instances based on target:
    - If target is a file (e.g. abc.md), returns workspace for that story.
    - If target is a workspace directory (e.g. outputs/abc), returns that workspace.
    - If target is a base directory (e.g. outputs) or None, discovers all workspaces in that directory.
    """
    base_out = Path(base_output_dir)
    if target:
        t_path = Path(target)
        # 1. Target is an existing or named markdown/text file
        if t_path.suffix.lower() in [".md", ".markdown", ".txt"] or (t_path.is_file()):
            return [StoryWorkspace(t_path, base_output_dir=base_out)]

        # 2. Target is an existing directory
        if t_path.is_dir():
            # Check if target is itself a storybook workspace
            if (t_path / "char-ref").exists() or (t_path / "style-ref").exists() or (t_path / "images").exists():
                return [StoryWorkspace(t_path.name, base_output_dir=t_path.parent)]

            # Target is a parent directory containing multiple workspaces
            sub_workspaces = []
            for sub in sorted(t_path.iterdir(), key=lambda x: x.name):
                if sub.is_dir() and ((sub / "char-ref").exists() or (sub / "style-ref").exists() or (sub / "images").exists()):
                    sub_workspaces.append(StoryWorkspace(sub.name, base_output_dir=t_path))
            if sub_workspaces:
                return sub_workspaces

            # If no subdirectories matched, treat target folder itself as the workspace
            return [StoryWorkspace(t_path.stem, base_output_dir=t_path.parent)]

        # 3. Target is a name or non-existent path: treat as story stem or file
        return [StoryWorkspace(target, base_output_dir=base_out)]

    # 4. No target specified: scan base_out
    if not base_out.exists():
        return []

    # Check if base_out is itself a workspace
    if (base_out / "char-ref").exists() or (base_out / "style-ref").exists():
        return [StoryWorkspace(base_out.name, base_output_dir=base_out.parent)]

    discovered = []
    for sub in sorted(base_out.iterdir(), key=lambda x: x.name):
        if sub.is_dir() and ((sub / "char-ref").exists() or (sub / "style-ref").exists() or (sub / "images").exists()):
            discovered.append(StoryWorkspace(sub.name, base_output_dir=base_out))

    return discovered


# ==============================================================================
# AI Media Asset Generation Engine
# ==============================================================================

def generate_media_assets(
    markdown_text: str,
    output_dir: Union[str, Path] = "outputs",
    media_type: str = "all",
    tag_id: Optional[str] = None,
    image_model: str = "gemini-3.1-flash-image",
    video_model: str = "veo-2.0-generate-001",
    aspect_ratio: str = "16:9",
    image_size: str = "1K",
    style_image: Optional[str] = None,
    style_prompt: Optional[str] = None,
    api_key: Optional[str] = None,
    dry_run: bool = False,
    verbose: bool = False,
    workspace: Optional[StoryWorkspace] = None
) -> Tuple[str, int]:
    """
    Extracts pending tags with prompts, generates image and video assets using Google GenAI / gemini-image.py,
    saves assets to workspace or output_dir, and links/refers them in the markdown.
    Returns: (updated_markdown_text, generated_count)
    """
    tags = extract_media_tags(markdown_text)
    if not tags:
        return markdown_text, 0

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if workspace:
        workspace.ensure_dirs()
        images_dir = workspace.images_dir
        videos_dir = workspace.videos_dir
    else:
        images_dir = out_path
        videos_dir = out_path

    # Filter target tags
    type_norm = media_type.lower()
    target_tags = []
    for t in tags:
        t_type = t.get("type", "image")
        t_id = t.get("id", "")
        if tag_id and t_id != tag_id:
            continue
        if type_norm in ["all", "both"] or t_type == type_norm or (type_norm == "image" and t_type == "image") or (type_norm == "video" and t_type == "video"):
            target_tags.append(t)

    if not target_tags:
        print("[storybook generate] No matching tags found to generate.")
        return markdown_text, 0

    # Auto-resolve style_prompt and style_image from workspace if available
    active_style_prompt = style_prompt
    active_style_image = style_image
    if workspace:
        style_json_file = workspace.style_ref_dir / "style.json"
        if not active_style_prompt and style_json_file.exists():
            try:
                with open(style_json_file, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    active_style_prompt = s_data.get("style_prompt")
            except Exception:
                pass
        if not active_style_image and workspace.style_ref_dir.exists():
            candidates = sorted(list(workspace.style_ref_dir.glob("*.png")) + list(workspace.style_ref_dir.glob("*.jpg")))
            if candidates:
                active_style_image = str(candidates[0])

    if dry_run:
        print(f"[storybook generate] DRY RUN: Found {len(target_tags)} media tag(s) to generate:")
        if active_style_prompt:
            print(f"  Applied Style Prompt: '{active_style_prompt}'")
        if active_style_image:
            print(f"  Applied Style Image : '{active_style_image}'")
        for t in target_tags:
            ext = ".png" if t.get("type") == "image" else ".mp4"
            target_file = (images_dir if t.get("type") == "image" else videos_dir) / f"{t.get('id', 'media')}{ext}"
            prompt_preview = t.get('prompt', '')[:60]
            engine = "via gemini-image.py" if t.get("type") == "image" else f"via {video_model}"
            print(f"  - [{t.get('type', 'media').upper()}] {t.get('id', '')}: '{prompt_preview}...' -> {target_file} ({engine})")
        return markdown_text, 0

    # Validate active_style_image if given
    if active_style_image and not Path(active_style_image).exists():
        print(f"Warning: Style image '{active_style_image}' does not exist.", file=sys.stderr)

    # Initialize Gemini client
    resolved_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not resolved_key:
        print("Error: Gemini API Key is required for media generation.", file=sys.stderr)
        print("Set GEMINI_API_KEY environment variable or pass --api-key.", file=sys.stderr)
        sys.exit(1)

    try:
        from google import genai
        client = genai.Client(api_key=resolved_key)
    except ImportError:
        client = None

    # Load character knowledge from workspace if available
    workspace_chars = []
    if workspace and (workspace.char_ref_dir / "characters.json").exists():
        try:
            with open(workspace.char_ref_dir / "characters.json", "r", encoding="utf-8") as f:
                c_idx = json.load(f)
                workspace_chars = c_idx.get("characters", [])
        except Exception:
            pass

    generated_count = 0
    replacements: List[Tuple[str, str]] = []

    for t in target_tags:
        t_type = t.get("type", "image")
        t_id = t.get("id") or f"media_{generated_count+1:03d}"
        prompt = t.get("prompt", "")
        sec = t.get("section") or t.get("title") or "Story scene"
        if not prompt:
            prompt = f"Storybook visual for '{sec}'"

        # Apply character visual DNA enhancement if matched
        effective_prompt = prompt
        matched_char_dna = []
        full_context = f"{sec} {prompt} {t.get('context_hint', '')}"
        for ch in workspace_chars:
            cname = ch.get("name", "")
            if cname and cname in full_context:
                cdna = ch.get("visual_dna", "")
                if cdna:
                    matched_char_dna.append(f"{cname} ({cdna})")
        if matched_char_dna:
            sep = " " if effective_prompt.endswith((".", "。", "!", "！")) else ". "
            effective_prompt = f"{effective_prompt}{sep}Character Visual Details: {'; '.join(matched_char_dna)}"

        # Apply style prompt modifier if provided
        if active_style_prompt:
            sep = " " if effective_prompt.endswith((".", "。", "!", "！")) else ". "
            effective_prompt = f"{effective_prompt}{sep}Art Style: {active_style_prompt.strip()}"

        if t_type == "image":
            target_file = images_dir / f"{t_id}.png"
            rel_asset = f"images/{t_id}.png" if workspace else str(target_file)
            print(f"[storybook generate] Generating image for {t_id} with gemini-image.py (model: {image_model})...")
            print(f"  Prompt: '{effective_prompt}'")
            if active_style_image:
                print(f"  Style Image: '{active_style_image}'")

            # Primary: Call gemini-image.py tool from image-craft
            gemini_script = find_gemini_image_script()
            image_generated = False

            if gemini_script and gemini_script.exists():
                cmd = [
                    sys.executable,
                    str(gemini_script),
                    effective_prompt,
                    "-o", str(target_file),
                    "-m", image_model,
                    "-r", aspect_ratio,
                    "-s", image_size,
                ]
                if active_style_image and Path(active_style_image).exists():
                    cmd.extend(["-i", str(Path(active_style_image).resolve())])
                if resolved_key:
                    cmd.extend(["--api-key", resolved_key])

                try:
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode != 0:
                        print(f"  Error from gemini-image: {res.stderr.strip()}", file=sys.stderr)
                    else:
                        if target_file.exists():
                            image_generated = True
                        else:
                            print(f"  Warning: gemini-image exited with 0 but {target_file} was not found.", file=sys.stderr)
                except Exception as e:
                    print(f"  Error invoking gemini-image: {e}", file=sys.stderr)

            # Fallback: Direct Google GenAI call if script is missing
            if not image_generated and client:
                try:
                    print(f"  Falling back to direct Google GenAI client for {t_id}...")
                    if "imagen" in image_model.lower():
                        cfg = {"output_mime_type": "image/png"}
                        if aspect_ratio:
                            cfg["aspect_ratio"] = aspect_ratio
                        res = client.models.generate_images(model=image_model, prompt=effective_prompt, config=cfg)
                        if hasattr(res, "generated_images") and res.generated_images:
                            img_bytes = res.generated_images[0].image.image_bytes
                            with open(target_file, "wb") as f:
                                f.write(img_bytes)
                            image_generated = True
                    else:
                        input_payload = []
                        if active_style_image and Path(active_style_image).exists():
                            try:
                                with open(active_style_image, "rb") as sif:
                                    sb64 = base64.b64encode(sif.read()).decode("utf-8")
                                mime_t, _ = mimetypes.guess_type(active_style_image)
                                input_payload.append({
                                    "type": "image",
                                    "data": sb64,
                                    "mime_type": mime_t or "image/png"
                                })
                            except Exception:
                                pass
                        input_payload.append({"type": "text", "text": effective_prompt})

                        resp_format = {"type": "image", "mime_type": "image/jpeg"}
                        if aspect_ratio:
                            resp_format["aspect_ratio"] = aspect_ratio
                        if image_size:
                            resp_format["image_size"] = image_size

                        interaction = client.interactions.create(
                            model=image_model,
                            input=input_payload if len(input_payload) > 1 else effective_prompt,
                            response_format=resp_format
                        )
                        extracted_bytes = None
                        if hasattr(interaction, "steps"):
                            for step in interaction.steps:
                                if getattr(step, "type", None) == "model_output":
                                    for block in getattr(step, "content", []):
                                        if getattr(block, "type", None) == "image" and hasattr(block, "data"):
                                            extracted_bytes = base64.b64decode(block.data)
                                            break
                        if not extracted_bytes and hasattr(interaction, "output_image") and interaction.output_image:
                            extracted_bytes = base64.b64decode(interaction.output_image.data)

                        if extracted_bytes:
                            try:
                                from PIL import Image
                                import io
                                img = Image.open(io.BytesIO(extracted_bytes))
                                img.save(target_file, format="PNG")
                            except Exception:
                                with open(target_file, "wb") as f:
                                    f.write(extracted_bytes)
                            image_generated = True
                except Exception as e:
                    print(f"  Error in direct GenAI fallback for {t_id}: {e}", file=sys.stderr)

            if image_generated:
                print(f"  -> Saved asset: {target_file}")
                t["asset"] = rel_asset
                t["status"] = "generated"
                generated_count += 1
                new_tag = format_tag(t, tag_format=t.get("_format", "json-comment"))

                # Reference images in markdown
                if workspace:
                    md_embed = f"\n\n![{t_id}]({rel_asset})"
                    raw_tag = t.get("_raw_tag", "")
                    idx = markdown_text.find(raw_tag)
                    after_tag = markdown_text[idx + len(raw_tag): idx + len(raw_tag) + 120] if idx != -1 else ""
                    if rel_asset in after_tag or f"[{t_id}]" in after_tag:
                        replacement_chunk = new_tag
                    else:
                        replacement_chunk = f"{new_tag}{md_embed}"
                else:
                    replacement_chunk = new_tag

                replacements.append((t.get("_raw_tag", ""), replacement_chunk))
            else:
                print(f"  Failed to generate image asset for {t_id}.", file=sys.stderr)

        elif t_type == "video":
            target_file = videos_dir / f"{t_id}.mp4"
            rel_asset = f"videos/{t_id}.mp4" if workspace else str(target_file)
            print(f"[storybook generate] Requesting video generation for {t_id} with {video_model}...")
            print(f"  Prompt: '{effective_prompt}'")
            if active_style_image:
                print(f"  Style Image: '{active_style_image}'")
            try:
                # Video generation via Google GenAI Veo
                video_kwargs = {
                    "model": video_model,
                    "prompt": effective_prompt
                }
                if active_style_image and Path(active_style_image).exists():
                    try:
                        with open(active_style_image, "rb") as sif:
                            img_data = sif.read()
                        from google.genai import types
                        video_kwargs["image"] = types.Image(image_bytes=img_data)
                    except Exception:
                        pass
                op = client.models.generate_videos(**video_kwargs)
                print(f"  -> Video operation submitted: {op}")
                t["asset"] = rel_asset
                t["status"] = "generating"
                generated_count += 1
                new_tag = format_tag(t, tag_format=t.get("_format", "json-comment"))

                if workspace:
                    md_embed = f'\n\n<video src="{rel_asset}" controls></video>'
                    raw_tag = t.get("_raw_tag", "")
                    idx = markdown_text.find(raw_tag)
                    after_tag = markdown_text[idx + len(raw_tag): idx + len(raw_tag) + 120] if idx != -1 else ""
                    if rel_asset in after_tag or f"src=\"{rel_asset}\"" in after_tag:
                        replacement_chunk = new_tag
                    else:
                        replacement_chunk = f"{new_tag}{md_embed}"
                else:
                    replacement_chunk = new_tag

                replacements.append((t.get("_raw_tag", ""), replacement_chunk))
            except Exception as e:
                print(f"  Note: Video generation not available or error: {e}", file=sys.stderr)

    updated_text = markdown_text
    for old_raw, new_raw in replacements:
        if old_raw and new_raw:
            updated_text = updated_text.replace(old_raw, new_raw, 1)

    return updated_text, generated_count


# ==============================================================================
# Story Content Creation Scaffold
# ==============================================================================

def create_story_content(
    prompt: str,
    output_path: Optional[str] = None,
    genre: Optional[str] = None,
    chapters: int = 3,
    api_key: Optional[str] = None
) -> str:
    """
    Scaffold for 'create' command.
    Acknowledge the prompt and prepare story content for upcoming full generation milestone.
    """
    print("=" * 60)
    print("Storybook Creator")
    print("=" * 60)
    print(f"  Prompt   : {prompt}")
    if genre:
        print(f"  Genre    : {genre}")
    print(f"  Chapters : {chapters}")
    if output_path:
        print(f"  Target   : {output_path}")
    print("=" * 60)
    print("[storybook create] Story content generation is scheduled for implementation.")
    print("For now, you can craft, tag, prompt, and generate media on any Markdown story:")
    print("  python storybook.py media <story.md>")

    # Scaffold Markdown template based on the prompt
    scaffold = f"""# {prompt}

---
title: "{prompt}"
status: draft
genre: "{genre or 'General'}"
---

# 第一章 旅程的开端

很久很久以前，在未知的大陆上，一段关于“{prompt}”的故事悄然拉开序幕。微风轻抚过古老的林间大道，阳光在绿叶上跳跃着斑驳的影子。

小小的脚步声打破了清晨的宁静，怀揣着梦想与好奇，主角踏上了这片充满奇遇与神秘色彩的土地。

# 第二章 意料之外的相遇

旅途逐渐深入未知的秘境，薄雾中若隐若现地浮现出一座古老的石拱桥。桥边静静伫立着一尊生满青苔的守护者石雕。

突然，一阵奇异的微光从石雕的眼眸中闪烁而起，空气中荡漾起前所未有的魔力波动。

# 第三章 归途与新的曙光

经历了一番惊险而奇妙的历险，黎明再次破晓。金色的晨曦洒满大地，映照出心中坚定的信念与勇气。

新的故事篇章已然启程，而这仅仅是一个伟大传奇的美好开端。
"""
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(scaffold)
        print(f"[storybook create] Created initial story scaffold draft at: {output_path}")

    return scaffold


# ==============================================================================
# Built-in Test Suite
# ==============================================================================

class TestStorybook(unittest.TestCase):

    def setUp(self):
        self.p1 = "很久很久以前，在群山环抱的一片古老森林里，住着一个名叫小明的年轻冒险家。小明从小就对大自然充满了无限的好奇，他总是喜欢背着自制的小布包，穿梭在郁郁葱葱的林间小道上，寻找那些隐藏在树根和岩石缝隙中的奇妙小生物。"
        self.p2 = "清晨的第一缕阳光穿透薄雾，将金色的光斑洒在潮湿的苔藓上。小明沿着一条熟悉的小溪缓缓向前走去，水流撞击着光滑的鹅卵石，发出悦耳的叮咚声。就在这时，小溪对岸的一道奇异蓝光吸引了他的注意，那是一团漂浮的光芒。"
        self.p3 = "小明小心翼翼地踩着溪流中的垫脚石跨过小溪。走近一看，那竟然是一只通体透明、散发着幽蓝荧光的小精灵。小精灵有着薄如蝉翼的翅膀，正悬停在一朵盛开的七彩野花上方，似乎在焦急地寻找着昨夜暴风雨中遗失的钥匙。"
        self.story_md = f"""# 魔法森林历险记

# 第一章 魔法森林

{self.p1}

{self.p2}

{self.p3}

# 第二章 神殿钥匙

{self.p1}

{self.p2}
"""

    def test_cjk_counting(self):
        text = "这是一个用来测试中文字数统计的简单句子。"
        total, cjk, words = count_story_units(text)
        self.assertEqual(cjk, 20)
        self.assertEqual(words, 0)
        self.assertEqual(total, 20)

    def test_english_counting(self):
        text = "The quick brown fox jumps over the lazy dog."
        total, cjk, words = count_story_units(text)
        self.assertEqual(cjk, 0)
        self.assertEqual(words, 9)
        self.assertEqual(total, 9)

    def test_video_tag_under_h1(self):
        result = insert_media_tags(self.story_md, media_types=["video"])
        tags = extract_media_tags(result)
        video_tags = [t for t in tags if t.get("type") == "video"]
        self.assertEqual(len(video_tags), 2)
        self.assertEqual(video_tags[0]["id"], "vid_001")
        self.assertEqual(video_tags[0]["title"], "第一章 魔法森林")

    def test_image_gap_and_first_insert(self):
        result = insert_media_tags(self.story_md, media_types=["image"], image_gap=200, first_insert=True)
        tags = extract_media_tags(result)
        image_tags = [t for t in tags if t.get("type") == "image"]
        self.assertEqual(len(image_tags), 3)

    def test_prompt_update(self):
        # Insert tags without prompts first
        tagged = insert_media_tags(self.story_md, media_types=["all"], generate_prompts=False)
        tags_before = extract_media_tags(tagged)
        for t in tags_before:
            self.assertEqual(t.get("prompt", ""), "")
        # Update prompts
        prompted = update_media_tag_prompts(tagged, force=True)
        tags_after = extract_media_tags(prompted)
        for t in tags_after:
            self.assertNotEqual(t.get("prompt", ""), "")

    def test_media_generate_dry_run(self):
        tagged = insert_media_tags(self.story_md, media_types=["image"], generate_prompts=True)
        updated, count = generate_media_assets(tagged, dry_run=True)
        self.assertEqual(count, 0)

    def test_media_generate_with_style(self):
        tagged = insert_media_tags(self.story_md, media_types=["all"], generate_prompts=True)
        updated, count = generate_media_assets(
            tagged,
            style_prompt="watercolor pastel art",
            style_image="examples/nonexistent_style.png",
            dry_run=True
        )
        self.assertEqual(count, 0)

    def test_clean_tags(self):
        tagged = insert_media_tags(self.story_md, media_types=["all"])
        cleaned = remove_media_tags(tagged)
        self.assertEqual(len(extract_media_tags(cleaned)), 0)

    def test_mixed_counting(self):
        text = "小明有 3 本 books 和 2 个 apples。"
        total, cjk, words = count_story_units(text)
        self.assertEqual(cjk, 7)
        self.assertEqual(words, 4)
        self.assertEqual(total, 11)

    def test_strip_markdown_syntax(self):
        text = "## 标题\n**加粗文字** 与 *斜体* 以及 [链接文本](https://example.com) 和 `代码`"
        total, cjk, words = count_story_units(text)
        self.assertEqual(cjk, 18)

    def test_split_frontmatter_and_headings(self):
        doc = """---
title: My Story
author: Test
---

# Chapter 1: Introduction

This is the first paragraph.

## Section 1.1

Another paragraph here.
"""
        blocks = split_markdown_into_blocks(doc)
        types = [b.block_type for b in blocks if b.block_type != MarkdownBlock.TYPE_BLANK]
        self.assertEqual(types, [
            MarkdownBlock.TYPE_FRONTMATTER,
            MarkdownBlock.TYPE_H1,
            MarkdownBlock.TYPE_PARAGRAPH,
            MarkdownBlock.TYPE_HEADING,
            MarkdownBlock.TYPE_PARAGRAPH
        ])

    def test_no_first_insert(self):
        result = insert_media_tags(self.story_md, media_types=["image"], image_gap=200, first_insert=False)
        tags = extract_media_tags(result)
        image_tags = [t for t in tags if t.get("type") == "image"]
        self.assertEqual(len(image_tags), 2)
        self.assertEqual(image_tags[0]["id"], "img_001")
        self.assertEqual(image_tags[1]["id"], "img_002")

    def test_both_image_and_video(self):
        result = insert_media_tags(self.story_md, media_types=["all"], image_gap=200)
        tags = extract_media_tags(result)
        vids = [t for t in tags if t.get("type") == "video"]
        imgs = [t for t in tags if t.get("type") == "image"]
        self.assertEqual(len(vids), 2)
        self.assertEqual(len(imgs), 3)

    def test_tag_formats(self):
        res_json = insert_media_tags(self.story_md, media_types=["image"], tag_format="json-comment")
        self.assertIn("<!-- storybook-media: {", res_json)
        self.assertGreater(len(extract_media_tags(res_json)), 0)

        res_kv = insert_media_tags(self.story_md, media_types=["image"], tag_format="kv-comment")
        self.assertIn('<!-- storybook-media type="image"', res_kv)
        self.assertGreater(len(extract_media_tags(res_kv)), 0)

        res_vis = insert_media_tags(self.story_md, media_types=["image"], tag_format="visible")
        self.assertIn('> 🎨 **[Media: image', res_vis)
        self.assertGreater(len(extract_media_tags(res_vis)), 0)

    def test_remove_markdown_media(self):
        doc = """# 序章

![Image](https://example.com/pic1.png)

这是一段故事正文。

<img src="https://example.com/pic2.jpg" alt="test" />

<video src="https://example.com/vid.mp4"></video>

这是另一段正文。
"""
        cleaned_all = remove_markdown_media(doc, "all")
        self.assertNotIn("https://example.com/pic1.png", cleaned_all)
        self.assertNotIn("https://example.com/pic2.jpg", cleaned_all)
        self.assertNotIn("https://example.com/vid.mp4", cleaned_all)
        self.assertIn("这是一段故事正文。", cleaned_all)

        cleaned_img = remove_markdown_media(doc, "image")
        self.assertNotIn("pic1.png", cleaned_img)
        self.assertIn("<video", cleaned_img)

        cleaned_vid = remove_markdown_media(doc, "video")
        self.assertIn("pic1.png", cleaned_vid)
        self.assertNotIn("<video", cleaned_vid)

    def test_stats(self):
        stats = get_storybook_stats(self.story_md)
        self.assertEqual(stats["h1_headings"], 3)
        self.assertEqual(stats["paragraphs"], 5)
        self.assertGreater(stats["cjk_characters"], 500)

    def test_create_scaffold(self):
        scaffold = create_story_content("测试故事", chapters=3)
        self.assertIn("# 测试故事", scaffold)
        self.assertIn("第一章", scaffold)

    def test_story_workspace_structure(self):
        ws = StoryWorkspace("abc.md", base_output_dir="outputs")
        self.assertEqual(ws.stem, "abc")
        self.assertEqual(ws.workspace_dir, Path("outputs/abc"))
        self.assertEqual(ws.output_md, Path("outputs/abc/abc-output.md"))
        self.assertEqual(ws.images_dir, Path("outputs/abc/images"))
        self.assertEqual(ws.videos_dir, Path("outputs/abc/videos"))
        self.assertEqual(ws.char_ref_dir, Path("outputs/abc/char-ref"))
        self.assertEqual(ws.style_ref_dir, Path("outputs/abc/style-ref"))

        char_a_dir = ws.get_char_dir("A")
        self.assertEqual(char_a_dir, Path("outputs/abc/char-ref/A"))

        rel_img = ws.get_relative_asset_path(ws.images_dir / "img_001.png")
        self.assertEqual(rel_img, "images/img_001.png")

        rel_vid = ws.get_relative_asset_path(ws.videos_dir / "vid_001.mp4")
        self.assertEqual(rel_vid, "videos/vid_001.mp4")

    def test_parse_char_refs_arg(self):
        # 1. Comma-separated single string
        res1 = parse_char_refs_arg(["A:XX.png, A:YY.png, B:ZZ.png"])
        self.assertEqual(res1, {"A": ["XX.png", "YY.png"], "B": ["ZZ.png"]})

        # 2. Multiple arguments
        res2 = parse_char_refs_arg(["A:XX.png", "B:ZZ.png", "C:WW.png"])
        self.assertEqual(res2, {"A": ["XX.png"], "B": ["ZZ.png"], "C": ["WW.png"]})

        # 3. Space-separated within string
        res3 = parse_char_refs_arg(["A:XX.png B:ZZ.png"])
        self.assertEqual(res3, {"A": ["XX.png"], "B": ["ZZ.png"]})

    def test_parse_style_refs_arg(self):
        res1 = parse_style_refs_arg(["XX.png, YY.png, ZZ.png"])
        self.assertEqual(res1, ["XX.png", "YY.png", "ZZ.png"])

        res2 = parse_style_refs_arg(["XX.png", "YY.png"])
        self.assertEqual(res2, ["XX.png", "YY.png"])

    def test_extract_characters_and_style(self):
        chars = extract_characters_from_story(self.story_md)
        self.assertGreater(len(chars), 0)
        char_names = [c["name"] for c in chars]
        self.assertIn("小明", char_names)

        style = extract_style_from_story(self.story_md)
        self.assertIn("style_name", style)
        self.assertIn("style_prompt", style)
        self.assertIn("reference_prompt", style)

    def test_setup_workspace_assets_dry_run(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = StoryWorkspace("test_story.md", base_output_dir=tmp_dir)
            report = setup_workspace_assets(
                workspace=ws,
                markdown_text=self.story_md,
                char_refs_arg={"A": ["test1.png"], "B": ["test2.png"]},
                style_refs_arg=["style1.png"],
                dry_run=True,
                verbose=False
            )
            self.assertEqual(len(report["characters"]), 2)
            self.assertEqual(len(report["styles"]), 1)

    def test_natural_sort_and_find_reference_images(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            td = Path(tmp_dir)
            filenames = [
                "ref_010.png",
                "ref_002.png",
                "ref_001.png",
                "ref_003.jpg",
                "custom_portrait.webp",
                "notes.txt",
                "character.json"
            ]
            for fn in filenames:
                (td / fn).write_text("dummy", encoding="utf-8")

            discovered = find_reference_images(td)
            expected = [
                "ref_001.png",
                "ref_002.png",
                "ref_003.jpg",
                "ref_010.png",
                "custom_portrait.webp"
            ]
            self.assertEqual(discovered, expected)

    def test_setup_workspace_assets_default_no_image_generation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = StoryWorkspace("test_scaffold.md", base_output_dir=tmp_dir)
            report = setup_workspace_assets(
                workspace=ws,
                markdown_text=self.story_md,
                generate_images=False,
                dry_run=False,
                verbose=False
            )
            # Directories exist
            self.assertTrue(ws.images_dir.exists())
            self.assertTrue(ws.videos_dir.exists())
            self.assertTrue(ws.char_ref_dir.exists())
            self.assertTrue(ws.style_ref_dir.exists())

            # JSON metadata files exist
            self.assertTrue((ws.char_ref_dir / "characters.json").exists())
            self.assertTrue((ws.style_ref_dir / "style.json").exists())

            # But NO image files generated!
            all_pngs = list(ws.workspace_dir.rglob("*.png"))
            self.assertEqual(len(all_pngs), 0)

            # Metadata lists empty images
            for c in report["characters"]:
                self.assertEqual(c["images"], [])
            for s in report["styles"]:
                self.assertEqual(s["images"], [])

    def test_collect_workspace_assets(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = StoryWorkspace("collect_test.md", base_output_dir=tmp_dir)
            # 1. First scaffold workspace without generating images
            setup_workspace_assets(
                workspace=ws,
                markdown_text=self.story_md,
                generate_images=False,
                dry_run=False,
                verbose=False
            )

            # 2. User places reference images in character and style folders
            char_a_dir = ws.get_char_dir("小明")
            (char_a_dir / "ref_002.png").write_text("img2", encoding="utf-8")
            (char_a_dir / "ref_001.png").write_text("img1", encoding="utf-8")
            (ws.style_ref_dir / "ref_001.png").write_text("style_img", encoding="utf-8")

            # 3. Run collect_workspace_assets
            collect_report = collect_workspace_assets(ws, dry_run=False, verbose=False)

            self.assertEqual(collect_report["total_character_images"], 2)
            self.assertEqual(collect_report["total_style_images"], 1)

            # Verify character.json was updated with images AND aligned visual_dna + portrait_prompt
            with open(char_a_dir / "character.json", "r", encoding="utf-8") as f:
                c_data = json.load(f)
            self.assertEqual(c_data["images"], ["ref_001.png", "ref_002.png"])
            self.assertIn("ref_001.png", c_data["visual_dna"])
            self.assertIn("ref_002.png", c_data["visual_dna"])
            self.assertIn("ref_001.png", c_data["portrait_prompt"])
            self.assertIn("ref_002.png", c_data["portrait_prompt"])

            # Verify master characters.json was updated
            with open(ws.char_ref_dir / "characters.json", "r", encoding="utf-8") as f:
                idx_data = json.load(f)
            char_entry = next((c for c in idx_data["characters"] if c["name"] == "小明"), None)
            self.assertIsNotNone(char_entry)
            self.assertEqual(char_entry["images"], ["ref_001.png", "ref_002.png"])
            self.assertIn("ref_001.png", char_entry["visual_dna"])
            self.assertIn("ref_002.png", char_entry["visual_dna"])
            self.assertIn("ref_001.png", char_entry["portrait_prompt"])
            self.assertIn("ref_002.png", char_entry["portrait_prompt"])

            # Verify style.json was updated with images AND aligned style_prompt
            with open(ws.style_ref_dir / "style.json", "r", encoding="utf-8") as f:
                s_data = json.load(f)
            self.assertEqual(s_data["images"], ["ref_001.png"])
            self.assertIn("ref_001.png", s_data["style_prompt"])

    def test_collect_workspace_assets_dry_run(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = StoryWorkspace("collect_dry.md", base_output_dir=tmp_dir)
            setup_workspace_assets(
                workspace=ws,
                markdown_text=self.story_md,
                generate_images=False,
                dry_run=False,
                verbose=False
            )
            char_dir = ws.get_char_dir("小明")
            (char_dir / "ref_001.png").write_text("img", encoding="utf-8")

            # Dry run collect
            report = collect_workspace_assets(ws, dry_run=True, verbose=False)
            self.assertEqual(report["total_character_images"], 1)

            # File on disk should still have original empty images list
            with open(char_dir / "character.json", "r", encoding="utf-8") as f:
                c_data = json.load(f)
            self.assertEqual(c_data["images"], [])

    def test_resolve_workspaces_for_target(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            td = Path(tmp_dir)
            ws1 = StoryWorkspace("story1.md", base_output_dir=td)
            ws1.ensure_dirs()
            ws2 = StoryWorkspace("story2.md", base_output_dir=td)
            ws2.ensure_dirs()

            # Target as file
            res1 = resolve_workspaces_for_target("story1.md", base_output_dir=td)
            self.assertEqual(len(res1), 1)
            self.assertEqual(res1[0].stem, "story1")

            # Target as directory
            res2 = resolve_workspaces_for_target(str(ws1.workspace_dir), base_output_dir=td)
            self.assertEqual(len(res2), 1)
            self.assertEqual(res2[0].stem, "story1")

            # Target as None (scans base_output_dir)
            res_all = resolve_workspaces_for_target(None, base_output_dir=td)
            self.assertEqual(len(res_all), 2)
            stems = sorted([w.stem for w in res_all])
            self.assertEqual(stems, ["story1", "story2"])



# ==============================================================================
# CLI Parsers & Main Dispatcher
# ==============================================================================

def read_input_content(input_path: Optional[str]) -> str:
    if input_path and input_path != "-":
        p = Path(input_path)
        if not p.exists():
            print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
            sys.exit(1)
        try:
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading '{input_path}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if sys.stdin.isatty() and not input_path:
            print("storybook: Reading from stdin (press Ctrl+D when finished)...", file=sys.stderr)
        return sys.stdin.read()


def write_output_content(content: str, output_path: Optional[str], input_path: Optional[str], in_place: bool):
    if in_place and input_path and input_path != "-":
        with open(input_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Successfully updated in-place: {input_path}")
    elif output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Successfully wrote output to {output_path}")
    else:
        sys.stdout.write(content)


def main():
    parser = argparse.ArgumentParser(
        prog="storybook",
        description="Storybook Craft: Story content generator and visual media pipeline.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # --------------------------------------------------------------------------
    # 1. 'create' command
    # --------------------------------------------------------------------------
    p_create = subparsers.add_parser(
        "create",
        help="Create story content from prompt (scaffold/draft)."
    )
    p_create.add_argument("prompt", help="Story idea, concept, or prompt.")
    p_create.add_argument("-o", "--output", help="Target markdown file path.")
    p_create.add_argument("--genre", help="Story genre (e.g. fantasy, bedtime, adventure).")
    p_create.add_argument("--chapters", type=int, default=3, help="Number of chapters (default: 3).")

    # --------------------------------------------------------------------------
    # 2. 'media' command
    # --------------------------------------------------------------------------
    p_media = subparsers.add_parser(
        "media",
        help="Visual media pipeline (end-to-end tag + prompt + generate, or specific subactions)."
    )
    media_sub = p_media.add_subparsers(dest="media_action", help="Media subaction")

    # Add shared arguments function for media subcommands
    def add_common_media_args(subp):
        subp.add_argument("input_file", nargs="?", default=None, help="Input markdown file.")
        subp.add_argument("-o", "--output", help="Output file path.")
        subp.add_argument("-w", "--in-place", action="store_true", help="Modify input file in-place.")

    # 2.1 media tag
    p_m_tag = media_sub.add_parser("tag", help="Insert visual media tags into markdown.")
    add_common_media_args(p_m_tag)
    p_m_tag.add_argument("-t", "--type", dest="media_types", action="append", choices=SUPPORTED_TYPES, help="Media type(s): image, video, all (default: all).")
    p_m_tag.add_argument("-g", "--gap", type=int, default=DEFAULT_IMAGE_GAP, help=f"Character interval between images (default: {DEFAULT_IMAGE_GAP}).")
    p_m_tag.add_argument("--first-insert", dest="first_insert", action="store_true", default=True, help="Insert opening image on 1st paragraph (default: True).")
    p_m_tag.add_argument("--no-first-insert", dest="first_insert", action="store_false", help="Do not force opening image.")
    p_m_tag.add_argument("--first-insert-pos", choices=["after-first-paragraph", "at-story-start"], default="after-first-paragraph")
    p_m_tag.add_argument("--reset-on-h1", action="store_true", help="Reset image character counter on each Level 1 heading.")
    p_m_tag.add_argument("--format", dest="tag_format", choices=SUPPORTED_FORMATS, default="json-comment")
    p_m_tag.add_argument("-c", "--clean-media", nargs="?", const="all", choices=["image", "video", "all"], help="Clean existing markdown media first.")

    # 2.2 media prompt
    p_m_prompt = media_sub.add_parser("prompt", help="Generate/enrich prompts for media tags from narrative context.")
    add_common_media_args(p_m_prompt)
    p_m_prompt.add_argument("--force", action="store_true", help="Overwrite existing tag prompts.")
    p_m_prompt.add_argument("--ai", action="store_true", help="Use Gemini AI to enhance visual prompts.")
    p_m_prompt.add_argument("--api-key", help="Gemini API key.")

    # 2.3 media generate
    p_m_gen = media_sub.add_parser("generate", help="Generate AI images/videos for media tags.")
    add_common_media_args(p_m_gen)
    p_m_gen.add_argument("-t", "--type", default="all", choices=["image", "video", "all"], help="Media type to generate (default: all).")
    p_m_gen.add_argument("--id", dest="tag_id", help="Target specific tag ID (e.g. img_001).")
    p_m_gen.add_argument("--output-dir", default="outputs", help="Directory to save media assets (default: outputs).")
    p_m_gen.add_argument("-m", "--model", default="gemini-3.1-flash-image", help="Image model (default: gemini-3.1-flash-image).")
    p_m_gen.add_argument("--video-model", default="veo-2.0-generate-001", help="Video model (default: veo-2.0-generate-001).")
    p_m_gen.add_argument("-r", "--ratio", default="16:9", help="Aspect ratio (default: 16:9).")
    p_m_gen.add_argument("-s", "--size", default="1K", help="Image resolution size (default: 1K).")
    p_m_gen.add_argument("--style-image", dest="style_image", help="Path to reference image file for visual style.")
    p_m_gen.add_argument("--style-prompt", dest="style_prompt", help="Text prompt specifying the visual art style.")
    p_m_gen.add_argument("--char-refs", "--char-ref", dest="char_refs", action="append", help="Character reference mapping: Name:image_path, ...")
    p_m_gen.add_argument("--style-ref", "--style-refs", dest="style_refs", action="append", help="Style reference image(s): image1.png, image2.png, ...")
    p_m_gen.add_argument("--api-key", help="Gemini API key.")
    p_m_gen.add_argument("--dry-run", action="store_true", help="Preview tags and output files without generating.")

    # 2.4 media clean
    p_m_clean = media_sub.add_parser("clean", help="Remove all storybook media tags from markdown.")
    add_common_media_args(p_m_clean)

    # 2.5 media stats
    p_m_stats = media_sub.add_parser("stats", help="Display story metrics and media tag summary.")
    p_m_stats.add_argument("input_file", nargs="?", default=None, help="Input markdown file.")

    # 2.6 media extract
    p_m_ext = media_sub.add_parser("extract", help="Extract media tags as structured JSON.")
    add_common_media_args(p_m_ext)

    # 2.7 media pipeline (default full pipeline)
    p_m_pipe = media_sub.add_parser("pipeline", help="Run full media pipeline (tag -> prompt -> generate).")
    add_common_media_args(p_m_pipe)
    p_m_pipe.add_argument("-t", "--type", dest="media_types", action="append", choices=SUPPORTED_TYPES, help="Media type(s): image, video, all (default: all).")
    p_m_pipe.add_argument("-g", "--gap", type=int, default=DEFAULT_IMAGE_GAP, help="Character interval between images.")
    p_m_pipe.add_argument("--output-dir", default="outputs", help="Directory for generated media assets.")
    p_m_pipe.add_argument("-m", "--model", default="gemini-3.1-flash-image", help="Image generation model.")
    p_m_pipe.add_argument("-r", "--ratio", default="16:9", help="Aspect ratio.")
    p_m_pipe.add_argument("-s", "--size", default="1K", help="Resolution.")
    p_m_pipe.add_argument("--style-image", dest="style_image", help="Path to reference image file for visual style.")
    p_m_pipe.add_argument("--style-prompt", dest="style_prompt", help="Text prompt specifying the visual art style.")
    p_m_pipe.add_argument("--char-refs", "--char-ref", dest="char_refs", action="append", help="Character reference mapping: Name:image_path, ...")
    p_m_pipe.add_argument("--style-ref", "--style-refs", dest="style_refs", action="append", help="Style reference image(s): image1.png, image2.png, ...")
    p_m_pipe.add_argument("--api-key", help="Gemini API key.")
    p_m_pipe.add_argument("--dry-run", action="store_true", help="Dry run asset generation.")
    p_m_pipe.add_argument("-c", "--clean-media", nargs="?", const="all", choices=["image", "video", "all"], help="Clean existing markdown media first.")

    # --------------------------------------------------------------------------
    # 3. 'assets' command
    # --------------------------------------------------------------------------
    p_assets = subparsers.add_parser(
        "assets",
        help="Manage story workspace reference assets (characters and style)."
    )
    p_assets.add_argument("input_file", nargs="?", default=None, help="Input markdown file.")
    p_assets.add_argument("-g", "--generate", action="store_true", help="Generate AI reference images for extracted characters and styles (default: only scaffold structure and JSON metadata).")
    p_assets.add_argument("--char-refs", "--char-ref", dest="char_refs", action="append", help="Character reference mapping: Name:image_path, ...")
    p_assets.add_argument("--style-ref", "--style-refs", dest="style_refs", action="append", help="Style reference image(s): image1.png, image2.png, ...")
    p_assets.add_argument("--style-prompt", help="Visual art style prompt.")
    p_assets.add_argument("--output-dir", default="outputs", help="Base output directory (default: outputs).")
    p_assets.add_argument("-m", "--model", default="gemini-3.1-flash-image", help="Image generation model.")
    p_assets.add_argument("--api-key", help="Gemini API key.")
    p_assets.add_argument("--force", action="store_true", help="Force re-extract/regenerate reference assets.")
    p_assets.add_argument("--dry-run", action="store_true", help="Preview asset extraction without generating files.")

    # --------------------------------------------------------------------------
    # 4. 'char-ref' command
    # --------------------------------------------------------------------------
    p_char_ref = subparsers.add_parser(
        "char-ref",
        help="Manage character references (auto-extract or import)."
    )
    p_char_ref.add_argument("input_file", nargs="?", default=None, help="Input markdown file.")
    p_char_ref.add_argument("-g", "--generate", action="store_true", help="Generate AI portrait reference images for extracted characters.")
    p_char_ref.add_argument("--char-refs", "--char-ref", dest="char_refs", action="append", help="Character reference mapping: Name:image_path, ...")
    p_char_ref.add_argument("--output-dir", default="outputs", help="Base output directory (default: outputs).")
    p_char_ref.add_argument("-m", "--model", default="gemini-3.1-flash-image", help="Image generation model.")
    p_char_ref.add_argument("--api-key", help="Gemini API key.")
    p_char_ref.add_argument("--force", action="store_true", help="Force re-extract/regenerate character references.")
    p_char_ref.add_argument("--dry-run", action="store_true", help="Preview character extraction without generating files.")

    # --------------------------------------------------------------------------
    # 5. 'style-ref' command
    # --------------------------------------------------------------------------
    p_style_ref = subparsers.add_parser(
        "style-ref",
        help="Manage style references (auto-extract or import)."
    )
    p_style_ref.add_argument("input_file", nargs="?", default=None, help="Input markdown file.")
    p_style_ref.add_argument("-g", "--generate", action="store_true", help="Generate AI style reference image for extracted style.")
    p_style_ref.add_argument("--style-ref", "--style-refs", dest="style_refs", action="append", help="Style reference image(s): image1.png, image2.png, ...")
    p_style_ref.add_argument("--style-prompt", help="Visual art style prompt.")
    p_style_ref.add_argument("--output-dir", default="outputs", help="Base output directory (default: outputs).")
    p_style_ref.add_argument("-m", "--model", default="gemini-3.1-flash-image", help="Image generation model.")
    p_style_ref.add_argument("--api-key", help="Gemini API key.")
    p_style_ref.add_argument("--force", action="store_true", help="Force re-extract/regenerate style references.")
    p_style_ref.add_argument("--dry-run", action="store_true", help="Preview style extraction without generating files.")

    # --------------------------------------------------------------------------
    # 6. 'collect' command (and 'storybook assets collect')
    # --------------------------------------------------------------------------
    p_collect = subparsers.add_parser(
        "collect",
        help="Scan workspace for reference images (ref_xxx.png), align character visual DNA and portrait prompts, and sync JSON files."
    )
    p_collect.add_argument("target", nargs="?", default=None, help="Input markdown file or workspace directory (default: scan all workspaces in output directory).")
    p_collect.add_argument("--output-dir", default="outputs", help="Base output directory (default: outputs).")
    p_collect.add_argument("-m", "--model", default="gemini-2.5-flash", help="Multimodal vision model for reference alignment (default: gemini-2.5-flash).")
    p_collect.add_argument("--api-key", help="Gemini API key for AI vision analysis.")
    p_collect.add_argument("--no-ai", dest="use_ai", action="store_false", default=True, help="Disable AI multimodal vision analysis and use local reference alignment.")
    p_collect.add_argument("--dry-run", action="store_true", help="Preview discovered images without modifying JSON files.")
    p_collect.add_argument("-v", "--verbose", action="store_true", default=True, help="Detailed discovery logs.")

    # --------------------------------------------------------------------------
    # 7. 'test' command
    # --------------------------------------------------------------------------
    p_test = subparsers.add_parser("test", help="Run embedded unit test suite.")
    p_test.add_argument("-v", "--verbose", action="store_true", help="Verbose test output.")

    # Handle argument aliases
    argv = sys.argv[1:]
    # Alias: 'storybook assets char-ref ...' -> 'storybook char-ref ...'
    if len(argv) >= 2 and argv[0] == "assets" and argv[1] in ["char-ref", "style-ref"]:
        argv.pop(0)

    # Alias: 'storybook assets collect ...' -> 'storybook collect ...'
    if len(argv) >= 2 and argv[0] == "assets" and argv[1] == "collect":
        argv.pop(0)
    elif len(argv) >= 1 and argv[0] == "assets" and "collect" in argv:
        argv.remove("assets")
        argv.remove("collect")
        argv.insert(0, "collect")

    # Handle special case: 'media <file>' where <file> is passed directly without subaction
    subactions = {"tag", "prompt", "generate", "clean", "stats", "extract", "pipeline"}
    if len(argv) >= 1 and argv[0] == "media":
        if len(argv) == 1:
            p_media.print_help()
            sys.exit(0)
        has_subaction = any(arg in subactions for arg in argv[1:])
        has_help = any(arg in ["-h", "--help"] for arg in argv[1:])
        if not has_subaction and not has_help:
            argv.insert(1, "pipeline")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # --------------------------------------------------------------------------
    # Dispatch: test
    # --------------------------------------------------------------------------
    if args.command == "test":
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestStorybook)
        verbosity = 2 if getattr(args, "verbose", False) else 1
        runner = unittest.TextTestRunner(verbosity=verbosity)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)

    # --------------------------------------------------------------------------
    # Dispatch: create
    # --------------------------------------------------------------------------
    if args.command == "create":
        create_story_content(
            prompt=args.prompt,
            output_path=args.output,
            genre=args.genre,
            chapters=args.chapters
        )
        sys.exit(0)

    # --------------------------------------------------------------------------
    # Dispatch: collect
    # --------------------------------------------------------------------------
    if args.command == "collect":
        target = getattr(args, "target", None)
        base_out = getattr(args, "output_dir", "outputs")
        dry_run = getattr(args, "dry_run", False)
        verbose = getattr(args, "verbose", True)
        api_key = getattr(args, "api_key", None)
        model = getattr(args, "model", "gemini-2.5-flash")
        use_ai = getattr(args, "use_ai", True)

        workspaces = resolve_workspaces_for_target(target, base_output_dir=base_out)
        if not workspaces:
            print(f"[storybook collect] No storybook workspaces found in '{base_out}'.", file=sys.stderr)
            if target:
                print(f"Target '{target}' does not appear to be an existing story file or workspace.", file=sys.stderr)
            else:
                print("Specify a story file or directory: python storybook.py assets collect <story.md>", file=sys.stderr)
            sys.exit(1)

        total_collected_chars = 0
        total_collected_styles = 0
        for ws in workspaces:
            res = collect_workspace_assets(
                workspace=ws,
                api_key=api_key,
                model=model,
                use_ai=use_ai,
                dry_run=dry_run,
                verbose=verbose
            )
            total_collected_chars += res.get("total_character_images", 0)
            total_collected_styles += res.get("total_style_images", 0)

        action_word = "Would collect" if dry_run else "Collected"
        print(f"\n[storybook collect] Finished: {action_word} {total_collected_chars} character image(s) and {total_collected_styles} style image(s) across {len(workspaces)} workspace(s).")
        sys.exit(0)

    # --------------------------------------------------------------------------
    # Dispatch: assets / char-ref / style-ref
    # --------------------------------------------------------------------------
    if args.command in ["assets", "char-ref", "style-ref"]:
        if not getattr(args, "input_file", None) and sys.stdin.isatty():
            if args.command == "assets":
                p_assets.print_help()
            elif args.command == "char-ref":
                p_char_ref.print_help()
            else:
                p_style_ref.print_help()
            sys.exit(0)

        input_text = read_input_content(args.input_file)
        workspace = StoryWorkspace(args.input_file, base_output_dir=getattr(args, "output_dir", "outputs"))

        char_refs_arg = parse_char_refs_arg(getattr(args, "char_refs", None)) if args.command in ["assets", "char-ref"] else None
        style_refs_arg = parse_style_refs_arg(getattr(args, "style_refs", None)) if args.command in ["assets", "style-ref"] else None

        should_generate = getattr(args, "generate", False)

        report = setup_workspace_assets(
            workspace=workspace,
            markdown_text=input_text,
            char_refs_arg=char_refs_arg,
            style_refs_arg=style_refs_arg,
            style_prompt=getattr(args, "style_prompt", None),
            image_model=getattr(args, "model", "gemini-3.1-flash-image"),
            api_key=getattr(args, "api_key", None),
            generate_images=should_generate,
            force=getattr(args, "force", False),
            dry_run=getattr(args, "dry_run", False),
            verbose=True
        )
        print(f"\n[storybook {args.command}] Asset setup completed for workspace '{workspace.stem}':")
        print(f"  Workspace: {workspace.workspace_dir}")
        print(f"  Characters: {len(report.get('characters', []))} character reference(s)")
        for c in report.get("characters", []):
            print(f"    - {c.get('name')}: {len(c.get('images', []))} image(s) ({c.get('source')})")
        print(f"  Styles: {len(report.get('styles', []))} style profile(s)")
        for s in report.get("styles", []):
            print(f"    - {s.get('style_name', 'Style')}: {len(s.get('images', []))} image(s) ({s.get('source')})")
        if not should_generate:
            print(f"\nTip: Place your reference images (e.g. ref_001.png, ref_002.png) in character/style folders,")
            print(f"     then run: python storybook.py assets collect {workspace.stem}.md")
            print(f"     Or generate AI references with: python storybook.py assets {workspace.stem}.md --generate")
        sys.exit(0)

    # --------------------------------------------------------------------------
    # Dispatch: media
    # --------------------------------------------------------------------------
    if args.command == "media":
        action = getattr(args, "media_action", None)

        # Mode: stats
        if action == "stats" or getattr(args, "stats", False):
            input_text = read_input_content(args.input_file)
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

        # Mode: extract
        if action == "extract" or getattr(args, "extract_tags", False):
            input_text = read_input_content(args.input_file)
            tags = extract_media_tags(input_text)
            clean_tags = [{k: v for k, v in t.items() if not k.startswith("_")} for t in tags]
            json_output = json.dumps({"count": len(clean_tags), "tags": clean_tags}, ensure_ascii=False, indent=2)
            write_output_content(json_output + "\n", args.output, args.input_file, False)
            sys.exit(0)

        # Mode: clean
        if action == "clean" or getattr(args, "clean", False):
            input_text = read_input_content(args.input_file)
            cleaned = remove_media_tags(input_text)
            write_output_content(cleaned, args.output, args.input_file, args.in_place)
            sys.exit(0)

        # Mode: tag only
        if action == "tag":
            input_text = read_input_content(args.input_file)
            m_types = args.media_types or ["all"]
            res = insert_media_tags(
                markdown_text=input_text,
                media_types=m_types,
                image_gap=args.gap,
                first_insert=args.first_insert,
                first_insert_pos=args.first_insert_pos,
                reset_on_h1=args.reset_on_h1,
                generate_prompts=False,
                clean_media=args.clean_media,
                tag_format=args.tag_format,
                remove_existing=True
            )
            write_output_content(res, args.output, args.input_file, args.in_place)
            sys.exit(0)

        # Mode: prompt only
        if action == "prompt":
            input_text = read_input_content(args.input_file)
            res = update_media_tag_prompts(
                markdown_text=input_text,
                force=args.force,
                use_ai=args.ai,
                api_key=args.api_key
            )
            write_output_content(res, args.output, args.input_file, args.in_place)
            sys.exit(0)

        # Mode: generate only
        if action == "generate":
            input_text = read_input_content(args.input_file)
            workspace = StoryWorkspace(args.input_file, base_output_dir=args.output_dir)

            char_refs_arg = parse_char_refs_arg(getattr(args, "char_refs", None))
            style_refs_arg = parse_style_refs_arg(getattr(args, "style_refs", None))
            if getattr(args, "style_image", None):
                style_refs_arg.append(args.style_image)

            # Ensure workspace reference assets exist
            setup_workspace_assets(
                workspace=workspace,
                markdown_text=input_text,
                char_refs_arg=char_refs_arg,
                style_refs_arg=style_refs_arg,
                style_prompt=getattr(args, "style_prompt", None),
                image_model=args.model,
                api_key=args.api_key,
                dry_run=args.dry_run,
                verbose=False
            )

            updated, count = generate_media_assets(
                markdown_text=input_text,
                output_dir=workspace.workspace_dir,
                media_type=args.type,
                tag_id=args.tag_id,
                image_model=args.model,
                video_model=args.video_model,
                aspect_ratio=args.ratio,
                image_size=args.size,
                style_image=getattr(args, "style_image", None),
                style_prompt=getattr(args, "style_prompt", None),
                api_key=args.api_key,
                dry_run=args.dry_run,
                workspace=workspace
            )
            target_out = args.output or (args.input_file if args.in_place else str(workspace.output_md))
            if not args.dry_run or args.output or args.in_place:
                write_output_content(updated, target_out, args.input_file, args.in_place)
            sys.exit(0)

        # ----------------------------------------------------------------------
        # Default 'media <file>': Full End-to-End: tag -> prompt -> assets -> generate
        # ----------------------------------------------------------------------
        input_text = read_input_content(args.input_file)
        workspace = StoryWorkspace(args.input_file, base_output_dir=getattr(args, "output_dir", "outputs"))
        workspace.ensure_dirs()

        char_refs_arg = parse_char_refs_arg(getattr(args, "char_refs", None))
        style_refs_arg = parse_style_refs_arg(getattr(args, "style_refs", None))
        if getattr(args, "style_image", None):
            style_refs_arg.append(args.style_image)

        m_types = args.media_types or ["all"]

        print("[storybook media] Step 1/4: Tagging story with media markers...")
        tagged_text = insert_media_tags(
            markdown_text=input_text,
            media_types=m_types,
            image_gap=getattr(args, "gap", DEFAULT_IMAGE_GAP),
            clean_media=getattr(args, "clean_media", None),
            generate_prompts=True,
            remove_existing=True
        )

        print("[storybook media] Step 2/4: Generating and updating context prompts...")
        prompted_text = update_media_tag_prompts(tagged_text, force=False)

        print("[storybook media] Step 3/4: Setting up workspace reference assets...")
        setup_workspace_assets(
            workspace=workspace,
            markdown_text=prompted_text,
            char_refs_arg=char_refs_arg,
            style_refs_arg=style_refs_arg,
            style_prompt=getattr(args, "style_prompt", None),
            image_model=getattr(args, "model", "gemini-3.1-flash-image"),
            api_key=getattr(args, "api_key", None),
            dry_run=getattr(args, "dry_run", False),
            verbose=True
        )

        print("[storybook media] Step 4/4: Media asset generation pipeline...")
        final_text, gen_count = generate_media_assets(
            markdown_text=prompted_text,
            output_dir=workspace.workspace_dir,
            media_type="all",
            image_model=getattr(args, "model", "gemini-3.1-flash-image"),
            aspect_ratio=getattr(args, "ratio", "16:9"),
            image_size=getattr(args, "size", "1K"),
            style_image=getattr(args, "style_image", None),
            style_prompt=getattr(args, "style_prompt", None),
            api_key=getattr(args, "api_key", None),
            dry_run=getattr(args, "dry_run", False),
            workspace=workspace
        )

        target_out = args.output or (args.input_file if args.in_place else str(workspace.output_md))
        if not getattr(args, "dry_run", False) or args.output or args.in_place:
            write_output_content(final_text, target_out, args.input_file, args.in_place)
        sys.exit(0)


if __name__ == "__main__":
    main()
