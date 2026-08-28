#!/usr/bin/env python3
"""
Unit and integration tests for storybook_craft.py
"""

import unittest
import json
from storybook_craft import (
    count_story_units,
    split_markdown_into_blocks,
    insert_media_tags,
    extract_media_tags,
    remove_media_tags,
    remove_markdown_media,
    get_storybook_stats,
    format_tag,
    MarkdownBlock
)


class TestCounting(unittest.TestCase):

    def test_cjk_counting(self):
        # 19 Chinese characters + 1 full-width period = 20 CJK units
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

    def test_mixed_counting(self):
        # 6 Chinese characters + 1 full-width period = 7 CJK units; 4 English words: 3, books, 2, apples
        text = "小明有 3 本 books 和 2 个 apples。"
        total, cjk, words = count_story_units(text)
        self.assertEqual(cjk, 7)
        self.assertEqual(words, 4)
        self.assertEqual(total, 11)

    def test_strip_markdown_syntax(self):
        # 标题 (2) + 加粗文字 (4) + 与 (1) + 斜体 (2) + 以及 (2) + 链接文本 (4) + 和 (1) + 代码 (2) = 18 CJK
        text = "## 标题\n**加粗文字** 与 *斜体* 以及 [链接文本](https://example.com) 和 `代码`"
        total, cjk, words = count_story_units(text)
        self.assertEqual(cjk, 18)


class TestBlockSplitting(unittest.TestCase):

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


class TestTagInsertion(unittest.TestCase):

    def setUp(self):
        # 110 CJK units per paragraph
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

    def test_video_tag_under_h1_and_skip_first_title(self):
        result = insert_media_tags(self.story_md, media_types=["video"])
        tags = extract_media_tags(result)
        
        video_tags = [t for t in tags if t.get("type") == "video"]
        # The first # Title (魔法森林历险记) is skipped; chapters 1 and 2 get video tags
        self.assertEqual(len(video_tags), 2)
        self.assertEqual(video_tags[0]["id"], "vid_001")
        self.assertEqual(video_tags[0]["title"], "第一章 魔法森林")
        self.assertEqual(video_tags[1]["id"], "vid_002")
        self.assertEqual(video_tags[1]["title"], "第二章 神殿钥匙")

    def test_image_gap_and_first_insert(self):
        # Each paragraph ~110 units.
        # p1: first_insert -> img_001
        # p2 (~110) + p3 (~110) = 220 >= 200 -> img_002
        # Chapter 2: p1 (~110) + p2 (~110) = 220 >= 200 -> img_003
        result = insert_media_tags(self.story_md, media_types=["image"], image_gap=200, first_insert=True)
        tags = extract_media_tags(result)
        image_tags = [t for t in tags if t.get("type") == "image"]
        
        self.assertEqual(len(image_tags), 3)
        self.assertEqual(image_tags[0]["id"], "img_001")
        self.assertEqual(image_tags[1]["id"], "img_002")
        self.assertEqual(image_tags[2]["id"], "img_003")

    def test_no_first_insert(self):
        # When first_insert is False:
        # p1 (~110) < 200
        # p1 + p2 (~220) >= 200 -> img_001
        # p3 (~110) + Chapter 2 p1 (~110) = 220 >= 200 -> img_002
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

    def test_generate_prompts(self):
        result = insert_media_tags(self.story_md, media_types=["all"], image_gap=200, generate_prompts=True)
        tags = extract_media_tags(result)
        
        # Check video prompt (under # Title -> only text after it is 1st priority)
        vid_001 = [t for t in tags if t.get("id") == "vid_001"][0]
        self.assertIn("第一章 魔法森林", vid_001["prompt"])
        self.assertIn("很久很久以前", vid_001["prompt"])

        # Check first image prompt (middle of section: after is 1st priority, before is secondary)
        img_001 = [t for t in tags if t.get("id") == "img_001"][0]
        self.assertIn("清晨的第一缕阳光", img_001["prompt"]) # Primary (after)
        self.assertIn("很久很久以前", img_001["prompt"])     # Secondary (before)

    def test_clean_and_remove_tags(self):
        tagged = insert_media_tags(self.story_md, media_types=["all"], image_gap=200)
        cleaned = remove_media_tags(tagged)
        tags = extract_media_tags(cleaned)
        self.assertEqual(len(tags), 0)
        self.assertIn("# 第一章 魔法森林", cleaned)
        self.assertIn(self.p1, cleaned)

    def test_tag_formats(self):
        # JSON format
        res_json = insert_media_tags(self.story_md, media_types=["image"], tag_format="json-comment")
        self.assertIn("<!-- storybook-media: {", res_json)
        tags_json = extract_media_tags(res_json)
        self.assertGreater(len(tags_json), 0)

        # KV format
        res_kv = insert_media_tags(self.story_md, media_types=["image"], tag_format="kv-comment")
        self.assertIn('<!-- storybook-media type="image"', res_kv)
        tags_kv = extract_media_tags(res_kv)
        self.assertGreater(len(tags_kv), 0)

        # Visible format
        res_vis = insert_media_tags(self.story_md, media_types=["image"], tag_format="visible")
        self.assertIn('> 🎨 **[Media: image', res_vis)
        tags_vis = extract_media_tags(res_vis)
        self.assertGreater(len(tags_vis), 0)

    def test_remove_markdown_media(self):
        doc = """# 序章

![Image](https://example.com/pic1.png)

这是一段故事正文。

<img src="https://example.com/pic2.jpg" alt="test" />

<video src="https://example.com/vid.mp4"></video>

这是另一段正文。
"""
        # Test cleaning all media (default)
        cleaned_all = remove_markdown_media(doc, "all")
        self.assertNotIn("https://example.com/pic1.png", cleaned_all)
        self.assertNotIn("https://example.com/pic2.jpg", cleaned_all)
        self.assertNotIn("https://example.com/vid.mp4", cleaned_all)
        self.assertIn("这是一段故事正文。", cleaned_all)
        self.assertIn("这是另一段正文。", cleaned_all)

        # Test cleaning images only
        cleaned_img = remove_markdown_media(doc, "image")
        self.assertNotIn("pic1.png", cleaned_img)
        self.assertNotIn("pic2.jpg", cleaned_img)
        self.assertIn("<video", cleaned_img)

        # Test cleaning videos only
        cleaned_vid = remove_markdown_media(doc, "video")
        self.assertIn("pic1.png", cleaned_vid)
        self.assertNotIn("<video", cleaned_vid)

    def test_clean_media_in_insert_tags(self):
        doc_with_images = f"""# 魔法森林历险记

# 第一章 魔法森林

![Image](https://example.com/old_image.png)

{self.p1}

{self.p2}
"""
        result = insert_media_tags(doc_with_images, media_types=["all"], clean_media="all")
        self.assertNotIn("https://example.com/old_image.png", result)
        self.assertIn("<!-- storybook-media:", result)

    def test_stats(self):
        stats = get_storybook_stats(self.story_md)
        self.assertEqual(stats["h1_headings"], 3)
        self.assertEqual(stats["paragraphs"], 5)
        self.assertGreater(stats["cjk_characters"], 500)


if __name__ == "__main__":
    unittest.main()
