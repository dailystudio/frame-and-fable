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

# Auto-load .env file if present
for _env_path in [
    Path(".env"),
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
]:
    if _env_path.exists():
        try:
            with open(_env_path, "r", encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith("#") and "=" in _line:
                        _k, _v = _line.split("=", 1)
                        _k = _k.strip()
                        _v = _v.strip().strip("'\"")
                        if _k and _v and _k not in os.environ:
                            os.environ[_k] = _v
        except Exception:
            pass



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


def clean_dialogue_quotes(text: str) -> str:
    """Removes spoken dialogue quotes while preserving quoted proper nouns / terms."""
    if not text:
        return ""
    def replace_quote(m):
        content = m.group(1).strip()
        # If it looks like dialogue (ends with ? ! or has typical dialogue markers or is long with sentence punctuation)
        is_dialogue = bool(re.search(r"[？！\?!]|^(?:快|看|不|哈|这|你|我|他|我们|你们|糟了|没错|为什么|难道|不止)", content))
        if is_dialogue or len(content) > 30:
            return ""  # strip dialogue
        return content  # keep term without quotes

    res = re.sub(r"[\u201c\u300c\u300e\"]([^\u201d\u300d\u300f\"]+)[\u201d\u300d\u300f\"]", replace_quote, text)
    res = re.sub(r"[\u2018\u300d\']([^\u2019\u300f\']+)[\u2019\u300f\']", replace_quote, res)
    return res


def clean_narrative_for_visual_prompt(text: str) -> str:
    """
    Cleans literary narrative text to extract concrete visual descriptions:
    1. Strips markdown syntax (headers, bold, links, blockquotes).
    2. Strips spoken dialogue quotes (preserves quoted proper nouns like '皮拉诺瓦').
    3. Strips speech indicators ('喊道', '轻声自语', etc.).
    4. Replaces auditory sensory details with visual equivalents.
    5. Removes abstract, emotional, or meta-narrative filler.
    """
    if not text:
        return ""
    # Strip markdown formatting
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"^>+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

    # Strip dialogue quotes
    cleaned = clean_dialogue_quotes(cleaned)

    # Strip speech indicator verbs
    cleaned = re.sub(
        r"(?:大声|轻声|颤声|怒|低声|惊恐地|激动地|喜极而泣地|震撼地|喃喃|不由得)?(?:喊道|说道|呼喊|自语|惊呼|低语|咆哮|怒吼|问道|回答|说|叫道|苦笑道|赞叹道|叹道)[，。、；！]*",
        "",
        cleaned
    )

    # Non-visual abstract commentary removals
    noise_patterns = [
        r"从那天起[，,]三位英雄的生活轨迹[，,]彻底改变了[。.]*",
        r"生命与希望[，,]就在这片土地上安然生长[。.]*",
        r"这份和平的景象之下[，,]隐藏着一个深刻的秘密[：:]*",
        r"无论他们如何努力[，,]那些关于时空裂隙的.*?都成了无稽之谈[。.]*",
        r"日复一日的失败[，,]让他们不得不开始适应这个陌生的.*?[。.]*",
        r"三位英雄的目光再次交织在一起[，,]比任何时候都更加坚定[。.]*",
        r"极地远征的艰难远超他们的想象[。.]*.*?[。.]*",
        r"然而平静的大陆被一次突如其来的.*?打破了宁静[。.]*",
        r"人们的病[，,]不在身上[，,]而在心里[。.]*",
    ]
    for np in noise_patterns:
        cleaned = re.sub(np, "", cleaned)

    # Auditory to visual replacements
    cleaned = cleaned.replace("孩童的笑闹声在铺着鹅卵石的街道上回荡", "孩童在铺着鹅卵石的街道上奔跑嬉戏")
    cleaned = cleaned.replace("商旅的马车与工匠铺子里的敲打声交织在一起", "商旅马车穿梭于市集，工匠铺里铁花飞溅")
    cleaned = cleaned.replace("发出悦耳的叮咚声", "激起清亮晶莹的水花")
    cleaned = cleaned.replace("发出沉闷金属撞击声的场所", "器械林立的现代力量健身房")
    cleaned = cleaned.replace("电脑风扇的低鸣", "工作台上闪烁的电子指示灯")
    cleaned = cleaned.replace("齐齐发出低鸣", "齐齐泛起柔和共鸣光芒")
    cleaned = cleaned.replace("发出凄厉的吱呀声", "狂暴扭曲地挣扎嘶吼")
    cleaned = cleaned.replace("一声低沉的共鸣响彻花店", "花店半空中光芒大盛")
    cleaned = cleaned.replace("刺耳的轰鸣声瞬间涌入感官", "车流与机械在宽阔道路上飞速穿梭")

    # Clean punctuation and extra spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^[，。、；！？,\s]+", "", cleaned)
    cleaned = re.sub(r"[，、；\s]+$", "", cleaned)
    return cleaned


def detect_scene_shot_and_framing(
    tag_type: str,
    text: str,
    section_title: str = "",
    is_chapter_start: bool = False
) -> str:
    """Determines camera framing and shot composition."""
    if tag_type == "video" or is_chapter_start:
        return "【电影级全景开篇镜头】广角视野，宏大纵深感，动态平稳推进构图"

    action_keywords = ["崩塌", "撕裂", "暴风雪", "怒吼", "砸碎", "对决", "巨兽", "冲击", "激战", "怪物", "异变", "决战", "飞跃", "挥动", "粉碎"]
    if any(kw in text for kw in action_keywords):
        return "【电影级动态动作镜头】低角度仰拍抓拍，强烈的动态张力与视觉冲击力"

    medium_keywords = ["工作台", "研究", "健身房", "花舍", "拾起", "注视", "操作台", "电脑", "诊室", "拼接", "碎片", "显示屏", "特写", "托起", "浇灌"]
    if any(kw in text for kw in medium_keywords):
        return "【电影级中景特写构图】富有故事感的人物姿态与环境道具交互细节"

    return "【史诗级广角场景构图】开阔的空间层次与生动的环境叙事细节"


def detect_scene_lighting(text: str, section_title: str = "") -> str:
    """Determines scene lighting, atmosphere, and volumetric mood."""
    combined = f"{section_title} {text}"
    if any(kw in combined for kw in ["极地", "冰川", "暴风雪", "坚冰", "冰山"]):
        return "极地清冷冰蓝自然光，漫天飞舞的细碎雪花粒子，冰晶剔透高光"
    if any(kw in combined for kw in ["虚空", "裂隙", "崩塌", "异界"]):
        return "暗紫色虚空裂隙与扭曲电弧火花，高对比度戏剧性明暗光影"
    if any(kw in combined for kw in ["蓝焰", "法杖", "奥术", "以太", "共鸣", "深夜", "芯片", "显示屏"]):
        return "幽蓝奥术魔火与柔和科技荧光交织，冷暖对比，体积光束"
    if any(kw in combined for kw in ["机械魔法时代", "现代都市", "夜景", "天际线", "大厦"]):
        return "现代都市璀璨霓虹天际线，车流红白光轨，冷色调玻璃金属反光"
    return "温暖明亮的金色晨光漫射，柔和光晕，空气中漂浮着微小的金色光尘"


def detect_and_enrich_characters(
    text: str,
    characters: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, List[str]]:
    """Identifies characters in text and enriches them with concise visual DNA anchors."""
    found = []
    enriched = text
    defaults = {
        "布洛克": "矮人狂战士布洛克·铁盾（头戴暗灰角盔，健硕身躯佩戴交叉皮革背带，手持沉重战锤与长方形金属巨盾）",
        "阿尔文": "博学法师阿尔文·蓝焰（身着深靛蓝星纹法袍，头戴巫师尖帽，浓密姜红胡须，手持顶端镶嵌幽蓝奥术光球的木法杖）",
        "米拉": "仁慈治愈师米拉·布伦（梳着栗色双麻花辫，头戴米色十字徽章软帽，身着芥末黄束腰袍与棕色长裤，随身佩戴药剂木瓶）",
    }
    if characters:
        for c in characters:
            name = c.get("name", "")
            if name and name in text:
                found.append(name)
    else:
        for short_name in defaults:
            if short_name in text:
                found.append(short_name)

    return enriched, found


# Curated cinematic visual prompts for the 55 media tags of "GoAlive的英雄们"
GO_ALIVE_HEROES_PROMPTS = {
    "vid_001": "【电影级全景开篇镜头】在中世纪奇幻大陆皮拉诺瓦（Pyranova），明媚温暖的金色阳光洒在连绵起伏的翠绿丘陵与金黄麦田上，麦浪如海洋般随风起伏。清澈透明的银光河蜿蜒穿过繁荣的中世纪市镇，河岸市集商旅马车络绎不绝，工匠铺里铁花飞溅。远景巍峨矗立着石砌城堡尖塔与庄严教堂钟楼。晨光柔和漫射，空气中漂浮着微小金色光尘，空间纵深宏大开阔。造型风格：3D定格动画/黏土雕塑质感与厚涂插画结合，造型饱满圆润，电影级暖金光影渲染。",
    "img_001": "【史诗级广角场景构图】中世纪繁华市镇的中心街景，高耸古朴的石砌城堡尖塔与庄严教堂钟楼在蔚蓝晴空下遥相辉映。铺着复古鹅卵石的街道上，孩童在喷泉旁奔跑嬉戏，酒馆半开的木门透出温暖炉火，吟游诗人在酒馆门口弹奏着木质鲁特琴。街道两旁摆满木桶、蔬果摊位与手工艺铺，暖黄色晨光倾泻在石墙与木瓦上，充满祥和安宁的生活气息。3D故事书艺术风格，手绘厚涂质感，温暖金琥珀色调。",
    "img_002": "【电影级广角低角度探索镜头】神秘深邃的古代史前文明地宫遗迹深处，地面覆盖着厚重的尘埃与坍塌的碎石。一架造型奇特、线条流畅古朴的史前“古老飞行器”金属残骸半掩埋在石堆与青苔之间，金属机翼上隐隐显露出神秘复杂的凹陷符文脉络。微弱的天光从地宫穹顶裂缝中垂直投下，形成神秘幽暗的丁达尔光束，历史沧桑感与未解之谜笼罩四周。高对比度戏剧光影，奇幻微缩景观质感。",
    "img_046": "【史诗级广角场景构图】神秘深邃的史前地宫“风之墓穴”入口前，魁梧粗犷的矮人狂战士“磐石”——布洛克·铁盾（Brock Ironshield）昂首伫立。他头戴坚固的角盔，深褐卷曲胡须茂密威严，身披斜跨皮带与金属护肩，双手稳稳按立着那一面由古代合金重铸而成的参天巨盾。巨盾表面冷冽泛光、刻满古老防御符文，如同一道坚不可摧的移动城墙。身后地宫阴影中半掩着数架沉睡的史前古老飞行器残骸。温暖晨曦穿透穹顶裂隙，洒下微弱丁达尔光束，英雄气概与厚重历史感交融。造型风格：3D定格动画/黏土雕塑质感与厚涂插画结合，造型饱满圆润，电影级暖金光影渲染。",
    "img_047": "【电影级中全景构图】神秘微光闪烁的古代遗迹藏书室内，“蓝焰”——阿尔文·蓝焰（Arven Blueflame）神情专注而庄严。这位身材矮壮、面容坚毅的博学法师，头戴深蓝色巫师尖顶帽，浓密的姜红胡须随魔力微风轻轻飘动，身着饰有淡蓝符文镶边的深靛蓝长袍。他左手持握着古朴粗糙的弯曲木质法杖，右手掌心托起一团清澈跳跃的幽蓝奥术魔焰。蓝焰的纯净光华映亮了石桌上摊开的古代金属飞行器符文图纸与以太核心部件，古老符文在蓝焰辉映下泛起共鸣微光。造型风格：3D定格动画/黏土雕塑质感与厚涂插画结合，造型饱满圆润，电影级暖金光影与冷调蓝焰交织。",
    "img_003": "【电影级中景特写镜头】“春愈者”米拉·布伦（矮小可爱的治愈师少女，头戴饰有米色十字徽章的软帽，栗色粗麻花辫垂在肩侧，身穿芥末黄束腰袍与棕色长裤）。她温柔地半跪在一座散发过载红光的古代机械装置前，双手掌心散发出柔和温润的翡翠绿治愈灵光，安抚着狂躁震颤的古代能量水晶。身旁佩戴着药剂木瓶与牛皮卷轴，神情专注仁慈。柔和光晕漫射，3D黏土质感故事书绘本风。",
    "vid_002": "【电影级全景灾难开篇镜头】原本平静祥和的中世纪村庄上空，晴空突然被狂暴撕裂开一道巨大的紫黑色“虚空裂隙”，宛如天空破碎的伤口。深不见底的时空漩涡翻滚咆哮，刺目的暗紫混沌电弧在云层与地面之间狂乱劈砍，大地剧烈颤抖，无数狰狞未知的异界虚空魔物从裂隙阴影中如潮水般汹涌倾泻而出。暗调冷紫光与闪电交织，压迫感十足的史诗灾变全景。",
    "img_004": "【电影级动态中景对峙构图】突变降临的村落边缘，博学矮人法师阿尔文·蓝焰（身着深靛蓝星纹长袍，头戴巫师尖帽，浓密姜红胡须）紧锁眉头，双手紧握木法杖，杖尖镶嵌的法球迸发出剧烈颤抖的幽蓝奥术光芒；身旁矮人狂战士布洛克·铁盾（头戴角盔，身形魁梧，皮带斜跨健硕胸膛）怒目圆睁，双手紧握沉重战锤与厚重金属巨盾，呈警惕御敌战斗姿态。远处地面裂隙蔓延，幽蓝法力光辉照亮两人凝重的面庞。",
    "img_005": "【电影级动态动作镜头】三位英雄背靠背紧密协作，在剧烈崩塌的虚空之门前展开终极封印决战！布洛克怒吼着将刻有符文的坚不可摧巨盾狠狠砸向地面，筑起暗金防御壁垒；阿尔文高举法杖爆发出通天彻地的耀眼幽蓝魔法火柱；米拉双手托起翠绿守护灵环。封印法阵的璀璨金光与狂暴的紫黑色虚空风暴产生剧烈大碰撞，脚下岩层大面积碎裂陷落，强烈的视觉冲击力与英雄史诗张力。",
    "img_006": "【电影级动态俯冲特写镜头】封印爆发的临界瞬间，脚下大地彻底塌陷撕裂，化作巨大的时空裂隙深渊！狂暴的时空引力如同无底黑洞，将布洛克、阿尔文与米拉三人齐齐吸入旋转的时空漩涡。阿尔文拼命释放蓝焰试图稳固空间，布洛克挥舞战锤抵抗扭曲重力，米拉神情惊恐伸手抓向同伴。流光溢彩的时空能量粒子如瀑布般飞旋，三人的身影逐渐被耀眼的白光与幽暗裂隙吞没。",
    "vid_003": "【电影级全景开篇镜头】三位中世纪装束的英雄从昏迷中苏醒，站在繁华现代超级大都市的开阔广场上。镜头以仰视广角徐徐升起，展现出遮天蔽日的摩天大楼玻璃幕墙反射着刺眼骄阳，纵横交错的高架桥上川流不息的现代汽车飞速穿梭，巨大的现代化喷气民航客机轰鸣着掠过钢筋水泥天际线。古典奇幻英雄与庞大现代科技丛林形成极度震撼的视觉对比。",
    "img_007": "【电影级中景反差镜头】车水马龙的现代十字路口，米拉脸色发白、充满惊愕地伸出手颤抖地指向湛蓝天空；天空中一架低空掠过的现代巨型民航客机展翅滑翔。阿尔文紧握手中的魔法木杖，目瞪口呆地望着飞驰而过的钢铁汽车；布洛克双手抱头，环顾四周高耸入云的玻璃写字楼，神情茫然不知所措。中世纪奇幻冒险者与现代工业文明的强烈戏剧碰撞。",
    "img_008": "【史诗级广角夜景俯瞰镜头】夜幕降临，超级现代都市化为一片璀璨夺目的光之海洋。布洛克、阿尔文与米拉站在摩天大楼天台边缘，俯瞰脚下壮丽的都市天际线：高低错落的大厦霓虹闪烁，高架立交桥上交织着如红宝石与白金光芒般的车流光轨，摩天轮与巨幅电子广告屏在夜色中流光溢彩。三位英雄背影倒映着整座不夜城的繁华，宛若星辰坠落凡间。",
    "img_009": "【电影级中全景街头探索镜头】熙熙攘攘的现代商业步行街，三位英雄小心翼翼地穿行在人群中。布洛克背着厚重巨盾和战锤，笨拙地躲避着滑滑板的青年；阿尔文好奇地注视着街边橱窗里播放视频的液晶电视；米拉则注视着路边自动售货机吐出的易拉罐。周围穿西装、戴耳机的现代行人纷纷投来好奇惊讶的目光。充满趣味与探索感的时空交错构图。",
    "vid_004": "【电影级城市全景蒙太奇镜头】穿梭在现代大都市街巷与阴影中的三位英雄。高耸的写字楼与阴暗的后巷形成强烈对比，布洛克、阿尔文与米拉手持中世纪指南针与法杖，在玻璃幕墙反光的城市丛林中四处探寻时空裂隙的线索。镜头以流畅推进视角展现他们穿行于斑马线、地铁出入口与林荫道，既有迷茫困顿，又怀揣着坚定的回家信念。",
    "img_010": "【电影级中景趣味镜头】现代力量健身房内部，器械林立、哑铃架整齐排列。身披野蛮人皮革斜挎带、头戴角盔的矮人狂战士布洛克·铁盾大步踏入馆内，双眼放光、兴致勃勃地注视着各种奇形怪状的杠铃与挥汗如雨的健身爱好者。他单手轻松托起一个巨大的重型哑铃，周围肌肉壮汉们目瞪口呆。强烈的工业风健身房背景，明亮聚光灯照射，充满幽默感。",
    "img_011": "【电影级动态全景动作镜头】烈日炎炎的现代化大厦建筑工地上，塔吊高耸，钢筋林立。矮人狂战士布洛克·铁盾身穿印有“铁盾搬运 IronShield Moving”字样的短袖工作服，展现出惊骇世俗的战士神力：他豪迈大笑，凭借单臂将一根数吨重的巨大工字钢梁轻松扛在肩头阔步前行！身旁戴着黄色安全帽的建筑工人们惊得扔掉了手中的图纸，目瞪口呆。阳光照射在钢材高光上，极富力量感。",
    "img_012": "【电影级中景特写镜头】光线昏暗的工作室内，博学法师阿尔文·蓝焰戴着复古老花镜，手中法杖顶端散发着幽蓝微光。他神情极度专注，俯身手持高倍放大镜，正仔细审视着拆解开来的现代电脑主板。绿色电路板上密集排列的金色线路与微型芯片，在法杖光芒照耀下宛若繁复神秘的中世纪魔法符文阵列。科技与古代奥术的奇妙重叠，微距细节清晰。",
    "img_013": "【电影级中景极客工坊镜头】充满赛博科技感的工作间，四台联排液晶显示屏上幽绿与深蓝色的代码流如瀑布般快速滚动。阿尔文·蓝焰手指在机械键盘上飞快敲击，身边凌乱地堆放着拆开的主板、电烙铁与测试仪器。他那根珍贵的古老法杖被当做防静电棒斜靠在主机箱旁，顶端散发着柔和的冷蓝防静电微光。电脑屏幕幽光映照在他专注严肃的脸庞上。",
    "img_014": "【电影级中景温馨治愈镜头】阳光洒满的现代心理咨询室内，整洁舒适，窗台摆放着翠绿盆栽。仁慈治愈师米拉·布伦面带春风般温暖慈祥的微笑，手持一只有着神秘刻纹的药剂木瓶，轻柔地给一盆常春藤浇水。身前沙发上坐着一位满面愁容、抱头焦虑的现代上班族，米拉身上散发出若有若无的金绿色心灵安抚光晕，室内氛围宁静祥和，阳光温暖和煦。",
    "img_015": "【史诗级中全景街角花舍镜头】阳光明媚的都市街角，米拉的花店“回春花舍 Bloom & Heal”温馨可爱。木质招牌下挂满风铃，店门前多层花架上摆满了娇艳欲滴的奇幻鲜花与生机盎然的奇特绿植。米拉头戴标志性十字徽章软帽，系着花艺围裙，正欢快地修剪着向日葵枝叶，脸颊洋溢着甜美的笑容。晨曦穿透花瓣，水珠晶莹剔透，暖意融融。",
    "vid_005": "【电影级室内全景推进镜头】寂静深夜的现代公寓内，窗帘紧闭，各种散落的线缆与电脑主机散发着昏暗待机微光。阿尔文·蓝焰神色庄严肃穆，手持古老法杖低声咏唱以太咒文。镜头缓缓向前推进，法杖顶端的蓝焰骤然暴涨，刹那间整间屋子内的电脑显示屏、主板指示灯与电源接口齐齐泛起耀眼的幽蓝奥术共振涟漪，电流火花四溢。",
    "img_016": "【电影级中景高潮镜头】昏暗杂乱的电脑维修间，阿尔文·蓝焰高高举起木质法杖，杖尖迸发出炽热夺目的深蓝魔法烈焰！半空中浮现出一圈圈半透明的古代以太符文光环，环绕着桌上闪烁的电脑显示屏与主机风扇剧烈旋转。空气中电弧劈啪作响，蓝色奥术辉光将整间屋子照耀得亮如白昼，神秘而震撼。",
    "img_017": "【电影级特写神态镜头】共鸣渐止，灯光与屏幕恢复常态。阿尔文·蓝焰双手剧烈颤抖地收回法杖，胸口剧烈起伏。桌上熄屏的手机与杂乱的芯片在阴影中反射着微光，阿尔文瞪大了眼睛注视着法杖，眼中充满难以置信的震撼与欣喜若狂的狂喜之色，满脸浓密姜红胡须随之颤抖。细腻的人物心理情绪刻画。",
    "img_018": "【电影级中景特写镜头】激动不已的阿尔文一把抓起桌上现代智能手机，手指颤抖而急速地划开屏幕，拨通布洛克的电话号码并贴在耳边。他右手兴奋地抓着法杖，身体前倾，神色亢奋迫切，桌上散落着喝剩的咖啡纸杯与螺丝刀。昏暗台灯投下暖黄光晕，勾勒出他激动张皇的神情。",
    "img_019": "【电影级中景夜景特写镜头】夜晚货运仓库旁的开阔空地上，身穿工装背心、身材魁梧如铁塔般的布洛克·铁盾单手拿着小巧的现代智能手机贴在耳侧。他粗犷刚毅的脸上写满了由困惑转为极度震惊的神情，另一只大手紧紧握住立在地面的沉重战锤，手臂青筋暴起。远处城市冷色调路灯照亮他的侧脸。",
    "img_020": "【电影级动态特写异变镜头】昏暗的公寓后厨内，一台原本普通的现代双门电冰箱在狂暴的魔法电弧中发生恐怖异变！金属柜门扭曲裂开，化作一张长满锋利参差钢铁锯齿獠牙的机械巨口；两枚圆形的制冷状态指示灯骤然亮起暴虐嗜血的猩红凶光；冰箱缝隙中狂暴地喷涌出滚滚刺骨的冰霜白雾，化身为凶残的“冰箱怪”！高戏剧冲突感。",
    "img_021": "【电影级动态动作镜头】狭小空间内的激烈激斗！异变冰箱怪张开獠牙巨口，疯狂喷射出暴风雪冰锥利刃；布洛克·铁盾怒吼着半跪在地，双手顶起散发暗金光芒的厚重合金巨盾，正面硬撼狂暴的冰霜冲击，火星与冰屑四溅；后方阿尔文·蓝焰法杖直指怪物，轰出一道水桶粗细的耀眼奥术蓝焰光柱，强烈的动感与英雄气概。",
    "img_022": "【电影级中景战后镜头】激战平息的狼藉房间内，冰箱怪四分五裂，冒着缕缕焦黑青烟与碎冰。阿尔文脸色微白，以法杖点地大口喘息，神情凝重而警惕；布洛克甩了甩战锤上的霜冻碎屑，收起巨盾，环视着四周被冰霜和电弧灼伤的墙壁，战斗硝烟在冷暖交错的残光中缓缓飘散。",
    "img_023": "【电影级中景观察镜头】米拉·布伦轻轻走过满是冰霜与机械碎片的狼藉地面，小心翼翼地绕开锐利的金属残片，走到散发寒气的冰箱怪残骸前。她敏锐的眼眸倒映出一抹非同寻常的光辉，脸上浮现出惊异与好奇的神情，身旁散落着破损的制冷铜管与齿轮。",
    "img_024": "【电影级微距特写镜头】在冰箱怪焦黑撕裂的金属机腹深处，一块巴掌大小、质地温润坚韧的神秘古老合金碎片静静悬浮。碎片表面雕刻着极其细密的古代星辰轨迹符文，正散发出温和纯净的金蓝双色微光，与周围粗糙扭曲的现代废铁形成鲜明对比，宛如蕴藏生命的奇迹。",
    "img_025": "【电影级中景特写抒情镜头】米拉·布伦温柔地半跪在废墟上，伸出纤细温暖的双手，小心翼翼地将那枚散发金蓝柔光的古代能量碎片托在手心。碎片散发的温润光芒轻柔地映照在米拉纯净善良的脸庞上，微风拂动她的栗色发辫，眼神中满溢着希望与感动的光芒。",
    "img_026": "【电影级中景三人构图镜头】阿尔文与布洛克快步围拢到米拉身边，三人共同注视着米拉手心中散发璀璨以太符文光华的能量碎片。阿尔文神情振奋高昂，伸出手指指引着碎片上的古代脉络；布洛克咧嘴露出豪迈的笑容，巨盾微垂。昏暗室内被这团神秘光源染上一层神圣的暖金色。",
    "img_027": "【电影级中景英雄誓约镜头】三位英雄紧紧靠在一起，目光在闪烁的古代能量碎片上交汇，神色无比坚定刚毅。阿尔文握紧法杖，布洛克战锤横胸，米拉轻按胸前的药剂瓶。窗外初升的黎明第一缕阳光穿透破损的窗户，与碎片的金蓝微光交相辉映，照亮了他们重返家园的决然征途。",
    "vid_006": "【电影级城市晨曦全景开篇航拍】破晓时分的现代大都市天际线，壮阔的朝阳将整座钢铁森林染上一层灿烂的金红色。镜头以壮阔的全景航拍徐徐推移，展现三位英雄在城市各个角落有条不紊地展开秘密“碎片狩猎”：阿尔文在工坊解析芯片，布洛克驾驶卡车穿梭废弃工厂，米拉在花店温室感应能量。充满史诗动力感。",
    "img_028": "【电影级中全景工坊镜头】阿尔文的公寓被彻底改造为融合现代科技与中世纪奥术的“魔导实验室”。正中央的大白板上密密麻麻画满了现代电路图、量子物理公式与古老飞行器以太符文模型；长桌上摆放着高精度示波器、电子显微镜以及多块散发不同微光的能量碎片。阿尔文手持羽毛笔与电烙铁，神情如醉如痴。",
    "img_029": "【电影级全景探索镜头】巨大的现代废品回收站中，报废汽车与废弃家电堆积如山。布洛克·铁盾驾驶着贴有“铁盾搬运”复古徽标的小型卡车停在废料堆旁，他凭借中世纪战士对危险与能量的惊人直觉，徒手掀开沉重的废铁壳，精准寻找并挑拣出散发隐秘魔力波动的异常零件。夕阳将他的影子拉得极长。",
    "img_030": "【电影级中景特写镜头】“回春花舍”内静谧的绿植温室，米拉将几块暗沉斑驳的金属碎片浸入盛满草药清泉的水晶盆中。她轻合双目，双手在水面上方施展治愈灵术，翠绿色的生命微光渗入水中，碎片表面的现代污垢与锈蚀悄然脱落，露出下方金光流转的古代以太合金脉络，水面荡漾起七彩光纹。",
    "img_031": "【史诗级广角黄昏剪影镜头】落日熔金的傍晚，三位英雄并肩伫立在城市高架立交桥的顶层护栏旁。天边晚霞绚烂如火，脚下是奔流不息的城市车流霓虹。阿尔文手持蓝焰微烁的法杖指向远方天际，布洛克肩扛战锤昂首远眺，米拉手持寻灵罗盘长发迎风飞舞。在现代钢铁巨兽的丛林中，英雄们的剪影挺拔而坚韧。",
    "vid_007": "【电影级暴风雨全景动作开篇】暴雨倾盆的废弃工业园区深夜，狂风呼啸，电闪雷鸣。破败的重工业厂房与废弃集装箱之间，数只由废弃工业微波炉、空调外机以及机械臂畸变融合而成的巨大机械怪兽在雷光中发出刺耳咆哮，金属外壳闪烁着狂暴的异常紫蓝电火花。镜头穿过雨幕，呈现出极具压迫感与科幻奇幻融合的战场全景。",
    "img_032": "【电影级动态动作抓拍镜头】暴雨中的激战高潮！布洛克·铁盾如同一座暗金战神腾空跃起，手中战锤灌注了无匹的刚猛巨力，化作一道耀眼的金色流星重重轰向地面一只狂暴的微波炉异变怪，地面混凝土瞬间碎裂炸开！阿尔文在侧翼撑起半球形幽蓝奥术护盾，米拉双手扬起翠绿藤蔓灵光束缚住敌人的钢铁巨足，战意沸腾。",
    "img_033": "【电影级微距特写镜头】米拉纤细白皙的指尖轻轻抚摸在一块刚刚净化获得的古代合金薄板上。金属薄板质感温润如玉，表面雕琢着如同电路又如同星辰轨迹的凹槽，在米拉触碰的刹那，整块碎片泛起如同心脏搏动般规律起伏的深邃湛蓝光晕，纯净而庄严，传递出古老神秘的信息。",
    "img_034": "【电影级中景桌面特写镜头】深夜古朴的书桌上，阿尔文·蓝焰神采飞扬地将收集而来的十几块形状互补的古代合金碎片严丝合缝地拼接在一起。碎片边缘完美契合的瞬间，接缝处骤然爆发出璀璨耀眼的金色与淡蓝光流，在桌面半空中投射出一副由无数跳跃光点构成的三维立体全息星图，照亮了三人震撼激动的脸庞。",
    "img_035": "【电影级广角奇观镜头】半空中的三维全息星图缓缓旋转，无数复杂的能量光路与坐标线条在现代房间中穿梭交织。光芒的终点穿过现代地图的所有繁华地带，最终笔直地聚焦、投射在地图最南端那片人迹罕至、极度寒冷的白色极地冰川之上。三位英雄伫立在旋转的光图周围，眼神凝重而坚定。",
    "vid_008": "【电影级史诗暴风雨全景镜头】雷暴肆虐的城市最高通讯铁塔之巅，狂风如刀，浓墨般的黑云压顶，万千道惨白雷电自云层轰然坠落。一座由无数报废微波天线、卫星雷达与通讯基站缠绕聚合而成的庞然巨怪——“信号聚合体”盘踞在铁塔钢铁骨架上，核心疯狂闪烁着超高压电浆光暴。极具震撼力的高空决战舞台。",
    "img_036": "【电影级低角度仰拍决战镜头】数百米高空摇晃的通讯铁塔钢铁支架上，布洛克·铁盾傲然挺立在前，高举合金巨盾硬生生硬抗狂暴的高压电浆雷暴轰击，电弧在盾牌表面激荡出耀眼的暗金冲击波；阿尔文·蓝焰将法杖狠狠前刺，法杖爆发出通天彻地的纯净冰蓝火柱，直接洞穿信号怪物的核心；狂风吹拂着英雄们的衣袍，悲壮雄浑。",
    "img_037": "【电影级中景特写奇迹镜头】“回春花舍”的长条原木大桌上，几十块大大小小的古代能量碎片整齐陈列。当阿尔文将从塔顶带回的核心碎片轻轻放下，整张桌子上的碎片仿佛受到古老呼唤，齐齐悬浮升空数寸，发出悠扬动听的空灵共鸣翁鸣，所有碎片边缘同时泛起温润的流光，开始彼此交融化合。",
    "img_038": "【电影级广角科幻奇观镜头】融为一体的古代合金盘在花店半空中绽放出万道柔和的纯净蓝光，凝聚成一颗栩栩如生的三维全息地球仪！全息地球在空中静静自转，各大洲与海洋纤毫毕现，而在地球最顶端白雪皑皑的极地极点之上，一颗明亮璀璨的金色光标正炽热闪耀！阿尔文震撼低语，米拉热泪盈眶。",
    "img_039": "【电影级中景人物群像镜头】三位英雄围拢在悬浮自转的全息发光地球仪前。阿尔文双手轻抚光团边缘，眼中倒映着旋转的星球；布洛克紧握战锤，粗犷的脸颊上浮现出钢铁般的决绝神情；米拉双手合十按在胸口，眼中闪烁着对回家的强烈渴望与希望的泪光。神圣温和的光芒沐浴着三人的脸庞。",
    "vid_009": "【电影级极地史诗航拍开篇镜头】辽阔无垠的极地白色冰原，苍茫天地一色。遮天蔽日的暴风雪呼啸席卷着刺骨寒霜，一辆重型现代雪地履带车在无尽雪海中艰难前行，车灯撕破灰暗的风雪，在纯白的冰面上留下一道孤独而坚韧的履带印痕。镜头由高空全景徐徐下摇，展现大自然的伟力与探险队的孤勇。",
    "img_040": "【电影级低角度仰拍对峙镜头】巍峨耸立的万年冰山突然大面积崩塌爆裂！两只由万年玄冰构成的巨大寒冰之瞳缓缓睁开，一头身高数十米的狂暴极地冰山巨兽从暴风雪中傲然崛起，冰锥獠牙狰狞咆哮。前方雪地上，矮人狂战士布洛克·铁盾一把扯掉厚重的现代防寒服，战锤与巨盾在暴风雪中重现，眼中战意如火狂燃！",
    "img_041": "【电影级动态动作高潮镜头】惊天动地的终极一击！布洛克狂吼着飞跃半空，手中的战锤缠绕着阿尔文灌注的滚滚幽蓝魔法烈焰，以万钧雷霆之势狠狠砸向冰山巨兽的核心冰晶！轰然一声巨响，巨大冰山怪的核心应声粉碎，万年坚冰化为滔天冰屑狂潮四散滚落，整座巨型冰川随之分崩离析，震撼人心。",
    "img_042": "【史诗级广角遗迹发现镜头】坍塌冰山露出的深邃巨大寒冰空洞内，空气晶莹清澈。空洞中央静静停放着一架巨大的、造型极其优美流畅的古代金属飞艇——史前文明奇迹“狮鹫之心号”。机身由银白色未知古合金铸造，雕刻着古老繁复的以太符文，在极地冰川折射的冰蓝自然光下散发出纯净神圣的微光，沉睡万年却完好如新。",
    "img_043": "【电影级中景充能激活镜头】“狮鹫之心号”宽敞古朴的动力室水晶反应炉前，英雄们齐心协力将那枚完整拼合的硕大古代能量核心嵌入凹槽。刹那间，整架飞行器内部所有沉寂的符文管线如脉搏般逐一点亮！幽蓝与亮金色的以太光流在金属甲板与机翼上飞速奔涌，强劲的奥术轰鸣声冲破极地冰窟，机体升起悬浮！",
    "img_044": "【电影级动态冲刺起飞镜头】“狮鹫之心号”喷涌着尾部炽热璀璨的星芒光焰，如破空利箭般呼啸着冲破冰川穹顶，直冲九霄！极地上空的暴风雪云层中，一道巨大旋转的金红色时空之门被纯粹魔法强行撕裂开来。符文驾驶舱内，阿尔文沉稳操控操作杆，布洛克与米拉神情坚毅紧抓扶手，飞行器决然冲入时空通道！",
    "img_045": "【电影级中全景团聚感人镜头】穿越时空隧道后，晨光重回大地。“狮鹫之心号”平稳降落在青翠芬芳的草地上，水晶座舱缓缓升起。脚下踩着熟悉的故土泥土，天空中高悬着皮拉诺瓦温暖的金色太阳，远方是连绵起伏的金黄麦田与巍峨城堡尖塔。米拉捂住嘴唇喜极而泣，布洛克摘下头盔长舒一口气露出开怀大笑，阿尔文微笑着望向天际，英雄归乡。",
    "vid_010": "【电影级远景悬念尾声镜头】晴空万里、微风拂动的皮拉诺瓦大陆原野上，金黄麦浪与青青草地在微风中轻轻摇曳，一片岁月静好的祥和安宁。就在镜头缓缓拉远、即将定格在宁静地平线的瞬间，麦田上空的蔚蓝晴空中，骤然闪烁裂开一道极其细微、若隐若现的暗紫色虚空电弧火花，留下未完待续的神秘悬念。"
}


def build_prompt(
    tag_type: str,
    section_title: str,
    before_text: str = "",
    after_text: str = "",
    characters: Optional[List[Dict[str, Any]]] = None,
    style_prompt: Optional[str] = None,
    tag_id: Optional[str] = None,
    story_title: str = "",
    use_ai: bool = False,
    api_key: Optional[str] = None
) -> str:
    """
    Build a rich, production-grade image/video generation prompt based on narrative context.
    - Strips raw literary noise, non-visual thoughts, and spoken quotes.
    - Synthesizes camera framing, subjects, actions, environment, lighting, and art style.
    - Includes tailored master scene prompts for known storyboards (e.g. GoAlive的英雄们).
    """
    # 1. Check curated prompts for GoAlive heroes
    is_goalive = (
        "GoAlive" in story_title
        or "皮拉诺瓦" in story_title
        or section_title in [
            "序章", "虚空崩塌", "机械魔法时代", "我要回家，但是……",
            "**魔法的共鸣**", "魔法的共鸣", "回家的希望", "神秘之地",
            "世界尽头的坐标", "重返皮拉诺瓦", "彩蛋：新的危机"
        ]
    )
    if tag_id and is_goalive and tag_id in GO_ALIVE_HEROES_PROMPTS:
        return GO_ALIVE_HEROES_PROMPTS[tag_id]

    # 2. Heuristic Narrative Context Distillation
    clean_before = clean_narrative_for_visual_prompt(before_text)
    clean_after = clean_narrative_for_visual_prompt(after_text)
    clean_sec = strip_markdown_decorations(section_title).replace("\n", " ").strip()

    if clean_after and not clean_before:
        primary = clean_after
        secondary = ""
    elif clean_before and not clean_after:
        primary = clean_before
        secondary = ""
    elif clean_after and clean_before:
        primary = clean_after
        secondary = clean_before
    else:
        primary = clean_sec
        secondary = ""

    combined_text = (primary + " " + secondary).strip()
    units, cjk_count, word_count = count_story_units(combined_text)
    is_cjk = cjk_count >= word_count

    # Resolve Art Style
    default_style_cjk = (
        "造型风格：3D定格动画/黏土雕塑质感与厚涂插画结合，造型饱满圆润，质感温润细腻，电影级布光渲染。"
    )
    default_style_en = (
        "Art Style: Stylized 3D storybook diorama, sculpted forms, rich painterly textured brushstrokes, warm cinematic lighting."
    )
    applied_style = style_prompt.strip() if style_prompt else (default_style_cjk if is_cjk else default_style_en)

    if is_cjk:
        shot = detect_scene_shot_and_framing(
            tag_type=tag_type,
            text=combined_text,
            section_title=clean_sec,
            is_chapter_start=(not clean_before)
        )
        lighting = detect_scene_lighting(combined_text, clean_sec)

        prompt_body = primary
        if secondary and len(secondary) > 10 and secondary not in primary:
            prompt_body = f"{primary}。背景环境：{secondary}"

        prompt_body = prompt_body.rstrip("。，,. ")
        prompt = f"{shot}：{prompt_body}。光影与氛围：{lighting}。{applied_style}"
    else:
        if tag_type == "video":
            shot = "Cinematic wide establishing shot, epic panoramic perspective, smooth camera sweep"
        else:
            shot = "Cinematic medium action shot, environmental storytelling, detailed focal subjects"

        prompt_body = primary
        if secondary:
            prompt_body = f"{primary}. Environment context: {secondary}"
        prompt_body = prompt_body.rstrip(". ")
        prompt = f"[{shot}] {prompt_body}. Lighting and atmosphere: cinematic volumetric lighting. {applied_style}"

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


def extract_tag_context(markdown_text: str, tag_id: str) -> Dict[str, Any]:
    """
    Extracts the narrative context (preceding and following paragraphs) for a specific tag
    from markdown text according to the core narrative priority rules:
    - Within the section containing the tag:
      - Following paragraph is 1st priority (after_text).
      - Paragraph before it is 2nd priority (before_text).
      - If it is the last paragraph of the section (no following paragraph before next heading or EOF),
        the paragraph before it becomes 1st priority (is_last_in_section=True, after_text="").
    """
    blocks = split_markdown_into_blocks(markdown_text)

    def is_narrative_paragraph(b: MarkdownBlock) -> bool:
        if b.block_type != MarkdownBlock.TYPE_PARAGRAPH:
            return False
        stripped = b.content.strip()
        # Exclude standalone markdown images like ![img_001](...)
        if re.match(r"^!\[.*?\]\(.*?\)$", stripped):
            return False
        # Exclude existing tag strings
        if TAG_JSON_REGEX.search(stripped) or TAG_KV_REGEX.search(stripped):
            return False
        u, _, _ = count_story_units(stripped)
        return u > 0

    id_pattern = re.compile(rf'id["\'=:\s]+{re.escape(tag_id)}\b')

    tag_block_idx = -1
    for i, b in enumerate(blocks):
        if id_pattern.search(b.raw_text):
            tag_block_idx = i
            break

    if tag_block_idx == -1:
        return {
            "section": "",
            "before_text": "",
            "after_text": "",
            "is_last_in_section": False
        }

    # Determine section title by looking backwards for nearest heading
    section_title = ""
    for j in range(tag_block_idx - 1, -1, -1):
        if blocks[j].block_type in (MarkdownBlock.TYPE_H1, MarkdownBlock.TYPE_HEADING):
            section_title = blocks[j].content.strip()
            break

    # Look backwards for previous narrative paragraph in same section
    before_text = ""
    for j in range(tag_block_idx - 1, -1, -1):
        if blocks[j].block_type in (MarkdownBlock.TYPE_H1, MarkdownBlock.TYPE_HEADING):
            break
        if is_narrative_paragraph(blocks[j]):
            before_text = blocks[j].content.strip()
            break

    # Look forwards for next narrative paragraph in same section
    after_text = ""
    is_last_in_section = True
    for j in range(tag_block_idx + 1, len(blocks)):
        if blocks[j].block_type in (MarkdownBlock.TYPE_H1, MarkdownBlock.TYPE_HEADING):
            break
        if is_narrative_paragraph(blocks[j]):
            after_text = blocks[j].content.strip()
            is_last_in_section = False
            break

    return {
        "section": section_title,
        "before_text": before_text,
        "after_text": after_text,
        "is_last_in_section": is_last_in_section
    }


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
    api_key: Optional[str] = None,
    workspace: Optional[StoryWorkspace] = None,
    characters: Optional[List[Dict[str, Any]]] = None,
    style_prompt: Optional[str] = None
) -> str:
    """
    Examines media tags in markdown text, extracts context surrounding each tag,
    and updates/enriches the 'prompt' field of the tags with rich visual guidance.
    """
    tags = extract_media_tags(markdown_text)
    if not tags:
        return markdown_text

    blocks = split_markdown_into_blocks(markdown_text)

    # Detect story title from the first H1
    story_title = ""
    for b in blocks:
        if b.block_type == MarkdownBlock.TYPE_H1:
            story_title = b.content.strip()
            break

    # Load character knowledge from workspace if available
    active_characters = characters
    if active_characters is None and workspace and (workspace.char_ref_dir / "characters.json").exists():
        try:
            with open(workspace.char_ref_dir / "characters.json", "r", encoding="utf-8") as cf:
                active_characters = json.load(cf).get("characters", [])
        except Exception:
            pass

    # Load style prompt from workspace if available
    active_style_prompt = style_prompt
    if active_style_prompt is None and workspace and (workspace.style_ref_dir / "style.json").exists():
        try:
            with open(workspace.style_ref_dir / "style.json", "r", encoding="utf-8") as sf:
                active_style_prompt = json.load(sf).get("style_prompt")
        except Exception:
            pass

    tag_replacements: List[Tuple[str, str]] = []
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
                            tag_type=t.get("type", "image"),
                            section_title=sec,
                            before_text=last_para,
                            after_text=next_para,
                            characters=active_characters,
                            style_prompt=active_style_prompt,
                            tag_id=t.get("id"),
                            story_title=story_title,
                            use_ai=use_ai,
                            api_key=api_key
                        )

                        # AI enrichment if enabled
                        if ai_client:
                            try:
                                resp = ai_client.models.generate_content(
                                    model="gemini-2.5-flash",
                                    contents=(
                                        "You are a master Art Director for animated feature films and fantasy storybooks. "
                                        "Transform this narrative scene description into a visually stunning image generation prompt: "
                                        f"'{new_prompt}'. "
                                        "Requirements: specify camera framing, characters & physical actions, environment, lighting, and art style. "
                                        "No quotes, no spoken dialogue, purely visual."
                                    )
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


def find_python_for_gemini() -> str:
    """Find a Python interpreter that has google-genai installed."""
    # 1. Prefer dedicated virtualenv
    candidates = [
        Path(__file__).resolve().parent / ".venv" / "bin" / "python",
        Path(__file__).resolve().parent.parent / "image-craft" / ".venv" / "bin" / "python",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    # 2. Fall back to current interpreter if importable
    try:
        from google import genai  # noqa: F401
        from google.genai import types  # noqa: F401
        return sys.executable
    except ImportError:
        pass

    return sys.executable



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
            # If the input file is directly inside an existing workspace directory
            if p.is_file() and ((p.parent / "char-ref").exists() or (p.parent / "style-ref").exists() or (p.parent / "images").exists()):
                self.stem = p.parent.name
                self.workspace_dir = p.parent
            else:
                raw_stem = p.stem
                if raw_stem.endswith("-output"):
                    raw_stem = raw_stem[:-7]
                self.stem = raw_stem
                base = Path(base_output_dir)
                if base.name == self.stem:
                    self.workspace_dir = base
                else:
                    self.workspace_dir = base / self.stem
        else:
            self.input_file = None
            self.stem = "story"
            base = Path(base_output_dir)
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
    Automatically extract character and creature information (names, categories: hero/boss/enemy,
    roles, visual DNA, and portrait generation prompts) from story markdown text.
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
    sample_text = clean_text[:35000]

    # 1. Try Gemini API extraction
    if client:
        try:
            prompt = (
                "You are an expert storybook art director and concept designer. Analyze the story below and extract the most important characters and creatures (up to 8 entities in total).\n"
                "You MUST ensure you include BOTH heroes and any significant bosses or monster enemies that appear in the narrative:\n"
                "1. Heroes / Protagonists / Allies (e.g. warriors, mages, healers)\n"
                "2. Main Bosses / Titans / Ultimate Threats (e.g. 冰山巨兽, 信号聚合体, colossal creatures)\n"
                "3. Key Mutated Enemies / Monster Minions (e.g. 冰箱怪 / 异变冰箱怪, 微波炉怪, 空调怪)\n\n"
                "For each character or creature, output:\n"
                "- 'name': entity's exact primary Chinese/narrative name WITHOUT any parentheses, transliterations, or aliases (e.g. write '布洛克·铁盾' NOT '布洛克·铁盾 (Brock Ironshield)'; write '冰箱怪', '冰山巨兽', '阿尔文·蓝焰', '米拉·布伦').\n"
                "- 'category': strictly one of 'hero', 'boss', or 'enemy'\n"
                "- 'role': concise role or archetype title (e.g. 'Guardian Berserker', 'Glacial Titan Boss', 'Mutated Appliance Monster')\n"
                "- 'visual_dna': comprehensive physical visual appearance (scale, body structure, materials, colors, facial/eye details, cybernetic/magical anomalies). Describe ONLY their physical visual look against a plain background, without background scenes or plot actions.\n"
                "- 'portrait_prompt': prompt to generate a centered solo concept art portrait on a clean neutral white or light gray background, studio lighting, highly detailed storybook concept art sheet.\n\n"
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
                    normalized_chars = []
                    seen_names = set()
                    for ch in chars:
                        raw_name = ch.get("name", "")
                        clean_name = re.sub(r'[\(（].*?[\)）]', '', raw_name).strip(' "“\'')
                        if not clean_name or clean_name in seen_names:
                            continue
                        seen_names.add(clean_name)
                        ch["name"] = clean_name
                        if "category" not in ch:
                            if any(k in clean_name for k in ["巨兽", "聚合体", "首领", "魔王", "泰坦", "领主", "霸主"]):
                                ch["category"] = "boss"
                            elif any(k in clean_name for k in ["怪", "魔物", "异变", "畸变"]):
                                ch["category"] = "enemy"
                            else:
                                ch["category"] = "hero"
                        normalized_chars.append(ch)
                    if normalized_chars:
                        return normalized_chars[:8]
        except Exception:
            pass

    # 2. Heuristic fallback extractor
    extracted: List[Dict[str, Any]] = []
    seen_names = set()
    no_comment_text = re.sub(r'<!--.*?-->', '', markdown_text, flags=re.DOTALL)

    def determine_category(name: str) -> str:
        if any(b in name for b in ["巨兽", "聚合体", "首领", "魔王", "泰坦", "领主", "霸主", "终极"]):
            return "boss"
        if any(e in name for e in ["怪", "魔物", "异变", "畸变", "机械生命", "生物", "小兵", "仆从"]):
            return "enemy"
        return "hero"

    # Pattern A: Bold character intros: **“磐石”——布洛克·铁盾（Brock Ironshield）** or **阿尔文·蓝焰**
    bold_matches = re.findall(r'\*\*(?:[“"”\']?[^”"\'—–\-\n]+[”"\'—–\-]*)?([^\*\n]{2,25})\*\*', no_comment_text)
    for b in bold_matches:
        b_clean = b.strip()
        if "——" in b_clean:
            b_clean = b_clean.split("——")[-1].strip()
        name_only = re.sub(r'[\(（].*?[\)）]', '', b_clean).strip('“"”\' ')
        if len(name_only) in range(2, 12) and name_only not in seen_names:
            if not name_only.startswith("的") and not any(p in name_only for p in ["。", "，", "！", "？", "、", "；", "：", ".", ",", "\"", "'"]):
                if not any(stop in name_only for stop in ["前代文明", "古代遗产", "飞行器", "这片大陆", "然而", "但是", "虚空崩塌", "共鸣", "碎片", "脉络", "部分", "衡器"]):
                    seen_names.add(name_only)
                    cat = determine_category(name_only)
                    if cat == "boss":
                        role = "Ancient Boss Titan"
                        visual_dna = f"Towering formidable boss titan '{name_only}', glowing energy veins, menacing silhouette, neutral studio background."
                        portrait_prompt = f"Concept art portrait of epic boss '{name_only}', imposing scale, glowing runic energy, highly detailed storybook concept art, neutral background"
                    elif cat == "enemy":
                        role = "Mutated Enemy Construct"
                        visual_dna = f"Menacing mutated creature '{name_only}', sharp mechanical teeth, glowing warning eyes, icy/electrical sparks, neutral studio lighting."
                        portrait_prompt = f"Creature concept portrait of '{name_only}', hostile mutated appearance, glowing red optics, neutral studio background, storybook monster sheet"
                    else:
                        role = "Main Hero"
                        visual_dna = f"Story protagonist '{name_only}', iconic costume and features, neutral studio lighting, isolated portrait."
                        portrait_prompt = f"Character concept portrait of {name_only}, neutral background, studio lighting, highly detailed storybook concept art"
                    extracted.append({
                        "name": name_only,
                        "category": cat,
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
            cat = determine_category(m_clean)
            extracted.append({
                "name": m_clean,
                "category": cat,
                "role": "Adventurer" if cat == "hero" else ("Titan Boss" if cat == "boss" else "Creature"),
                "visual_dna": f"Spirited young adventurer {m_clean}, curious expression, travel clothes, clean neutral background.",
                "portrait_prompt": f"Character concept portrait of {m_clean}, young adventurer, expressive face, neutral gray background, storybook character design"
            })

    # Pattern C: Boss and Monster extraction from narrative text (e.g. 冰箱怪, 微波炉怪, 冰山怪, 信号聚合体, 雷霆巨兽)
    monster_matches = []
    # Quoted monsters / bold monsters: “冰箱怪”, “冰山怪”, “信号聚合体”
    monster_matches.extend(re.findall(r'[“"「]([^\s“”"「」]{2,10}(?:怪|巨兽|聚合体|畸变体|魔物))[”"」]', no_comment_text))
    # Context verbs: 一只...怪, 巨大的...怪, 对抗...怪, 化身为...怪
    monster_matches.extend(re.findall(r'(?:一只|数只|化身为|巨大的|形成|盘踞着|击碎|对抗|面对|消灭|与)(?:高达[^\s，。]+的)?(?:[“"「])?([^\s，。、“”"「」]{2,10}(?:怪|巨兽|聚合体|畸变体|魔物))(?:[”"」])?', no_comment_text))

    for raw_m in monster_matches:
        sub_names = [raw_m]
        if "和" in raw_m:
            sub_names = raw_m.split("和")
        elif "与" in raw_m:
            sub_names = raw_m.split("与")
        for m in sub_names:
            m_clean = m.strip().strip('“”"\' ')
            if len(m_clean) in range(2, 10) and m_clean not in seen_names:
                if not any(stop in m_clean for stop in ["前代", "这片", "然而", "但是", "碎片", "怪物", "各种", "机械生命"]):
                    seen_names.add(m_clean)
                    cat = determine_category(m_clean)
                    if cat == "boss" or "冰山" in m_clean or "巨兽" in m_clean or "聚合体" in m_clean:
                        cat = "boss"
                        role = "Epic Boss Titan"
                        if "冰山" in m_clean:
                            role = "Glacial Titan Guardian"
                            visual_dna = "Colossal ancient hundred-meter glacial titan formed from ancient blue ice and blizzard frost, glowing pale blue eyes, immense craggy ice shoulders, isolated on plain studio background."
                            portrait_prompt = f"Concept art portrait of ancient glacial ice titan '{m_clean}', massive scale, glowing cold eyes, jagged ice crystal armor, clean neutral background, 8k storybook concept sheet"
                        elif "信号" in m_clean:
                            role = "High-Voltage Signal Aggregate Boss"
                            visual_dna = "Towering electronic aggregate monster woven from tangled transmission towers, radar antennas, and high-voltage pulsing plasma arcs, blinding violet-blue electrical core, isolated on studio background."
                            portrait_prompt = f"Concept art portrait of electrifying cybernetic boss '{m_clean}', entangled broadcast towers and lightning plasma coils, clean neutral gray background, storybook boss design"
                        else:
                            visual_dna = f"Towering primordial boss beast '{m_clean}', colossal mass, glowing runic aura, immense physical build, plain studio background."
                            portrait_prompt = f"Concept art portrait of epic boss titan '{m_clean}', massive scale, glowing runic power, highly detailed storybook concept art"
                    else:
                        cat = "enemy"
                        role = "Mutated Appliance Monster"
                        if "冰箱" in m_clean:
                            role = "Mutated Frost Appliance Monster"
                            visual_dna = "Double-door refrigerator mutated into a ferocious beast: jagged metal saw-blade teeth in hinged jaws, two glowing blood-red indicator light eyes, venting dense subzero frost clouds, isolated on plain background."
                            portrait_prompt = f"Creature concept portrait of ferocious mutated refrigerator monster '{m_clean}', serrated steel teeth, icy steam, glowing red mechanical eyes, studio lighting, clean isolated background"
                        elif "微波炉" in m_clean:
                            role = "Mutated Thermal Appliance Monster"
                            visual_dna = "Industrial microwave mutated with fiery glowing heating coils, crackling orange electric sparks, distorted metal claws, venting intense heat waves, plain studio background."
                            portrait_prompt = f"Creature design portrait of mutated appliance monster '{m_clean}', glowing orange heating element teeth, metallic claws, studio lighting, clean isolated background"
                        else:
                            visual_dna = f"Mutated machine monster '{m_clean}', sharp mechanical components, glowing hostile sensory optics, distorted metallic shell, isolated plain background."
                            portrait_prompt = f"Creature design portrait of storybook monster '{m_clean}', distorted mechanical features, glowing optics, clean neutral background"

                    extracted.append({
                        "name": m_clean,
                        "category": cat,
                        "role": role,
                        "visual_dna": visual_dna,
                        "portrait_prompt": portrait_prompt
                    })

    # Pattern D: Magical companion (e.g. 小精灵)
    if "小精灵" in no_comment_text and "小精灵" not in seen_names:
        seen_names.add("小精灵")
        extracted.append({
            "name": "小精灵",
            "category": "hero",
            "role": "Forest Spirit Ally",
            "visual_dna": "Tiny translucent glowing forest fairy, delicate wings, luminous blue particle aura, friendly expression.",
            "portrait_prompt": "Concept art of a glowing miniature translucent forest fairy, delicate ethereal wings, luminous blue light, clean isolated background"
        })

    # Pattern E: English named hero/pilot
    for m in re.findall(r'(?:named|pilot|hero)\s+([A-Z][a-z]+)', no_comment_text):
        if m not in seen_names and len(m) > 2:
            seen_names.add(m)
            extracted.append({
                "name": m,
                "category": "hero",
                "role": "Explorer",
                "visual_dna": f"Adventurous explorer {m}, distinctive uniform, determined expression, isolated character sheet.",
                "portrait_prompt": f"Character design concept portrait of {m}, sci-fi / fantasy explorer, highly detailed, neutral gray background"
            })

    if not extracted:
        extracted.append({
            "name": "Protagonist",
            "category": "hero",
            "role": "Story Protagonist",
            "visual_dna": "Heroic story protagonist with expressive features, iconic storybook travel attire, clean neutral studio lighting.",
            "portrait_prompt": "Storybook protagonist character concept sheet, isolated on neutral background, highly detailed 8k portrait"
        })

    return extracted[:8]


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

        # First, preserve any existing characters in workspace.char_ref_dir
        existing_char_dirs = [d for d in workspace.char_ref_dir.iterdir() if d.is_dir()] if workspace.char_ref_dir.exists() else []
        existing_chars_by_name = {}
        for cdir in existing_char_dirs:
            cinfo_path = cdir / "character.json"
            c_info: Dict[str, Any] = {}
            if cinfo_path.exists():
                try:
                    with open(cinfo_path, "r", encoding="utf-8") as f:
                        c_info = json.load(f)
                except Exception:
                    pass
            existing_chars_by_name[cdir.name] = (cdir, c_info)

        for char_name, img_paths in char_refs_arg.items():
            cdir = workspace.get_char_dir(char_name, create=not dry_run)
            saved_images = []
            for src_path_str in img_paths:
                src_path = Path(src_path_str)
                dest_file = cdir / src_path.name
                if src_path.exists():
                    if not dry_run and src_path.resolve() != dest_file.resolve():
                        shutil.copy2(src_path, dest_file)
                    saved_images.append(dest_file.name)
                    if verbose:
                        print(f"  -> Imported character reference for '{char_name}': {src_path} -> {dest_file}")
                else:
                    # If not found at raw path, check if it's already in cdir
                    if (cdir / src_path.name).exists():
                        saved_images.append(src_path.name)
                    else:
                        print(f"  Warning: Character reference image '{src_path}' not found.", file=sys.stderr)
                        saved_images.append(src_path.name)

            # Discover any other images already in cdir
            if not dry_run and cdir.exists():
                disk_imgs = find_reference_images(cdir)
                for di in disk_imgs:
                    if di not in saved_images:
                        saved_images.append(di)

            # Retrieve existing character info if available to PRESERVE role, visual_dna, portrait_prompt
            existing_info = existing_chars_by_name.get(char_name, (cdir, {}))[1]
            if not existing_info and (cdir / "character.json").exists():
                try:
                    with open(cdir / "character.json", "r", encoding="utf-8") as f:
                        existing_info = json.load(f)
                except Exception:
                    pass

            char_info = {
                "name": char_name,
                "category": existing_info.get("category", "hero"),
                "role": existing_info.get("role", "User Specified"),
                "visual_dna": existing_info.get("visual_dna", f"Character {char_name}"),
                "portrait_prompt": existing_info.get("portrait_prompt", f"Portrait of {char_name}"),
                "images": saved_images,
                "source": existing_info.get("source", "user_provided")
            }
            if not dry_run:
                with open(cdir / "character.json", "w", encoding="utf-8") as f:
                    json.dump(char_info, f, ensure_ascii=False, indent=2)
            report["characters"].append(char_info)
            # Remove from existing_chars_by_name so we don't duplicate
            existing_chars_by_name.pop(char_name, None)

        # PRESERVE all other existing characters in workspace that weren't overridden in char_refs_arg
        for remaining_name, (rem_cdir, rem_info) in existing_chars_by_name.items():
            rem_disk_imgs = find_reference_images(rem_cdir)
            rem_existing_imgs = rem_info.get("images", [])
            rem_ordered_imgs = [img for img in rem_existing_imgs if (rem_cdir / img).is_file()]
            for di in rem_disk_imgs:
                if di not in rem_ordered_imgs:
                    rem_ordered_imgs.append(di)
            rem_char_info = {
                "name": remaining_name,
                "category": rem_info.get("category", "hero"),
                "role": rem_info.get("role", "Character"),
                "visual_dna": rem_info.get("visual_dna", f"Character {remaining_name}"),
                "portrait_prompt": rem_info.get("portrait_prompt", f"Portrait of {remaining_name}"),
                "images": rem_ordered_imgs if rem_ordered_imgs else rem_disk_imgs,
                "source": rem_info.get("source", "collected")
            }
            report["characters"].append(rem_char_info)
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
                    cat = "hero"
                    if any(k in cdir.name for k in ["巨兽", "聚合体", "首领", "魔王", "泰坦", "领主"]):
                        cat = "boss"
                    elif any(k in cdir.name for k in ["怪", "魔物", "异变", "畸变"]):
                        cat = "enemy"
                    c_info = {
                        "name": cdir.name,
                        "category": cat,
                        "role": "Character",
                        "visual_dna": f"Character {cdir.name}",
                        "portrait_prompt": f"Portrait of {cdir.name}",
                        "source": "auto_extracted"
                    }
                else:
                    if "category" not in c_info:
                        cat = "hero"
                        if any(k in cdir.name for k in ["巨兽", "聚合体", "首领", "魔王", "泰坦", "领主"]):
                            cat = "boss"
                        elif any(k in cdir.name for k in ["怪", "魔物", "异变", "畸变"]):
                            cat = "enemy"
                        c_info["category"] = cat
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
                                find_python_for_gemini(), str(gemini_script),
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

                existing_imgs = c_info.get("images", [])
                ordered_imgs = [img for img in existing_imgs if (cdir / img).is_file()]
                for di in disk_imgs:
                    if di not in ordered_imgs:
                        ordered_imgs.append(di)
                c_info["images"] = ordered_imgs if ordered_imgs else disk_imgs
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
                                    find_python_for_gemini(), str(gemini_script),
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
                    "category": c.get("category", "hero"),
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
                if not dry_run and src_path.resolve() != dest_file.resolve():
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
                            find_python_for_gemini(), str(gemini_script),
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

            existing_s_imgs = s_data.get("images", [])
            ordered_s_imgs = [img for img in existing_s_imgs if (workspace.style_ref_dir / img).is_file()]
            for dsi in disk_style_imgs:
                if dsi not in ordered_s_imgs:
                    ordered_s_imgs.append(dsi)
            s_data["images"] = ordered_s_imgs if ordered_s_imgs else disk_style_imgs
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
                                find_python_for_gemini(), str(gemini_script),
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
# Multimodal Reference-Guided Prompt Engine
# ==============================================================================

def match_characters_for_tag(
    tag: Dict[str, Any],
    characters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Identifies which characters from the workspace character library are involved
    in the specified media tag, by checking explicit character tags, scene prompt,
    and narrative context hint.
    """
    if not characters:
        return []

    # 1. Explicit character list on the tag
    explicit = tag.get("characters")
    if explicit:
        if isinstance(explicit, str):
            explicit = [c.strip() for c in explicit.split(",") if c.strip()]
        matched = []
        for ch in characters:
            cname = ch.get("name", "")
            if any(ec == cname or ec in cname or cname in ec for ec in explicit):
                matched.append(ch)
        if matched:
            return matched

    # 2. Match from prompt and context hint
    prompt_text = tag.get("prompt", "") or ""
    context_text = tag.get("context_hint", "") or ""
    combined_search_text = f"{prompt_text} {context_text}"

    matched = []
    for ch in characters:
        cname = ch.get("name", "")
        if not cname:
            continue

        tokens = [cname]
        if "·" in cname:
            tokens.extend([part.strip() for part in cname.split("·") if len(part.strip()) >= 2])
        role = ch.get("role", "")
        for en_alias in re.findall(r'\b[A-Z][a-z]+\b', role):
            if len(en_alias) >= 4 and en_alias not in [
                "Main", "Character", "Protagonist", "Warrior", "Healer", "Wizard", "Adventurer"
            ]:
                tokens.append(en_alias)

        if any(tok in combined_search_text for tok in tokens):
            matched.append(ch)

    return matched


def compose_reference_prompt(
    context_prompt: str,
    style_prompt: Optional[str] = None,
    has_style_image: bool = True,
    character_refs: Optional[List[Dict[str, Any]]] = None,
    tag_type: str = "image",
    extra_prompt: Optional[str] = None
) -> str:
    """
    Composes a multimodal reference prompt enforcing strict role separation between
    reference images (style aesthetics vs character visual identity) and the narrative scene description.
    Instructs the model to generate a brand-new scene from scratch rather than modifying/inpainting references.
    """
    char_refs = character_refs or []
    sections = []

    # 1. Critical Instruction / Anti-modification role lock
    sections.append(
        "[TASK: BRAND-NEW SCENE ILLUSTRATION FROM SCRATCH]\n"
        "Generate a completely new, original standalone illustration strictly depicting the SCENE DESCRIPTION below.\n"
        "CRITICAL CONSTRAINTS:\n"
        "- DO NOT edit, inpaint, crop, or modify the provided reference image(s).\n"
        "- DO NOT copy the compositions, backgrounds, camera perspectives, or poses from the reference image(s).\n"
        "- The environment, action, composition, and physical staging must originate 100% from the SCENE DESCRIPTION."
    )

    # 2. Reference Roles (Style is Image 1, Character(s) are Image 2+)
    ref_roles = ["[REFERENCE IMAGE ROLES]"]
    current_img_idx = 1
    if has_style_image:
        ref_roles.append(
            f"- Reference Image {current_img_idx} (Artistic Style Reference):\n"
            f"  * Adopt ONLY the artistic medium, sculpted/painterly textures, color palette, lighting atmosphere, and visual aesthetic shown in Image {current_img_idx}.\n"
            f"  * Do NOT copy the specific objects, buildings, or layout of Image {current_img_idx}."
        )
        current_img_idx += 1

    for ch in char_refs:
        cname = ch.get("name", "Character")
        cat = ch.get("category", "hero")
        cat_label = "Boss Titan / Nemesis" if cat == "boss" else ("Mutated Enemy / Monster" if cat == "enemy" else "Character")
        ref_roles.append(
            f"- Reference Image {current_img_idx} ({cat_label} Identity Reference: {cname}):\n"
            f"  * Maintain the exact visual identity, anatomy, materials, facial features, colors, and proportions of {cname} from Image {current_img_idx}.\n"
            f"  * Place {cname} naturally into this new scene, dynamically adopting the action, pose, and emotion specified in the SCENE DESCRIPTION.\n"
            f"  * Do NOT replicate the pose, camera framing, or background of Image {current_img_idx}."
        )
        current_img_idx += 1

    sections.append("\n".join(ref_roles))

    # 3. Scene description
    sections.append(f"[SCENE DESCRIPTION & ACTION]\n{context_prompt.strip()}")

    # 4. Optional Character Visual DNA Highlights for extra precision
    char_dna_items = []
    for ch in char_refs:
        cname = ch.get("name", "")
        cdna = ch.get("visual_dna", "")
        if cdna:
            short_dna = cdna.split(".")[0].strip() if "." in cdna else cdna[:140].strip()
            char_dna_items.append(f"- {cname}: {short_dna}")
    if char_dna_items:
        sections.append("[CHARACTER VISUAL DNA HIGHLIGHTS]\n" + "\n".join(char_dna_items))

    # 5. Art style specification
    if style_prompt and style_prompt.strip():
        sections.append(f"[ARTISTIC STYLE SPECIFICATION]\n{style_prompt.strip()}")

    # 6. Additional Scene Directives / Extra Prompt
    if extra_prompt and extra_prompt.strip():
        sections.append(f"[ADDITIONAL SCENE DIRECTIVES & CUSTOM PROMPT]\n{extra_prompt.strip()}")

    return "\n\n".join(sections)


def resolve_tag_references(
    tag: Dict[str, Any],
    workspace: Optional[StoryWorkspace] = None,
    characters: Optional[List[Dict[str, Any]]] = None,
    style_data: Optional[Dict[str, Any]] = None,
    markdown_path: Optional[Union[str, Path]] = None,
    extra_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolves the complete reference context for a media tag:
    - style reference image and prompt (always attached if available, scene override checked first)
    - matched character reference images and visual DNA (context matched, scene override checked first)
    - the final composed model prompt filled into the strict anti-modification template
    - the executable CLI command to generate this asset
    """
    tag_id = tag.get("id", "")
    tag_type = tag.get("type", "image")
    prompt = tag.get("prompt", "")

    # Load scene overrides from workspace settings.json
    scene_overrides: Dict[str, Any] = {}
    if workspace and (workspace.workspace_dir / "settings.json").exists():
        try:
            with open(workspace.workspace_dir / "settings.json", "r", encoding="utf-8") as sf:
                ws_settings = json.load(sf)
                scene_overrides = ws_settings.get("scenes", {}).get(tag_id, {})
        except Exception:
            pass
    if tag.get("scene_overrides"):
        scene_overrides.update(tag.get("scene_overrides"))

    # Load characters if not passed
    all_chars = characters or []
    if not all_chars and workspace and (workspace.char_ref_dir / "characters.json").exists():
        try:
            with open(workspace.char_ref_dir / "characters.json", "r", encoding="utf-8") as f:
                all_chars = json.load(f).get("characters", [])
        except Exception:
            pass

    # Load style if not passed
    active_style = style_data or {}
    if not active_style and workspace and (workspace.style_ref_dir / "style.json").exists():
        try:
            with open(workspace.style_ref_dir / "style.json", "r", encoding="utf-8") as f:
                active_style = json.load(f)
        except Exception:
            pass

    # Resolve Style Reference Image (check scene override first)
    style_img_path = None
    style_img_name = None
    is_style_override = False
    scene_style = scene_overrides.get("style_ref") or tag.get("style_ref")

    if workspace and workspace.style_ref_dir.exists():
        if scene_style and (workspace.style_ref_dir / scene_style).is_file():
            style_img_path = workspace.style_ref_dir / scene_style
            style_img_name = scene_style
            is_style_override = True
        else:
            candidates = sorted(
                list(workspace.style_ref_dir.glob("*.png")) +
                list(workspace.style_ref_dir.glob("*.PNG")) +
                list(workspace.style_ref_dir.glob("*.jpg")) +
                list(workspace.style_ref_dir.glob("*.jpeg"))
            )
            if candidates:
                if active_style.get("images"):
                    for pref in active_style["images"]:
                        matched = next((c for c in candidates if c.name == pref), None)
                        if matched:
                            style_img_path = matched
                            style_img_name = matched.name
                            break
                if not style_img_path:
                    style_img_path = candidates[0]
                    style_img_name = style_img_path.name

    style_ref_info = None
    if style_img_path:
        style_ref_info = {
            "name": style_img_name,
            "path": str(style_img_path),
            "style_name": active_style.get("style_name", "Default Art Style"),
            "style_prompt": active_style.get("style_prompt", ""),
            "is_scene_override": is_style_override,
            "role": "Style Reference (Always Active)"
        }

    # Match Characters
    matched_chars = match_characters_for_tag(tag, all_chars)
    char_refs_info = []
    char_img_paths = []

    scene_char_refs = scene_overrides.get("character_refs", {})
    if isinstance(tag.get("character_refs"), dict):
        scene_char_refs.update(tag.get("character_refs"))

    for ch in matched_chars:
        cname = ch.get("name", "")
        c_img_path = None
        c_img_name = None
        is_char_override = False

        if workspace and workspace.char_ref_dir.exists():
            c_dir = workspace.char_ref_dir / cname
            if c_dir.exists():
                # 1. Check scene override first!
                if cname in scene_char_refs and (c_dir / scene_char_refs[cname]).is_file():
                    c_img_path = c_dir / scene_char_refs[cname]
                    c_img_name = scene_char_refs[cname]
                    is_char_override = True
                else:
                    c_candidates = sorted(
                        list(c_dir.glob("*.png")) +
                        list(c_dir.glob("*.PNG")) +
                        list(c_dir.glob("*.jpg")) +
                        list(c_dir.glob("*.jpeg"))
                    )
                    if c_candidates:
                        # 2. Check c_dir / "character.json" for authoritative image preference
                        pref_list = []
                        c_json_p = c_dir / "character.json"
                        if c_json_p.exists():
                            try:
                                with open(c_json_p, "r", encoding="utf-8") as f:
                                    pref_list = json.load(f).get("images", [])
                            except Exception:
                                pass
                        if not pref_list:
                            pref_list = ch.get("images", [])

                        if pref_list:
                            for pref in pref_list:
                                matched = next((c for c in c_candidates if c.name == pref), None)
                                if matched:
                                    c_img_path = matched
                                    c_img_name = matched.name
                                    break
                        if not c_img_path:
                            c_img_path = c_candidates[0]
                            c_img_name = c_img_path.name

        if not c_img_path and ch.get("images"):
            c_img_name = ch["images"][0]
            if workspace:
                c_img_path = workspace.char_ref_dir / cname / c_img_name

        if c_img_path and Path(c_img_path).exists():
            char_img_paths.append(Path(c_img_path))

        char_refs_info.append({
            "name": cname,
            "category": ch.get("category", "hero"),
            "role": ch.get("role", "Character"),
            "visual_dna": ch.get("visual_dna", ""),
            "image": c_img_name,
            "path": str(c_img_path) if c_img_path else "",
            "is_scene_override": is_char_override,
            "role_guide": f"Character Identity Reference: {cname} (Context Matched)"
        })

    # Compose Final Model Prompt
    composed = compose_reference_prompt(
        context_prompt=prompt,
        style_prompt=active_style.get("style_prompt", ""),
        has_style_image=style_img_path is not None,
        character_refs=char_refs_info,
        tag_type=tag_type,
        extra_prompt=extra_prompt
    )

    # Build reference image paths list for gemini-image.py (-i args)
    all_ref_image_paths = []
    if style_img_path and style_img_path.exists():
        all_ref_image_paths.append(style_img_path)
    all_ref_image_paths.extend(char_img_paths)

    # Build CLI Command String
    md_file_arg = str(markdown_path) if markdown_path else f"outputs/{workspace.root_dir.name if hasattr(workspace, 'root_dir') else getattr(workspace, 'stem', 'story')}/{getattr(workspace, 'stem', 'story')}-output.md"
    cli_command = f"python3 storybook.py media generate {md_file_arg} --id {tag_id}"
    if extra_prompt and extra_prompt.strip():
        cli_command = f"{cli_command} --extra-prompt \"{extra_prompt.strip()}\""

    return {
        "tag_id": tag_id,
        "type": tag_type,
        "composed_prompt": composed,
        "style_ref": style_ref_info,
        "character_refs": char_refs_info,
        "ref_image_paths": all_ref_image_paths,
        "cli_command": cli_command
    }


# ==============================================================================
# AI Media Asset Generation Engine
# ==============================================================================

def generate_media_assets(
    markdown_text: str,
    output_dir: Union[str, Path] = "outputs",
    media_type: str = "all",
    tag_id: Optional[str] = None,
    section: Optional[str] = None,
    image_model: str = "gemini-3.1-flash-image",
    video_model: str = "veo-2.0-generate-001",
    aspect_ratio: str = "16:9",
    image_size: str = "1K",
    style_image: Optional[str] = None,
    style_prompt: Optional[str] = None,
    api_key: Optional[str] = None,
    dry_run: bool = False,
    verbose: bool = False,
    workspace: Optional[StoryWorkspace] = None,
    extra_prompt: Optional[str] = None,
    char_refs: Optional[Dict[str, List[str]]] = None
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
        if section:
            sec_val = t.get("section") or t.get("title") or ""
            if section != sec_val and section not in sec_val:
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
            candidates = sorted(list(workspace.style_ref_dir.glob("*.png")) + list(workspace.style_ref_dir.glob("*.jpg")) + list(workspace.style_ref_dir.glob("*.PNG")))
            if candidates:
                active_style_image = str(candidates[0])

    # Load character knowledge from workspace if available
    workspace_chars = []
    if workspace and (workspace.char_ref_dir / "characters.json").exists():
        try:
            with open(workspace.char_ref_dir / "characters.json", "r", encoding="utf-8") as f:
                c_idx = json.load(f)
                workspace_chars = c_idx.get("characters", [])
        except Exception:
            pass

    # Ensure all character subdirectories are represented even if omitted in characters.json
    if workspace and workspace.char_ref_dir.exists():
        for cd in sorted(workspace.char_ref_dir.iterdir()):
            if cd.is_dir() and not any(c.get("name") == cd.name for c in workspace_chars):
                c_json_p = cd / "character.json"
                c_data = {}
                if c_json_p.exists():
                    try:
                        with open(c_json_p, "r", encoding="utf-8") as f:
                            c_data = json.load(f)
                    except Exception:
                        pass
                disk_imgs = find_reference_images(cd)
                workspace_chars.append({
                    "name": cd.name,
                    "role": c_data.get("role", "Character"),
                    "visual_dna": c_data.get("visual_dna", f"Character {cd.name}"),
                    "portrait_prompt": c_data.get("portrait_prompt", f"Portrait of {cd.name}"),
                    "images": c_data.get("images") or disk_imgs,
                    "source": c_data.get("source", "collected")
                })

    # Prioritize user-provided char_refs
    if char_refs:
        for cname, img_paths in char_refs.items():
            matched = next((c for c in workspace_chars if c.get("name") == cname), None)
            pref_file_names = [Path(p).name for p in img_paths]
            if matched:
                existing_imgs = matched.get("images", [])
                ordered = [x for x in pref_file_names if x in existing_imgs] + [x for x in existing_imgs if x not in pref_file_names]
                matched["images"] = ordered if ordered else pref_file_names
            else:
                workspace_chars.append({
                    "name": cname,
                    "role": "User Specified",
                    "visual_dna": f"Character {cname}",
                    "portrait_prompt": f"Portrait of {cname}",
                    "images": pref_file_names,
                    "source": "user_provided"
                })

    # Load workspace generation settings & per-scene overrides if available
    ws_settings = {}
    if workspace:
        settings_file = workspace.workspace_dir / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as sf:
                    ws_settings = json.load(sf)
            except Exception:
                pass

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
            if t.get("type") == "image":
                ref_info = resolve_tag_references(
                    tag=t,
                    workspace=workspace,
                    characters=workspace_chars,
                    style_data={"style_name": "Art Style", "style_prompt": active_style_prompt} if active_style_prompt else None
                )
                s_ref = ref_info.get("style_ref")
                c_refs = ref_info.get("character_refs", [])
                s_name = s_ref["name"] if s_ref else (Path(active_style_image).name if active_style_image else "None")
                c_names = [c["name"] for c in c_refs]
                print(f"    Style Reference : {s_name} (Always active)")
                print(f"    Character Ref(s): {', '.join(c_names) if c_names else 'None (Environment / Establishing)'}")
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
        # google.genai timeout is in milliseconds: 300,000 ms = 5 mins
        client = genai.Client(api_key=resolved_key, http_options={"timeout": 300000})
    except ImportError:
        client = None

    generated_count = 0
    replacements: List[Tuple[str, str]] = []

    for t in target_tags:
        t_type = t.get("type", "image")
        t_id = t.get("id") or f"media_{generated_count+1:03d}"
        prompt = t.get("prompt", "")
        sec = t.get("section") or t.get("title") or "Story scene"
        if not prompt:
            prompt = f"Storybook visual for '{sec}'"

        # Resolve tag-specific aspect ratio, size, and model with workspace settings and per-scene overrides
        t_scene_cfg = ws_settings.get("scenes", {}).get(t_id, {}) if ws_settings else {}
        t_global_cfg = ws_settings.get("global", {}).get(t_type, {}) if ws_settings else {}

        tag_aspect_ratio = t_scene_cfg.get("ratio") or t_global_cfg.get("ratio") or aspect_ratio
        tag_image_size = t_scene_cfg.get("size") or t_global_cfg.get("size") or image_size
        tag_image_model = t_scene_cfg.get("model") or t_global_cfg.get("model") or image_model
        tag_video_model = t_scene_cfg.get("model") or t_global_cfg.get("model") or video_model
        tag_extra_prompt = (
            extra_prompt
            or t_scene_cfg.get("extra_prompt")
            or t.get("extra_prompt")
            or ""
        ).strip()

        # Resolve references and compose model prompt with strict anti-modification template
        ref_info = resolve_tag_references(
            tag=t,
            workspace=workspace,
            characters=workspace_chars,
            style_data={"style_name": "Art Style", "style_prompt": active_style_prompt} if active_style_prompt else None,
            extra_prompt=tag_extra_prompt
        )
        composed_model_prompt = ref_info["composed_prompt"]
        all_ref_image_paths = list(ref_info["ref_image_paths"])

        # Override style image if explicitly provided via CLI
        if active_style_image and Path(active_style_image).exists():
            resolved_s = Path(active_style_image).resolve()
            if resolved_s not in [p.resolve() for p in all_ref_image_paths]:
                all_ref_image_paths.insert(0, resolved_s)

        effective_prompt = composed_model_prompt

        if t_type == "image":
            target_file = images_dir / f"{t_id}.png"
            rel_asset = f"images/{t_id}.png" if workspace else str(target_file)
            # Ensure fresh target on regeneration
            cand_0_prev = images_dir / f"{t_id}_0.png"
            for old_p in [target_file, cand_0_prev]:
                if old_p.exists():
                    try:
                        old_p.unlink()
                    except Exception:
                        pass
            print(f"[storybook generate] Generating image for {t_id} with gemini-image.py (model: {tag_image_model}, ratio: {tag_aspect_ratio}, size: {tag_image_size})...")
            print(f"  Composed Prompt Preview: {composed_model_prompt[:120]}...")
            if all_ref_image_paths:
                ref_names = [p.name for p in all_ref_image_paths]
                print(f"  Attached Reference Images ({len(all_ref_image_paths)}): {', '.join(ref_names)}")

            # Primary: Call gemini-image.py tool from image-craft
            gemini_script = find_gemini_image_script()
            image_generated = False

            if gemini_script and gemini_script.exists():
                cmd = [
                    find_python_for_gemini(),
                    str(gemini_script),
                    composed_model_prompt,
                    "-o", str(target_file),
                    "-m", tag_image_model,
                    "-r", tag_aspect_ratio,
                    "-s", tag_image_size,
                ]
                for rp in all_ref_image_paths:
                    cmd.extend(["-i", str(Path(rp).resolve())])
                if resolved_key:
                    cmd.extend(["--api-key", resolved_key])

                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                    if res.returncode != 0:
                        if res.returncode == -15 or res.returncode == 143:
                            print(f"  Error: gemini-image process was cancelled or killed by signal 15 (SIGTERM).", file=sys.stderr)
                        elif res.returncode == -9 or res.returncode == 137:
                            print(f"  Error: gemini-image process was killed by signal 9 (SIGKILL / Out-of-Memory).", file=sys.stderr)
                        else:
                            print(f"  Error from gemini-image (exit code {res.returncode}): {res.stderr.strip()}", file=sys.stderr)
                    else:
                        if not target_file.exists():
                            cand_0 = target_file.parent / f"{target_file.stem}_0{target_file.suffix}"
                            if cand_0.exists():
                                shutil.copy2(cand_0, target_file)
                        if target_file.exists():
                            image_generated = True
                        else:
                            print(f"  Warning: gemini-image exited with 0 but {target_file} was not found.", file=sys.stderr)
                except subprocess.TimeoutExpired:
                    print(f"  Error: gemini-image timed out after 600 seconds.", file=sys.stderr)
                except Exception as e:
                    print(f"  Error invoking gemini-image: {e}", file=sys.stderr)

            # Fallback: Direct Google GenAI call if script is missing
            if not image_generated and client:
                try:
                    print(f"  Falling back to direct Google GenAI client for {t_id}...")
                    if "imagen" in tag_image_model.lower():
                        cfg = {"output_mime_type": "image/png"}
                        if tag_aspect_ratio:
                            cfg["aspect_ratio"] = tag_aspect_ratio
                        res = client.models.generate_images(model=tag_image_model, prompt=composed_model_prompt, config=cfg)
                        if hasattr(res, "generated_images") and res.generated_images:
                            img_bytes = res.generated_images[0].image.image_bytes
                            with open(target_file, "wb") as f:
                                f.write(img_bytes)
                            image_generated = True
                    else:
                        input_payload = []
                        for rp in all_ref_image_paths:
                            if Path(rp).exists():
                                try:
                                    with open(rp, "rb") as rpf:
                                        rb64 = base64.b64encode(rpf.read()).decode("utf-8")
                                    mime_t, _ = mimetypes.guess_type(str(rp))
                                    input_payload.append({
                                        "type": "image",
                                        "data": rb64,
                                        "mime_type": mime_t or "image/png"
                                    })
                                except Exception:
                                    pass
                        input_payload.append({"type": "text", "text": composed_model_prompt})

                        resp_format = {"type": "image", "mime_type": "image/jpeg"}
                        if tag_aspect_ratio:
                            resp_format["aspect_ratio"] = tag_aspect_ratio
                        if tag_image_size:
                            resp_format["image_size"] = tag_image_size

                        interaction = client.interactions.create(
                            model=tag_image_model,
                            input=input_payload if len(input_payload) > 1 else composed_model_prompt,
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
            print(f"[storybook generate] Requesting video generation for {t_id} with {tag_video_model}...")
            print(f"  Prompt: '{effective_prompt}'")
            if active_style_image:
                print(f"  Style Image: '{active_style_image}'")
            try:
                # Video generation via Google GenAI Veo
                video_kwargs = {
                    "model": tag_video_model,
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
        self.old_gemini_key = os.environ.pop("GEMINI_API_KEY", None)
        self.old_google_key = os.environ.pop("GOOGLE_API_KEY", None)
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

    def tearDown(self):
        if self.old_gemini_key:
            os.environ["GEMINI_API_KEY"] = self.old_gemini_key
        if self.old_google_key:
            os.environ["GOOGLE_API_KEY"] = self.old_google_key

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
    p_m_prompt.add_argument("--style-prompt", dest="style_prompt", help="Visual art style prompt override.")
    p_m_prompt.add_argument("--api-key", help="Gemini API key.")

    # 2.3 media generate
    p_m_gen = media_sub.add_parser("generate", help="Generate AI images/videos for media tags.")
    add_common_media_args(p_m_gen)
    p_m_gen.add_argument("-t", "--type", default="all", choices=["image", "video", "all"], help="Media type to generate (default: all).")
    p_m_gen.add_argument("--id", "--tag", dest="tag_id", help="Target specific tag ID (e.g. img_001).")
    p_m_gen.add_argument("--section", "--chapter", dest="section", help="Target specific section or chapter title (e.g. 序章).")
    p_m_gen.add_argument("--force", action="store_true", help="Force regeneration of existing media assets.")
    p_m_gen.add_argument("--output-dir", default="outputs", help="Directory to save media assets (default: outputs).")
    p_m_gen.add_argument("-m", "--model", default="gemini-3.1-flash-image", help="Image model (default: gemini-3.1-flash-image).")
    p_m_gen.add_argument("--video-model", default="veo-2.0-generate-001", help="Video model (default: veo-2.0-generate-001).")
    p_m_gen.add_argument("-r", "--ratio", default="16:9", help="Aspect ratio (default: 16:9).")
    p_m_gen.add_argument("-s", "--size", default="1K", help="Image resolution size (default: 1K).")
    p_m_gen.add_argument("--style-image", dest="style_image", help="Path to reference image file for visual style.")
    p_m_gen.add_argument("--style-prompt", dest="style_prompt", help="Text prompt specifying the visual art style.")
    p_m_gen.add_argument("--char-refs", "--char-ref", dest="char_refs", action="append", help="Character reference mapping: Name:image_path, ...")
    p_m_gen.add_argument("--style-ref", "--style-refs", dest="style_refs", action="append", help="Style reference image(s): image1.png, image2.png, ...")
    p_m_gen.add_argument("--extra-prompt", dest="extra_prompt", help="Extra prompt directives to append to the generation prompt.")
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
    # 7. 'view' command
    # --------------------------------------------------------------------------
    p_view = subparsers.add_parser(
        "view",
        help="Launch the MD3 Storybook Craft web viewer to review workspaces, characters, and media."
    )
    p_view.add_argument("--port", type=int, default=5173, help="Port to listen on (default: 5173).")
    p_view.add_argument("--no-open", action="store_true", help="Do not automatically open browser.")
    p_view.add_argument("--output-dir", default="outputs", help="Base output directory to inspect (default: outputs).")

    # --------------------------------------------------------------------------
    # 8. 'test' command
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
    # Dispatch: view
    # --------------------------------------------------------------------------
    if args.command == "view":
        viewer_server_path = Path(__file__).resolve().parent / "viewer" / "server.py"
        if not viewer_server_path.exists():
            print(f"[storybook view] Error: Viewer server not found at {viewer_server_path}", file=sys.stderr)
            sys.exit(1)
        import importlib.util
        spec = importlib.util.spec_from_file_location("storybook_viewer_server", str(viewer_server_path))
        viewer_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(viewer_mod)
        viewer_mod.run_server(
            port=getattr(args, "port", 5173),
            open_browser=not getattr(args, "no_open", False),
            outputs_dir=getattr(args, "output_dir", "outputs")
        )
        sys.exit(0)

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
            workspace = None
            if args.input_file:
                p = Path(args.input_file)
                if (p.parent / "char-ref").exists() or (p.parent / "style-ref").exists():
                    workspace = StoryWorkspace(p.parent)
                else:
                    workspace = StoryWorkspace(args.input_file)

            chars = None
            s_prompt = getattr(args, "style_prompt", None)
            if workspace:
                if (workspace.char_ref_dir / "characters.json").exists():
                    try:
                        with open(workspace.char_ref_dir / "characters.json", "r", encoding="utf-8") as cf:
                            chars = json.load(cf).get("characters", [])
                    except Exception:
                        pass
                if not s_prompt and (workspace.style_ref_dir / "style.json").exists():
                    try:
                        with open(workspace.style_ref_dir / "style.json", "r", encoding="utf-8") as sf:
                            s_prompt = json.load(sf).get("style_prompt")
                    except Exception:
                        pass

            res = update_media_tag_prompts(
                markdown_text=input_text,
                force=args.force,
                use_ai=args.ai,
                api_key=args.api_key,
                workspace=workspace,
                characters=chars,
                style_prompt=s_prompt
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
                section=getattr(args, "section", None),
                image_model=args.model,
                video_model=args.video_model,
                aspect_ratio=args.ratio,
                image_size=args.size,
                style_image=getattr(args, "style_image", None),
                style_prompt=getattr(args, "style_prompt", None),
                api_key=args.api_key,
                dry_run=args.dry_run,
                workspace=workspace,
                extra_prompt=getattr(args, "extra_prompt", None),
                char_refs=char_refs_arg
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
            workspace=workspace,
            char_refs=char_refs_arg
        )

        target_out = args.output or (args.input_file if args.in_place else str(workspace.output_md))
        if not getattr(args, "dry_run", False) or args.output or args.in_place:
            write_output_content(final_text, target_out, args.input_file, args.in_place)
        sys.exit(0)


if __name__ == "__main__":
    main()
