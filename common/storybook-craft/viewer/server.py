#!/usr/bin/env python3
"""
Storybook Craft Viewer Server
Serves the MD3 Vue.js SPA and REST API for inspecting workspaces,
characters, art style profiles, scene media, and story markdown.
"""

import os
import sys
import json
import re
import mimetypes
import webbrowser
import base64
import subprocess
import shutil
import threading
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote

VIEWER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = VIEWER_DIR.parent
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DEFAULT_EXAMPLES_DIR = PROJECT_ROOT / "examples"
DIST_DIR = VIEWER_DIR / "dist"

# Automatically load persisted GEMINI_API_KEY from outputs/.gemini_api_key if available
_KEY_FILE = DEFAULT_OUTPUTS_DIR / ".gemini_api_key"
if not os.environ.get("GEMINI_API_KEY") and _KEY_FILE.exists():
    try:
        with open(_KEY_FILE, "r", encoding="utf-8") as _kf:
            _saved_key = _kf.read().strip()
            if _saved_key:
                os.environ["GEMINI_API_KEY"] = _saved_key
    except Exception:
        pass

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from storybook import (
        compose_reference_prompt,
        match_characters_for_tag,
        find_python_for_gemini,
        build_prompt,
        update_media_tag_prompts,
        extract_media_tags,
        extract_tag_context,
        extract_characters_from_story,
        StoryWorkspace
    )
except Exception:
    compose_reference_prompt = None
    match_characters_for_tag = None
    find_python_for_gemini = None
    build_prompt = None
    update_media_tag_prompts = None
    extract_media_tags = None
    extract_tag_context = None
    extract_characters_from_story = None
    StoryWorkspace = None



DEFAULT_SETTINGS = {
    "global": {
        "image": {
            "ratio": "16:9",
            "size": "1K",
            "model": "gemini-3.1-flash-image"
        },
        "video": {
            "ratio": "16:9",
            "model": "veo-2.0-generate-001",
            "duration": "5s"
        }
    },
    "sections": {},
    "scenes": {}
}


class TaskManager:
    def __init__(self, default_outputs_dir: Path):
        self.default_outputs_dir = default_outputs_dir
        self.lock = threading.RLock()
        self._running_procs = {}  # task_id -> subprocess.Popen

    def _get_history_file(self, outputs_dir: Path, stem: str) -> Path:
        return outputs_dir / stem / ".generation_tasks.json"

    def load_tasks(self, outputs_dir: Path, stem: str) -> list:
        history_file = self._get_history_file(outputs_dir, stem)
        if not history_file.exists():
            return []
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)
                if isinstance(tasks, list):
                    modified = False
                    for t in tasks:
                        if t.get("status") == "running" and t.get("id") not in self._running_procs:
                            t["status"] = "failed"
                            t["error"] = "Task interrupted (server was stopped or restarted)"
                            if not t.get("finished_at"):
                                t["finished_at"] = datetime.now().isoformat()
                            modified = True
                    if modified:
                        self.save_tasks(outputs_dir, stem, tasks)
                    return tasks
                return []
        except Exception as e:
            print(f"[TaskManager] Error loading tasks for {stem}: {e}")
            return []

    def save_tasks(self, outputs_dir: Path, stem: str, tasks: list):
        history_file = self._get_history_file(outputs_dir, stem)
        try:
            history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(tasks[:200], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[TaskManager] Error saving tasks for {stem}: {e}")

    def add_task(self, outputs_dir: Path, stem: str, task: dict):
        with self.lock:
            tasks = self.load_tasks(outputs_dir, stem)
            tasks.insert(0, task)
            self.save_tasks(outputs_dir, stem, tasks)

    def update_task(self, outputs_dir: Path, stem: str, task_id: str, updates: dict):
        with self.lock:
            tasks = self.load_tasks(outputs_dir, stem)
            for t in tasks:
                if t.get("id") == task_id:
                    t.update(updates)
                    break
            self.save_tasks(outputs_dir, stem, tasks)

    def clear_tasks(self, outputs_dir: Path, stem: str) -> list:
        with self.lock:
            tasks = self.load_tasks(outputs_dir, stem)
            kept = [t for t in tasks if t.get("status") == "running"]
            self.save_tasks(outputs_dir, stem, kept)
            return kept

    def cancel_task(self, outputs_dir: Path, stem: str, task_id: str) -> bool:
        with self.lock:
            proc = self._running_procs.get(task_id)
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    self.update_task(outputs_dir, stem, task_id, {
                        "status": "failed",
                        "error": "Cancelled by user",
                        "finished_at": datetime.now().isoformat()
                    })
                    return True
                except Exception as e:
                    print(f"[TaskManager] Error cancelling task {task_id}: {e}")
            else:
                self.update_task(outputs_dir, stem, task_id, {
                    "status": "failed",
                    "error": "Cancelled by user",
                    "finished_at": datetime.now().isoformat()
                })
                return True
        return False


task_manager = TaskManager(DEFAULT_OUTPUTS_DIR)


class StorybookViewerHandler(SimpleHTTPRequestHandler):
    outputs_dir = DEFAULT_OUTPUTS_DIR
    examples_dir = DEFAULT_EXAMPLES_DIR
    dist_dir = DIST_DIR
    task_manager = task_manager

    def end_headers(self):
        # Enable CORS for local dev servers
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_HEAD(self):
        self.handle_request(is_head=True)

    def do_GET(self):
        self.handle_request(is_head=False)

    def do_POST(self):
        parsed = urlparse(self.path)
        pathname = unquote(parsed.path)

        if pathname == "/api/settings/api-key":
            self.handle_api_save_api_key()
            return

        settings_marker = "/settings"
        if pathname.startswith("/api/workspace/") and pathname.endswith(settings_marker):
            stem = pathname[len("/api/workspace/"):-len(settings_marker)].strip("/")
            self.handle_api_save_settings(stem)
            return

        upload_marker = "/upload-ref"
        if upload_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(upload_marker)]
            self.handle_api_upload_ref(stem)
            return

        delete_marker = "/delete-ref"
        if delete_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(delete_marker)]
            self.handle_api_delete_ref(stem)
            return

        select_ref_marker = "/select-ref"
        if select_ref_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(select_ref_marker)]
            self.handle_api_select_ref(stem)
            return

        extract_chars_marker = "/extract-characters"
        if extract_chars_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(extract_chars_marker)]
            self.handle_api_extract_characters(stem)
            return

        generate_marker = "/generate"
        if generate_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(generate_marker)]
            self.handle_api_generate(stem)
            return

        build_prompt_marker = "/build-prompt"
        if build_prompt_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(build_prompt_marker)]
            self.handle_api_build_prompt(stem)
            return

        insert_tag_marker = "/insert-tag"
        if insert_tag_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(insert_tag_marker)]
            self.handle_api_insert_tag(stem)
            return

        update_prompt_marker = "/update-tag-prompt"
        if update_prompt_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(update_prompt_marker)]
            self.handle_api_update_tag_prompt(stem)
            return

        enrich_prompts_marker = "/enrich-prompts"
        if enrich_prompts_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(enrich_prompts_marker)]
            self.handle_api_enrich_prompts(stem)
            return

        tasks_clear_marker = "/tasks/clear"
        if tasks_clear_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(tasks_clear_marker)]
            self.handle_api_clear_tasks(stem)
            return

        tasks_retry_marker = "/tasks/retry"
        if tasks_retry_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(tasks_retry_marker)]
            self.handle_api_retry_task(stem)
            return

        tasks_cancel_marker = "/tasks/cancel"
        if tasks_cancel_marker in pathname and pathname.startswith("/api/workspace/"):
            sub = pathname[len("/api/workspace/"):]
            stem = sub[:sub.index(tasks_cancel_marker)]
            self.handle_api_cancel_task(stem)
            return

        self.send_json_response({"error": "POST endpoint not found"}, status=404)


    def handle_request(self, is_head=False):
        parsed = urlparse(self.path)
        pathname = unquote(parsed.path)

        # 0. API: /api/settings/api-key
        if pathname == "/api/settings/api-key":
            self.handle_api_get_api_key(is_head=is_head)
            return

        # 1. API: /api/workspaces
        if pathname == "/api/workspaces":
            self.handle_api_workspaces(is_head=is_head)
            return

        # 1.5 API: /api/workspace/<stem>/settings
        if pathname.startswith("/api/workspace/") and pathname.endswith("/settings"):
            stem = pathname[len("/api/workspace/"):-len("/settings")].strip("/")
            self.handle_api_get_settings(stem, is_head=is_head)
            return

        # 1.6 API: /api/workspace/<stem>/tasks
        if pathname.startswith("/api/workspace/") and pathname.endswith("/tasks"):
            stem = pathname[len("/api/workspace/"):-len("/tasks")].strip("/")
            self.handle_api_get_tasks(stem, is_head=is_head)
            return

        # 2. API: /api/workspace/<stem>
        if pathname.startswith("/api/workspace/"):
            stem = pathname[len("/api/workspace/"):]
            self.handle_api_workspace_detail(stem, is_head=is_head)
            return

        # 3. API: /api/asset/<path>
        if pathname.startswith("/api/asset/"):
            asset_path = pathname[len("/api/asset/"):]
            self.handle_api_asset(asset_path, is_head=is_head)
            return

        # 4. SPA Static Files (from dist/)
        self.handle_spa_static(pathname, is_head=is_head)

    def send_json_response(self, data, status=200, is_head=False):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not is_head:
            self.wfile.write(body)

    def load_workspace_settings(self, stem: str) -> dict:
        ws_dir = self.outputs_dir / stem
        settings_file = ws_dir / "settings.json"
        res = json.loads(json.dumps(DEFAULT_SETTINGS))
        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    if "global" in loaded and isinstance(loaded["global"], dict):
                        if "image" in loaded["global"] and isinstance(loaded["global"]["image"], dict):
                            res["global"]["image"].update(loaded["global"]["image"])
                        if "video" in loaded["global"] and isinstance(loaded["global"]["video"], dict):
                            res["global"]["video"].update(loaded["global"]["video"])
                    if "sections" in loaded and isinstance(loaded["sections"], dict):
                        res["sections"] = loaded["sections"]
                    if "scenes" in loaded and isinstance(loaded["scenes"], dict):
                        res["scenes"] = loaded["scenes"]
            except Exception as e:
                print(f"[viewer server] Error reading settings from {settings_file}: {e}")
        return res

    def save_workspace_settings(self, stem: str, data: dict) -> dict:
        ws_dir = self.outputs_dir / stem
        ws_dir.mkdir(parents=True, exist_ok=True)
        settings_file = ws_dir / "settings.json"

        current = self.load_workspace_settings(stem)
        if isinstance(data, dict):
            if "global" in data and isinstance(data["global"], dict):
                if "image" in data["global"] and isinstance(data["global"]["image"], dict):
                    current["global"]["image"].update(data["global"]["image"])
                if "video" in data["global"] and isinstance(data["global"]["video"], dict):
                    current["global"]["video"].update(data["global"]["video"])
            if "sections" in data and isinstance(data["sections"], dict):
                current["sections"] = data["sections"]
            if "scenes" in data and isinstance(data["scenes"], dict):
                current["scenes"] = data["scenes"]

        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)

        return current

    def handle_api_get_settings(self, stem: str, is_head: bool = False):
        settings = self.load_workspace_settings(stem)
        self.send_json_response(settings, is_head=is_head)

    def handle_api_save_settings(self, stem: str):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
            saved = self.save_workspace_settings(stem, payload)
            self.send_json_response({"success": True, "settings": saved})
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_get_api_key(self, is_head=False):
        key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
        masked = f"{key[:6]}...{key[-4:]}" if len(key) >= 12 else ("******" if key else "")
        self.send_json_response({
            "has_key": bool(key),
            "masked_key": masked
        }, is_head=is_head)

    def handle_api_save_api_key(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
            key = (payload.get("api_key") or "").strip()
            if key:
                os.environ["GEMINI_API_KEY"] = key
                self.outputs_dir.mkdir(parents=True, exist_ok=True)
                key_file = self.outputs_dir / ".gemini_api_key"
                with open(key_file, "w", encoding="utf-8") as f:
                    f.write(key)
            else:
                os.environ.pop("GEMINI_API_KEY", None)
                key_file = self.outputs_dir / ".gemini_api_key"
                if key_file.exists():
                    key_file.unlink()
            masked = f"{key[:6]}...{key[-4:]}" if len(key) >= 12 else ("******" if key else "")
            self.send_json_response({"success": True, "has_key": bool(key), "masked_key": masked})
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_workspaces(self, is_head=False):
        if not self.outputs_dir.exists():
            self.send_json_response({"workspaces": []}, is_head=is_head)
            return

        workspaces = []
        try:
            for entry in sorted(self.outputs_dir.iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    ws_dir = entry
                    char_dir = ws_dir / "char-ref"
                    style_dir = ws_dir / "style-ref"
                    images_dir = ws_dir / "images"
                    videos_dir = ws_dir / "videos"

                    char_count = 0
                    char_image_count = 0
                    if char_dir.exists():
                        for cd in char_dir.iterdir():
                            if cd.is_dir():
                                char_count += 1
                                char_image_count += len([
                                    f for f in cd.iterdir()
                                    if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                                ])

                    style_count = 0
                    if style_dir.exists():
                        style_count = len([
                            f for f in style_dir.iterdir()
                            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                        ])

                    gen_images_count = 0
                    if images_dir.exists():
                        gen_images_count = len([
                            f for f in images_dir.iterdir()
                            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                        ])

                    gen_videos_count = 0
                    if videos_dir.exists():
                        gen_videos_count = len([
                            f for f in videos_dir.iterdir()
                            if f.is_file() and f.suffix.lower() in {".mp4", ".webm"}
                        ])

                    output_md = ws_dir / f"{entry.name}-output.md"

                    workspaces.append({
                        "stem": entry.name,
                        "directory": str(ws_dir),
                        "charactersCount": char_count,
                        "characterImagesCount": char_image_count,
                        "styleImagesCount": style_count,
                        "generatedImagesCount": gen_images_count,
                        "generatedVideosCount": gen_videos_count,
                        "hasOutputMd": output_md.exists()
                    })

            self.send_json_response({"workspaces": workspaces})
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_workspace_detail(self, stem, is_head=False):
        ws_dir = self.outputs_dir / stem
        if not ws_dir.exists() or not ws_dir.is_dir():
            self.send_json_response({"error": f"Workspace '{stem}' not found"}, status=404, is_head=is_head)
            return

        try:
            # Characters
            characters = []
            char_dir = ws_dir / "char-ref"
            chars_json_path = char_dir / "characters.json"
            if chars_json_path.exists():
                try:
                    with open(chars_json_path, "r", encoding="utf-8") as f:
                        chars_data = json.load(f)
                        characters = chars_data.get("characters", [])
                except Exception:
                    pass

            if char_dir.exists():
                for cd in sorted(char_dir.iterdir()):
                    if cd.is_dir():
                        existing = next((c for c in characters if c.get("name") == cd.name), None)
                        imgs = [
                            f.name for f in sorted(cd.iterdir())
                            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                        ]
                        c_json_path = cd / "character.json"
                        c_json = {}
                        if c_json_path.exists():
                            try:
                                with open(c_json_path, "r", encoding="utf-8") as cf:
                                    c_json = json.load(cf)
                            except Exception:
                                pass

                        preferred_imgs = c_json.get("images") or (existing.get("images") if existing else None) or imgs
                        ordered = [x for x in preferred_imgs if (cd / x).is_file()]
                        for img_f in imgs:
                            if img_f not in ordered:
                                ordered.append(img_f)

                        if not existing:
                            characters.append({
                                "name": cd.name,
                                "role": c_json.get("role", "Character"),
                                "visual_dna": c_json.get("visual_dna", ""),
                                "portrait_prompt": c_json.get("portrait_prompt", ""),
                                "images": ordered,
                                "source": c_json.get("source", "collected")
                            })
                        else:
                            existing["images"] = ordered
                            if not existing.get("visual_dna") and c_json.get("visual_dna"):
                                existing["visual_dna"] = c_json.get("visual_dna")
                            if not existing.get("portrait_prompt") and c_json.get("portrait_prompt"):
                                existing["portrait_prompt"] = c_json.get("portrait_prompt")

            # Style
            style = {
                "style_name": "Default Style",
                "style_prompt": "",
                "reference_prompt": "",
                "images": []
            }
            style_dir = ws_dir / "style-ref"
            style_json_path = style_dir / "style.json"
            if style_json_path.exists():
                try:
                    with open(style_json_path, "r", encoding="utf-8") as sf:
                        style = json.load(sf)
                except Exception:
                    pass

            if style_dir.exists():
                style_imgs = [
                    f.name for f in sorted(style_dir.iterdir())
                    if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                ]
                if style_imgs:
                    current_s_imgs = style.get("images", [])
                    filtered = [x for x in current_s_imgs if (style_dir / x).exists()]
                    for img_f in style_imgs:
                        if img_f not in filtered:
                            filtered.append(img_f)
                    style["images"] = filtered

            # Generated Media
            generated_images = []
            images_dir = ws_dir / "images"
            if images_dir.exists():
                for f in sorted(images_dir.iterdir()):
                    if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                        mtime = int(f.stat().st_mtime)
                        generated_images.append({
                            "name": f.name,
                            "id": f.stem,
                            "sizeBytes": f.stat().st_size,
                            "mtime": mtime,
                            "path": f"images/{f.name}",
                            "assetUrl": f"/api/asset/{stem}/images/{f.name}?v={mtime}"
                        })

            generated_videos = []
            videos_dir = ws_dir / "videos"
            if videos_dir.exists():
                for f in sorted(videos_dir.iterdir()):
                    if f.is_file() and f.suffix.lower() in {".mp4", ".webm"}:
                        mtime = int(f.stat().st_mtime)
                        generated_videos.append({
                            "name": f.name,
                            "id": f.stem,
                            "sizeBytes": f.stat().st_size,
                            "mtime": mtime,
                            "path": f"videos/{f.name}",
                            "assetUrl": f"/api/asset/{stem}/videos/{f.name}?v={mtime}"
                        })

            # Markdown Content
            markdown_content = ""
            markdown_type = "none"
            clean_stem = re.sub(r'(_zh|_en)$', '', stem)
            candidates = [
                (ws_dir / f"{stem}-output.md", "output"),
                (ws_dir / f"{stem}.md", "workspace"),
                (self.examples_dir / f"{stem}_crafted.md", "example"),
                (self.examples_dir / f"{clean_stem}_crafted.md", "example"),
                (self.examples_dir / f"{stem}.md", "example"),
                (PROJECT_ROOT / "tests" / f"{stem}.md", "test"),
            ]
            for candidate, mtype in candidates:
                if candidate.exists():
                    try:
                        markdown_content = candidate.read_text(encoding="utf-8")
                        markdown_type = mtype
                        break
                    except Exception:
                        pass

            if not markdown_content and ws_dir.exists():
                md_files = list(ws_dir.glob("*.md"))
                if md_files:
                    try:
                        markdown_content = md_files[0].read_text(encoding="utf-8")
                        markdown_type = "workspace"
                    except Exception:
                        pass

            # Extract tags with comprehensive parsing
            raw_tags = []
            json_regex = re.compile(r'<!--\s*storybook-media:\s*(\{.*?\})\s*-->', re.DOTALL)
            for m in json_regex.finditer(markdown_content):
                try:
                    t = json.loads(m.group(1))
                    t["_pos"] = m.start()
                    raw_tags.append(t)
                except Exception:
                    pass

            kv_regex = re.compile(r'<!--\s*storybook-media\s+([^>]*?)\s*-->', re.DOTALL)
            for m in kv_regex.finditer(markdown_content):
                content = m.group(1).strip()
                if content.startswith("{") or content.startswith(":"):
                    continue
                kv_dict = {"_pos": m.start()}
                for am in re.finditer(r'(\w+)=["\'](.*?)["\']', content):
                    kv_dict[am.group(1)] = am.group(2)
                if kv_dict.get("id") or kv_dict.get("type"):
                    raw_tags.append(kv_dict)

            raw_tags.sort(key=lambda x: x.get("_pos", 0))

            all_generated = generated_images + generated_videos
            ws_settings = self.load_workspace_settings(stem)
            scenes_cfg = ws_settings.get("scenes", {})
            sections_cfg = ws_settings.get("sections", {})

            tags = []
            for rt in raw_tags:
                tag_id = rt.get("id", "")
                tag_type = rt.get("type", "image").lower()
                matched = next((
                    a for a in all_generated
                    if a["id"] == tag_id or
                    a["name"].startswith(tag_id + ".") or
                    tag_id in a["name"] or
                    (rt.get("asset") and a["name"] == Path(rt["asset"]).name)
                ), None)

                rt_clean = {k: v for k, v in rt.items() if not k.startswith("_")}
                rt_clean["type"] = tag_type
                tag_section = rt_clean.get("section") or rt_clean.get("title") or "Story Scene"
                rt_clean["section"] = tag_section
                rt_clean["prompt"] = rt_clean.get("prompt", "")
                rt_clean["context_hint"] = rt_clean.get("context_hint", "")
                rt_clean["isGenerated"] = matched is not None
                rt_clean["matchedAsset"] = matched

                scene_cfg = scenes_cfg.get(tag_id, {})
                section_cfg = sections_cfg.get(tag_section, {})

                # Match character references
                matched_chars = []
                if match_characters_for_tag:
                    matched_chars = match_characters_for_tag(rt_clean, characters)
                else:
                    for ch in characters:
                        cname = ch.get("name", "")
                        if cname and (cname in rt_clean["prompt"] or cname in rt_clean["context_hint"]):
                            matched_chars.append(ch)

                char_refs_data = []
                for ch in matched_chars:
                    cname = ch.get("name", "")
                    imgs = ch.get("images", [])
                    c_img = imgs[0] if imgs else None
                    char_override_scope = None

                    # 1. Check tag-level override first!
                    tag_char_refs = scene_cfg.get("character_refs", {})
                    if cname in tag_char_refs:
                        override_val = tag_char_refs[cname]
                        if (ws_dir / "char-ref" / cname / override_val).is_file():
                            c_img = override_val
                            char_override_scope = "tag"

                    # 2. Check scene/section-level override!
                    if not char_override_scope and tag_section:
                        sec_char_refs = section_cfg.get("character_refs", {})
                        if cname in sec_char_refs:
                            sec_override_val = sec_char_refs[cname]
                            if (ws_dir / "char-ref" / cname / sec_override_val).is_file():
                                c_img = sec_override_val
                                char_override_scope = "scene"

                    char_refs_data.append({
                        "name": cname,
                        "category": ch.get("category", "hero"),
                        "role": ch.get("role", "Character"),
                        "visual_dna": ch.get("visual_dna", ""),
                        "image": c_img,
                        "assetUrl": f"/api/asset/{stem}/char-ref/{cname}/{c_img}" if c_img else None,
                        "is_scene_override": char_override_scope is not None,
                        "override_scope": char_override_scope,
                        "role_guide": f"Character Identity Reference: {cname} ({'Tag Override' if char_override_scope == 'tag' else ('Scene Override' if char_override_scope == 'scene' else 'Context Matched')})"
                    })

                # Style Reference (check tag override > section override > global)
                style_imgs = style.get("images", [])
                style_img = style_imgs[0] if style_imgs else None
                style_override_scope = None

                tag_style_ref = scene_cfg.get("style_ref")
                if tag_style_ref and (ws_dir / "style-ref" / tag_style_ref).is_file():
                    style_img = tag_style_ref
                    style_override_scope = "tag"
                elif tag_section:
                    sec_style_ref = section_cfg.get("style_ref")
                    if sec_style_ref and (ws_dir / "style-ref" / sec_style_ref).is_file():
                        style_img = sec_style_ref
                        style_override_scope = "scene"

                style_ref_data = {
                    "name": style_img,
                    "assetUrl": f"/api/asset/{stem}/style-ref/{style_img}" if style_img else None,
                    "style_name": style.get("style_name", "Art Style"),
                    "style_prompt": style.get("style_prompt", ""),
                    "is_scene_override": style_override_scope is not None,
                    "override_scope": style_override_scope,
                    "role": "Style Reference (Always Active)"
                } if style_img else None

                # Composed prompt with strict anti-modification template
                composed_prompt = ""
                extra_p = scene_cfg.get("extra_prompt")
                if compose_reference_prompt:
                    composed_prompt = compose_reference_prompt(
                        context_prompt=rt_clean["prompt"],
                        style_prompt=style.get("style_prompt", ""),
                        has_style_image=style_img is not None,
                        character_refs=char_refs_data,
                        tag_type=tag_type,
                        extra_prompt=extra_p
                    )
                else:
                    composed_prompt = rt_clean["prompt"]

                rt_clean["style_ref"] = style_ref_data
                rt_clean["character_refs"] = char_refs_data
                rt_clean["composed_prompt"] = composed_prompt
                rt_clean["cli_command"] = f"python3 storybook.py media generate outputs/{stem}/{stem}-output.md --id {tag_id}"

                tags.append(rt_clean)

            self.send_json_response({
                "stem": stem,
                "characters": characters,
                "style": style,
                "generatedImages": generated_images,
                "generatedVideos": generated_videos,
                "markdownContent": markdown_content,
                "markdownType": markdown_type,
                "tags": tags,
                "settings": self.load_workspace_settings(stem)
            }, is_head=is_head)
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500, is_head=is_head)

    def handle_api_asset(self, asset_path, is_head=False):
        target = (self.outputs_dir / asset_path).resolve()
        # Security check: must be inside outputs_dir
        if not str(target).startswith(str(self.outputs_dir.resolve())):
            self.send_response(403)
            self.end_headers()
            if not is_head:
                self.wfile.write(b"Forbidden")
            return

        if not target.exists() or not target.is_file():
            self.send_response(404)
            self.end_headers()
            if not is_head:
                self.wfile.write(b"Asset not found")
            return

        mime_type, _ = mimetypes.guess_type(str(target))
        if not mime_type:
            mime_type = "application/octet-stream"

        file_size = target.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()

        if not is_head:
            with open(target, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)

    def handle_api_upload_ref(self, stem):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8"))

            ref_type = payload.get("type", "character")  # "character" or "style"
            char_name = payload.get("character_name", "").strip()
            custom_filename = payload.get("filename", "").strip()
            image_data = payload.get("image_base64", "").strip()

            if not image_data:
                self.send_json_response({"error": "No image data provided"}, status=400)
                return

            if "," in image_data:
                _, base64_str = image_data.split(",", 1)
            else:
                base64_str = image_data

            img_bytes = base64.b64decode(base64_str)

            ws_dir = self.outputs_dir / stem
            if not ws_dir.exists():
                self.send_json_response({"error": f"Workspace '{stem}' not found"}, status=404)
                return

            if ref_type == "character":
                if not char_name:
                    self.send_json_response({"error": "character_name is required for character reference"}, status=400)
                    return
                char_dir = ws_dir / "char-ref" / char_name
                char_dir.mkdir(parents=True, exist_ok=True)
                filename = custom_filename or "ref_001.png"
                if not any(filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                    filename += ".png"
                out_file = char_dir / filename
                with open(out_file, "wb") as f:
                    f.write(img_bytes)

                # Update character.json
                c_json_file = char_dir / "character.json"
                c_data = {}
                if c_json_file.exists():
                    try:
                        with open(c_json_file, "r", encoding="utf-8") as f:
                            c_data = json.load(f)
                    except Exception:
                        pass
                imgs = c_data.get("images", [])
                if filename not in imgs:
                    imgs.insert(0, filename)
                else:
                    imgs.remove(filename)
                    imgs.insert(0, filename)
                c_data["images"] = imgs
                with open(c_json_file, "w", encoding="utf-8") as f:
                    json.dump(c_data, f, ensure_ascii=False, indent=2)

                # Update characters.json in char-ref if present
                all_chars_file = ws_dir / "char-ref" / "characters.json"
                if all_chars_file.exists():
                    try:
                        with open(all_chars_file, "r", encoding="utf-8") as f:
                            chars_meta = json.load(f)
                        for c in chars_meta.get("characters", []):
                            if c.get("name") == char_name:
                                if "images" not in c:
                                    c["images"] = []
                                if filename not in c["images"]:
                                    c["images"].insert(0, filename)
                                else:
                                    c["images"].remove(filename)
                                    c["images"].insert(0, filename)
                        with open(all_chars_file, "w", encoding="utf-8") as f:
                            json.dump(chars_meta, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

                asset_url = f"/api/asset/{stem}/char-ref/{char_name}/{filename}"
                self.send_json_response({
                    "success": True,
                    "message": f"Successfully updated reference photo for '{char_name}'",
                    "filename": filename,
                    "assetUrl": asset_url,
                    "type": "character",
                    "character_name": char_name
                })

            elif ref_type == "style":
                style_dir = ws_dir / "style-ref"
                style_dir.mkdir(parents=True, exist_ok=True)
                filename = custom_filename or "ref_001.png"
                if not any(filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                    filename += ".png"
                out_file = style_dir / filename
                with open(out_file, "wb") as f:
                    f.write(img_bytes)

                # Update style.json
                s_json_file = style_dir / "style.json"
                s_data = {}
                if s_json_file.exists():
                    try:
                        with open(s_json_file, "r", encoding="utf-8") as f:
                            s_data = json.load(f)
                    except Exception:
                        pass
                imgs = s_data.get("images", [])
                if filename not in imgs:
                    imgs.insert(0, filename)
                else:
                    imgs.remove(filename)
                    imgs.insert(0, filename)
                s_data["images"] = imgs
                with open(s_json_file, "w", encoding="utf-8") as f:
                    json.dump(s_data, f, ensure_ascii=False, indent=2)

                asset_url = f"/api/asset/{stem}/style-ref/{filename}"
                self.send_json_response({
                    "success": True,
                    "message": "Successfully updated style reference image",
                    "filename": filename,
                    "assetUrl": asset_url,
                    "type": "style"
                })
            else:
                self.send_json_response({"error": f"Unknown reference type '{ref_type}'"}, status=400)

        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_delete_ref(self, stem):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}

            ref_type = payload.get("type", "character")
            char_name = payload.get("character_name", "").strip()
            filename = payload.get("filename", "").strip()

            if not filename:
                self.send_json_response({"error": "filename is required"}, status=400)
                return

            # Sanitize filename
            filename = os.path.basename(filename)

            ws_dir = self.outputs_dir / stem
            if not ws_dir.exists():
                self.send_json_response({"error": f"Workspace '{stem}' not found"}, status=404)
                return

            if ref_type == "character":
                if not char_name:
                    self.send_json_response({"error": "character_name is required for character reference"}, status=400)
                    return

                deleted = False
                for char_base in ["char-ref", "characters"]:
                    target_file = ws_dir / char_base / char_name / filename
                    if target_file.exists():
                        try:
                            target_file.unlink()
                            deleted = True
                        except Exception:
                            pass

                    # Clean character.json
                    c_json = ws_dir / char_base / char_name / "character.json"
                    if c_json.exists():
                        try:
                            with open(c_json, "r", encoding="utf-8") as f:
                                c_data = json.load(f)
                            imgs = c_data.get("images", [])
                            if filename in imgs:
                                c_data["images"] = [x for x in imgs if x != filename]
                                with open(c_json, "w", encoding="utf-8") as f:
                                    json.dump(c_data, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass

                    # Clean characters.json
                    all_json = ws_dir / char_base / "characters.json"
                    if all_json.exists():
                        try:
                            with open(all_json, "r", encoding="utf-8") as f:
                                chars_meta = json.load(f)
                            for c in chars_meta.get("characters", []):
                                if c.get("name") == char_name:
                                    c["images"] = [x for x in c.get("images", []) if x != filename]
                            with open(all_json, "w", encoding="utf-8") as f:
                                json.dump(chars_meta, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass

                self.send_json_response({
                    "success": True,
                    "message": f"Successfully deleted reference photo '{filename}' for '{char_name}'",
                    "filename": filename,
                    "type": "character",
                    "character_name": char_name
                })

            elif ref_type == "style":
                for style_base in ["style-ref", "style"]:
                    target_file = ws_dir / style_base / filename
                    if target_file.exists():
                        try:
                            target_file.unlink()
                        except Exception:
                            pass

                    s_json = ws_dir / style_base / "style.json"
                    if s_json.exists():
                        try:
                            with open(s_json, "r", encoding="utf-8") as f:
                                s_data = json.load(f)
                            imgs = s_data.get("images", [])
                            if filename in imgs:
                                s_data["images"] = [x for x in imgs if x != filename]
                                with open(s_json, "w", encoding="utf-8") as f:
                                    json.dump(s_data, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass

                self.send_json_response({
                    "success": True,
                    "message": f"Successfully deleted style reference '{filename}'",
                    "filename": filename,
                    "type": "style"
                })

            elif ref_type == "asset":
                for sub in ["images", "videos"]:
                    target_file = ws_dir / sub / filename
                    if target_file.exists():
                        try:
                            target_file.unlink()
                        except Exception:
                            pass
                self.send_json_response({
                    "success": True,
                    "message": f"Successfully deleted asset '{filename}'",
                    "filename": filename,
                    "type": "asset"
                })

            else:
                self.send_json_response({"error": f"Unknown reference type '{ref_type}'"}, status=400)

        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_select_ref(self, stem):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}

            ref_type = payload.get("type", "style")  # "style" or "character"
            char_name = payload.get("character_name", "").strip()
            asset_path = payload.get("asset_path", "").strip()
            filename = (payload.get("filename") or payload.get("image_name") or "").strip()
            tag_id = payload.get("tag_id", "").strip()
            section = payload.get("section", "").strip()
            # 3 scopes: "tag" | "scene" | "global"
            scope = payload.get("scope")
            if not scope:
                scope = "tag" if tag_id else ("scene" if section else "global")
            action = payload.get("action", "select")

            ws_dir = self.outputs_dir / stem
            if not ws_dir.exists():
                self.send_json_response({"error": f"Workspace '{stem}' not found"}, status=404)
                return

            # Clean asset_path if it's a URL
            if "/api/asset/" in asset_path:
                parts = asset_path.split("/api/asset/")[1].split("?")[0].split("/")
                if len(parts) > 1:
                    asset_path = "/".join(parts[1:])

            # Handle reset action
            if action == "reset":
                current_settings = self.load_workspace_settings(stem)
                reset_done = False

                if scope == "tag" or (not scope and tag_id):
                    if tag_id and "scenes" in current_settings and tag_id in current_settings["scenes"]:
                        scene_entry = current_settings["scenes"][tag_id]
                        if ref_type == "character":
                            if "character_refs" in scene_entry and char_name in scene_entry["character_refs"]:
                                scene_entry["character_refs"].pop(char_name, None)
                                reset_done = True
                        elif ref_type == "style":
                            if "style_ref" in scene_entry:
                                scene_entry.pop("style_ref", None)
                                reset_done = True

                if not reset_done and (scope == "scene" or (not scope and section)):
                    if section and "sections" in current_settings and section in current_settings["sections"]:
                        sec_entry = current_settings["sections"][section]
                        if ref_type == "character":
                            if "character_refs" in sec_entry and char_name in sec_entry["character_refs"]:
                                sec_entry["character_refs"].pop(char_name, None)
                                reset_done = True
                        elif ref_type == "style":
                            if "style_ref" in sec_entry:
                                sec_entry.pop("style_ref", None)
                                reset_done = True

                self.save_workspace_settings(stem, current_settings)
                self.send_json_response({
                    "success": True,
                    "action": "reset",
                    "tag_id": tag_id,
                    "section": section,
                    "character_name": char_name,
                    "type": ref_type,
                    "message": f"Successfully reset reference override for {char_name or 'style'}"
                })
                return

            if ref_type == "style":
                style_dir = ws_dir / "style-ref"
                style_dir.mkdir(parents=True, exist_ok=True)
                final_filename = filename

                # 1. Check asset_path first
                src_file = None
                if asset_path:
                    cand = ws_dir / asset_path
                    if cand.exists() and cand.is_file():
                        src_file = cand
                        final_filename = final_filename or src_file.name

                if not src_file and final_filename and (style_dir / final_filename).is_file():
                    src_file = style_dir / final_filename

                if not src_file and final_filename and (ws_dir / "images" / final_filename).is_file():
                    src_file = ws_dir / "images" / final_filename

                if not src_file:
                    self.send_json_response({"error": f"Asset file '{asset_path or filename}' not found for style reference"}, status=404)
                    return

                dst_file = style_dir / final_filename
                if src_file.resolve() != dst_file.resolve():
                    shutil.copy2(src_file, dst_file)

                # Scope: Tag vs Scene vs Global
                if scope == "tag" and tag_id:
                    current_settings = self.load_workspace_settings(stem)
                    current_settings.setdefault("scenes", {}).setdefault(tag_id, {})["style_ref"] = final_filename
                    self.save_workspace_settings(stem, current_settings)
                    asset_url = f"/api/asset/{stem}/style-ref/{final_filename}"
                    self.send_json_response({
                        "success": True,
                        "message": f"Successfully set '{final_filename}' as style reference for tag '{tag_id}'",
                        "filename": final_filename,
                        "assetUrl": asset_url,
                        "type": "style",
                        "tag_id": tag_id,
                        "section": section,
                        "scope": "tag",
                        "override_scope": "tag",
                        "is_scene_override": True
                    })
                    return

                if scope == "scene" and section:
                    current_settings = self.load_workspace_settings(stem)
                    current_settings.setdefault("sections", {}).setdefault(section, {})["style_ref"] = final_filename
                    if tag_id and tag_id in current_settings.get("scenes", {}):
                        current_settings["scenes"][tag_id].pop("style_ref", None)
                    self.save_workspace_settings(stem, current_settings)
                    asset_url = f"/api/asset/{stem}/style-ref/{final_filename}"
                    self.send_json_response({
                        "success": True,
                        "message": f"Successfully set '{final_filename}' as style reference for scene '{section}'",
                        "filename": final_filename,
                        "assetUrl": asset_url,
                        "type": "style",
                        "tag_id": tag_id,
                        "section": section,
                        "scope": "scene",
                        "override_scope": "scene",
                        "is_scene_override": True
                    })
                    return

                # Global update to style.json
                s_json_file = style_dir / "style.json"
                s_data = {}
                if s_json_file.exists():
                    try:
                        with open(s_json_file, "r", encoding="utf-8") as f:
                            s_data = json.load(f)
                    except Exception:
                        pass
                imgs = s_data.get("images", [])
                if final_filename in imgs:
                    imgs.remove(final_filename)
                imgs.insert(0, final_filename)
                s_data["images"] = imgs

                with open(s_json_file, "w", encoding="utf-8") as f:
                    json.dump(s_data, f, ensure_ascii=False, indent=2)

                # If tag_id or section had overrides, clean them up so they follow the new global default
                current_settings = self.load_workspace_settings(stem)
                settings_dirty = False
                if tag_id and tag_id in current_settings.get("scenes", {}):
                    if "style_ref" in current_settings["scenes"][tag_id]:
                        current_settings["scenes"][tag_id].pop("style_ref", None)
                        settings_dirty = True
                if section and section in current_settings.get("sections", {}):
                    if "style_ref" in current_settings["sections"][section]:
                        current_settings["sections"][section].pop("style_ref", None)
                        settings_dirty = True
                if settings_dirty:
                    self.save_workspace_settings(stem, current_settings)

                asset_url = f"/api/asset/{stem}/style-ref/{final_filename}"
                self.send_json_response({
                    "success": True,
                    "message": f"Successfully selected '{final_filename}' as global style reference",
                    "filename": final_filename,
                    "assetUrl": asset_url,
                    "type": "style",
                    "scope": "global",
                    "override_scope": None,
                    "is_scene_override": False
                })

            elif ref_type == "character":
                if not char_name:
                    self.send_json_response({"error": "character_name is required for character reference"}, status=400)
                    return

                char_dir = ws_dir / "char-ref" / char_name
                char_dir.mkdir(parents=True, exist_ok=True)
                final_filename = filename

                # 1. Resolve source file. Check asset_path FIRST!
                src_file = None
                if asset_path:
                    cand = ws_dir / asset_path
                    if cand.exists() and cand.is_file():
                        # Protect against cross-character file copying collisions
                        if "char-ref" in str(cand) and cand.parent.name != char_name:
                            final_filename = f"{cand.parent.name}_{cand.name}"
                        else:
                            final_filename = final_filename or cand.name
                        src_file = cand

                if not src_file and final_filename and (char_dir / final_filename).is_file():
                    src_file = char_dir / final_filename

                if not src_file and final_filename and (ws_dir / "images" / final_filename).is_file():
                    src_file = ws_dir / "images" / final_filename

                if not src_file:
                    self.send_json_response({"error": f"Asset file '{asset_path or filename}' not found for character '{char_name}'"}, status=404)
                    return

                dst_file = char_dir / final_filename
                if src_file.resolve() != dst_file.resolve():
                    shutil.copy2(src_file, dst_file)

                # Scope 1: Only this tag
                if scope == "tag" and tag_id:
                    current_settings = self.load_workspace_settings(stem)
                    current_settings.setdefault("scenes", {}).setdefault(tag_id, {}).setdefault("character_refs", {})[char_name] = final_filename
                    self.save_workspace_settings(stem, current_settings)
                    asset_url = f"/api/asset/{stem}/char-ref/{char_name}/{final_filename}"
                    self.send_json_response({
                        "success": True,
                        "message": f"Successfully set '{final_filename}' as reference photo for '{char_name}' on tag '{tag_id}'",
                        "filename": final_filename,
                        "assetUrl": asset_url,
                        "type": "character",
                        "character_name": char_name,
                        "tag_id": tag_id,
                        "section": section,
                        "scope": "tag",
                        "override_scope": "tag",
                        "is_scene_override": True
                    })
                    return

                # Scope 2: This Scene (Section)
                if scope == "scene" and section:
                    current_settings = self.load_workspace_settings(stem)
                    current_settings.setdefault("sections", {}).setdefault(section, {}).setdefault("character_refs", {})[char_name] = final_filename
                    # Clean tag override for this character on this tag so it inherits the scene override
                    if tag_id and tag_id in current_settings.get("scenes", {}):
                        current_settings["scenes"][tag_id].get("character_refs", {}).pop(char_name, None)
                    self.save_workspace_settings(stem, current_settings)
                    asset_url = f"/api/asset/{stem}/char-ref/{char_name}/{final_filename}"
                    self.send_json_response({
                        "success": True,
                        "message": f"Successfully set '{final_filename}' as reference photo for '{char_name}' on scene '{section}'",
                        "filename": final_filename,
                        "assetUrl": asset_url,
                        "type": "character",
                        "character_name": char_name,
                        "tag_id": tag_id,
                        "section": section,
                        "scope": "scene",
                        "override_scope": "scene",
                        "is_scene_override": True
                    })
                    return

                # Scope 3: Global workspace default
                c_json_file = char_dir / "character.json"
                c_data = {}
                if c_json_file.exists():
                    try:
                        with open(c_json_file, "r", encoding="utf-8") as f:
                            c_data = json.load(f)
                    except Exception:
                        pass
                if not c_data:
                    c_data = {
                        "name": char_name,
                        "category": "hero",
                        "role": "Character",
                        "visual_dna": f"Character {char_name}",
                        "portrait_prompt": f"Portrait of {char_name}",
                        "source": "collected"
                    }
                imgs = c_data.get("images", [])
                if final_filename in imgs:
                    imgs.remove(final_filename)
                imgs.insert(0, final_filename)
                for f in sorted(char_dir.iterdir()):
                    if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                        if f.name not in imgs:
                            imgs.append(f.name)
                c_data["images"] = imgs
                with open(c_json_file, "w", encoding="utf-8") as f:
                    json.dump(c_data, f, ensure_ascii=False, indent=2)

                # Update characters.json, PRESERVING all other characters
                all_chars_file = ws_dir / "char-ref" / "characters.json"
                chars_meta = {"characters": []}
                if all_chars_file.exists():
                    try:
                        with open(all_chars_file, "r", encoding="utf-8") as f:
                            chars_meta = json.load(f)
                    except Exception:
                        chars_meta = {"characters": []}

                found_in_meta = False
                for c in chars_meta.get("characters", []):
                    if c.get("name") == char_name:
                        found_in_meta = True
                        c_imgs = c.get("images", [])
                        if final_filename in c_imgs:
                            c_imgs.remove(final_filename)
                        c_imgs.insert(0, final_filename)
                        for f_name in imgs:
                            if f_name not in c_imgs:
                                c_imgs.append(f_name)
                        c["images"] = c_imgs
                        if not c.get("visual_dna") and c_data.get("visual_dna"):
                            c["visual_dna"] = c_data.get("visual_dna")
                        if not c.get("portrait_prompt") and c_data.get("portrait_prompt"):
                            c["portrait_prompt"] = c_data.get("portrait_prompt")
                        if "category" in c_data:
                            c["category"] = c_data["category"]

                if not found_in_meta:
                    chars_meta.setdefault("characters", []).append(c_data)

                with open(all_chars_file, "w", encoding="utf-8") as f:
                    json.dump(chars_meta, f, ensure_ascii=False, indent=2)

                # Clear tag and scene override if any for this character so they follow global default
                current_settings = self.load_workspace_settings(stem)
                settings_dirty = False
                if tag_id and tag_id in current_settings.get("scenes", {}):
                    if "character_refs" in current_settings["scenes"][tag_id]:
                        if char_name in current_settings["scenes"][tag_id]["character_refs"]:
                            current_settings["scenes"][tag_id]["character_refs"].pop(char_name, None)
                            settings_dirty = True
                if section and section in current_settings.get("sections", {}):
                    if "character_refs" in current_settings["sections"][section]:
                        if char_name in current_settings["sections"][section]["character_refs"]:
                            current_settings["sections"][section]["character_refs"].pop(char_name, None)
                            settings_dirty = True
                if settings_dirty:
                    self.save_workspace_settings(stem, current_settings)

                asset_url = f"/api/asset/{stem}/char-ref/{char_name}/{final_filename}"
                self.send_json_response({
                    "success": True,
                    "message": f"Successfully selected '{final_filename}' as global reference photo for '{char_name}'",
                    "filename": final_filename,
                    "assetUrl": asset_url,
                    "type": "character",
                    "character_name": char_name,
                    "scope": "global",
                    "override_scope": None,
                    "is_scene_override": False
                })
            else:
                self.send_json_response({"error": f"Unknown reference type '{ref_type}'"}, status=400)

        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_extract_characters(self, stem: str):
        try:
            ws_dir = self.outputs_dir / stem
            if not ws_dir.exists():
                self.send_json_response({"error": f"Workspace '{stem}' not found"}, status=404)
                return

            md_files = [f for f in ws_dir.glob("*.md") if not f.name.startswith(".")]
            if not md_files:
                self.send_json_response({"error": f"No markdown file found in workspace '{stem}'"}, status=404)
                return

            output_md = ws_dir / f"{stem}-output.md"
            if not output_md.exists():
                output_md = md_files[0]

            with open(output_md, "r", encoding="utf-8") as f:
                md_text = f.read()

            api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
            if not extract_characters_from_story:
                self.send_json_response({"error": "Character extraction engine not available"}, status=500)
                return

            extracted = extract_characters_from_story(md_text, api_key=api_key)
            char_dir = ws_dir / "char-ref"
            char_dir.mkdir(parents=True, exist_ok=True)

            chars_json_file = char_dir / "characters.json"
            existing_chars = []
            if chars_json_file.exists():
                try:
                    with open(chars_json_file, "r", encoding="utf-8") as f:
                        existing_chars = json.load(f).get("characters", [])
                except Exception:
                    pass

            # Map existing chars by normalized name
            def normalize_cname(n: str) -> str:
                return re.sub(r'[\(（].*?[\)）]', '', n or "").strip(' "“\'')

            existing_by_norm = {}
            for c in existing_chars:
                if "name" in c:
                    norm = normalize_cname(c["name"])
                    if norm:
                        existing_by_norm[norm] = c

            result_chars = []
            processed_norms = set()

            for item in extracted:
                cname = normalize_cname(item.get("name", ""))
                if not cname or cname in processed_norms:
                    continue
                processed_norms.add(cname)

                cdir = char_dir / cname
                cdir.mkdir(parents=True, exist_ok=True)
                c_json_file = cdir / "character.json"

                c_info = {}
                if c_json_file.exists():
                    try:
                        with open(c_json_file, "r", encoding="utf-8") as f:
                            c_info = json.load(f)
                    except Exception:
                        pass
                if not c_info and cname in existing_by_norm:
                    c_info = existing_by_norm[cname]

                disk_imgs = []
                for f in sorted(cdir.iterdir()):
                    if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                        disk_imgs.append(f.name)

                merged_imgs = list(c_info.get("images", []))
                for di in disk_imgs:
                    if di not in merged_imgs:
                        merged_imgs.append(di)

                c_data = {
                    "name": cname,
                    "category": item.get("category", c_info.get("category", "hero")),
                    "role": item.get("role", c_info.get("role", "Character")),
                    "visual_dna": item.get("visual_dna", c_info.get("visual_dna", "")),
                    "portrait_prompt": item.get("portrait_prompt", c_info.get("portrait_prompt", "")),
                    "images": merged_imgs if merged_imgs else disk_imgs,
                    "source": c_info.get("source", "auto_extracted")
                }

                with open(c_json_file, "w", encoding="utf-8") as f:
                    json.dump(c_data, f, ensure_ascii=False, indent=2)

                result_chars.append(c_data)

            # Preserve any existing characters that were not in extracted list
            final_chars_list = list(result_chars)
            for norm, c in existing_by_norm.items():
                if norm not in processed_norms:
                    c["name"] = normalize_cname(c["name"])
                    final_chars_list.append(c)

            with open(chars_json_file, "w", encoding="utf-8") as f:
                json.dump({"characters": final_chars_list}, f, ensure_ascii=False, indent=2)

            self.send_json_response({
                "success": True,
                "message": f"Successfully extracted {len(result_chars)} character(s) and creature(s)",
                "extracted_count": len(result_chars),
                "characters": final_chars_list
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def start_generation_task(self, stem: str, payload: dict) -> dict:
        tag_id = payload.get("tag_id")
        section = payload.get("section")
        media_type = payload.get("type", "image")
        ratio = payload.get("ratio")
        size = payload.get("size")
        model = payload.get("model")

        ws_dir = self.outputs_dir / stem
        output_md = ws_dir / f"{stem}-output.md"
        if not output_md.exists():
            md_files = [f for f in ws_dir.glob("*.md") if not f.name.startswith(".")]
            if md_files:
                output_md = md_files[0]
            else:
                raise FileNotFoundError(f"No storybook markdown found in {ws_dir}")

        ws_settings = self.load_workspace_settings(stem)
        scene_override = ws_settings.get("scenes", {}).get(tag_id, {}) if tag_id else {}
        section_override = ws_settings.get("sections", {}).get(section, {}) if section else {}
        global_type_cfg = ws_settings.get("global", {}).get(media_type, {})

        effective_ratio = (
            ratio if ratio and ratio != "inherit"
            else scene_override.get("ratio")
            or section_override.get("ratio")
            or global_type_cfg.get("ratio")
            or "16:9"
        )

        effective_size = (
            size if size and size != "inherit"
            else scene_override.get("size")
            or section_override.get("size")
            or global_type_cfg.get("size")
            or "1K"
        )

        effective_model = (
            model if model and model != "inherit"
            else scene_override.get("model")
            or section_override.get("model")
            or global_type_cfg.get("model")
            or ("gemini-3.1-flash-image" if media_type == "image" else "veo-2.0-generate-001")
        )

        py_exe = find_python_for_gemini() if find_python_for_gemini else sys.executable
        storybook_script = PROJECT_ROOT / "storybook.py"
        cmd = [
            py_exe,
            str(storybook_script),
            "media", "generate",
            str(output_md),
            "--type", media_type,
            "--force",
        ]
        if tag_id:
            cmd.extend(["--id", tag_id])
        if section:
            cmd.extend(["--section", section])
        if effective_ratio:
            cmd.extend(["--ratio", str(effective_ratio)])
        if effective_size:
            cmd.extend(["--size", str(effective_size)])
        if effective_model:
            if media_type == "video":
                cmd.extend(["--video-model", str(effective_model)])
            else:
                cmd.extend(["--model", str(effective_model)])

        extra_prompt = (payload.get("extra_prompt") or scene_override.get("extra_prompt") or section_override.get("extra_prompt") or "").strip()
        if extra_prompt:
            cmd.extend(["--extra-prompt", extra_prompt])

        api_key = (payload.get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
            cmd.extend(["--api-key", api_key])

        # Resolve prompt text from markdown if available
        tag_prompt = ""
        try:
            with open(output_md, "r", encoding="utf-8") as f:
                md_text = f.read()
            if extract_media_tags:
                all_tags = extract_media_tags(md_text)
                for t in all_tags:
                    if t.get("id") == tag_id:
                        tag_prompt = t.get("prompt", "")
                        break
        except Exception:
            pass

        # Resolve reference images used for this generation task
        ref_images_used = {
            "style": None,
            "characters": []
        }

        # Style reference (tag override > section override > global)
        style_dir = ws_dir / "style-ref"
        style_img_file = None
        tag_style_ref = scene_override.get("style_ref")
        sec_style_ref = section_override.get("style_ref")
        if tag_style_ref and (style_dir / tag_style_ref).is_file():
            style_img_file = style_dir / tag_style_ref
        elif sec_style_ref and (style_dir / sec_style_ref).is_file():
            style_img_file = style_dir / sec_style_ref
        elif style_dir.exists():
            s_json_file = style_dir / "style.json"
            s_imgs = []
            if s_json_file.exists():
                try:
                    with open(s_json_file, "r", encoding="utf-8") as sf:
                        s_imgs = json.load(sf).get("images", [])
                except Exception:
                    pass
            for candidate_img in s_imgs:
                if (style_dir / candidate_img).is_file():
                    style_img_file = style_dir / candidate_img
                    break
            if not style_img_file:
                for f in sorted(style_dir.iterdir()):
                    if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                        style_img_file = f
                        break
        if style_img_file:
            ref_images_used["style"] = style_img_file.name
            try:
                rel_style = str(style_img_file.relative_to(PROJECT_ROOT))
            except Exception:
                rel_style = str(style_img_file)
            cmd.extend(["--style-image", rel_style])

        # Character references (matched by tag context/prompt)
        char_dir = ws_dir / "char-ref"
        all_chars = []
        chars_json = char_dir / "characters.json"
        if chars_json.exists():
            try:
                with open(chars_json, "r", encoding="utf-8") as cf:
                    all_chars = json.load(cf).get("characters", [])
            except Exception:
                pass

        # Fallback: scan character subdirectories in char_dir to never miss characters
        if char_dir.exists():
            for cd in sorted(char_dir.iterdir()):
                if cd.is_dir() and not any(c.get("name") == cd.name for c in all_chars):
                    c_json_path = cd / "character.json"
                    c_info = {}
                    if c_json_path.exists():
                        try:
                            with open(c_json_path, "r", encoding="utf-8") as cf:
                                c_info = json.load(cf)
                        except Exception:
                            pass
                    all_chars.append({
                        "name": cd.name,
                        "category": c_info.get("category", "hero"),
                        "role": c_info.get("role", "Character"),
                        "visual_dna": c_info.get("visual_dna", ""),
                        "portrait_prompt": c_info.get("portrait_prompt", ""),
                        "images": c_info.get("images", []),
                        "source": c_info.get("source", "collected")
                    })

        matching_tag = None
        if tag_prompt:
            matching_tag = {"id": tag_id, "prompt": tag_prompt, "type": media_type}
        elif tag_id:
            matching_tag = {"id": tag_id, "prompt": payload.get("prompt", ""), "type": media_type}

        matched_characters = []
        if matching_tag:
            if match_characters_for_tag:
                matched_characters = match_characters_for_tag(matching_tag, all_chars)
            else:
                for ch in all_chars:
                    cname = ch.get("name", "")
                    if cname and (cname in matching_tag.get("prompt", "") or cname in matching_tag.get("context_hint", "")):
                        matched_characters.append(ch)

        tag_char_refs = scene_override.get("character_refs", {})
        sec_char_refs = section_override.get("character_refs", {})
        for ch in matched_characters:
            cname = ch.get("name", "")
            cd = char_dir / cname
            c_img_file = None

            # 1. Check tag override first!
            tag_c_img = tag_char_refs.get(cname)
            if tag_c_img and (cd / tag_c_img).is_file():
                c_img_file = cd / tag_c_img
            # 2. Check section override second!
            elif sec_char_refs.get(cname) and (cd / sec_char_refs[cname]).is_file():
                c_img_file = cd / sec_char_refs[cname]
            else:
                c_json_path = cd / "character.json"
                preferred_c_imgs = []
                if c_json_path.exists():
                    try:
                        with open(c_json_path, "r", encoding="utf-8") as cjf:
                            preferred_c_imgs = json.load(cjf).get("images", [])
                    except Exception:
                        pass
                if not preferred_c_imgs:
                    preferred_c_imgs = ch.get("images", [])
                for c_cand in preferred_c_imgs:
                    if (cd / c_cand).is_file():
                        c_img_file = cd / c_cand
                        break
                if not c_img_file and cd.exists():
                    for f in sorted(cd.iterdir()):
                        if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                            c_img_file = f
                            break
            if c_img_file:
                ref_images_used["characters"].append({
                    "name": cname,
                    "image": c_img_file.name,
                    "asset_url": f"/api/asset/{stem}/char-ref/{cname}/{c_img_file.name}"
                })
                try:
                    rel_char_img = str(c_img_file.relative_to(PROJECT_ROOT))
                except Exception:
                    rel_char_img = str(c_img_file)
                cmd.extend(["--char-refs", f"{cname}:{rel_char_img}"])

        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now().isoformat()

        task = {
            "id": task_id,
            "stem": stem,
            "type": media_type,
            "tag_id": tag_id,
            "section": section,
            "prompt": tag_prompt or payload.get("prompt", ""),
            "model": effective_model,
            "ratio": effective_ratio,
            "size": effective_size,
            "extra_prompt": extra_prompt,
            "ref_images": ref_images_used,
            "status": "running",
            "started_at": now_iso,
            "finished_at": None,
            "duration_sec": 0,
            "command": " ".join(cmd),
            "stdout": "",
            "stderr": "",
            "error": None,
            "asset_url": None,
            "payload": payload
        }
        self.task_manager.add_task(self.outputs_dir, stem, task)

        def worker():
            start_t = time.time()
            try:
                proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.task_manager._running_procs[task_id] = proc
                stdout, stderr = proc.communicate()
                self.task_manager._running_procs.pop(task_id, None)

                duration = round(time.time() - start_t, 2)
                finished_iso = datetime.now().isoformat()

                attached_refs = []
                m_refs = re.search(r'Attached Reference Images \((\d+)\):\s*([^\n]+)', stdout)
                if m_refs:
                    attached_refs = [x.strip() for x in m_refs.group(2).split(",") if x.strip()]

                # Check if asset was produced
                asset_url = None
                if tag_id:
                    exts = [".png", ".jpg", ".jpeg", ".webp"] if media_type == "image" else [".mp4", ".webm"]
                    target_dir = ws_dir / ("images" if media_type == "image" else "videos")
                    for ext in exts:
                        p = target_dir / f"{tag_id}{ext}"
                        if p.exists():
                            asset_url = f"/api/asset/{stem}/{target_dir.name}/{p.name}"
                            break

                if proc.returncode != 0:
                    err_msg = stderr.strip() or stdout.strip() or f"Process exited with code {proc.returncode}"
                    self.task_manager.update_task(self.outputs_dir, stem, task_id, {
                        "status": "failed",
                        "error": err_msg,
                        "stdout": stdout,
                        "stderr": stderr,
                        "duration_sec": duration,
                        "finished_at": finished_iso,
                        "attached_ref_images": attached_refs
                    })
                else:
                    self.task_manager.update_task(self.outputs_dir, stem, task_id, {
                        "status": "completed",
                        "error": None,
                        "stdout": stdout,
                        "stderr": stderr,
                        "duration_sec": duration,
                        "finished_at": finished_iso,
                        "asset_url": asset_url,
                        "attached_ref_images": attached_refs
                    })
            except Exception as ex:
                self.task_manager._running_procs.pop(task_id, None)
                duration = round(time.time() - start_t, 2)
                self.task_manager.update_task(self.outputs_dir, stem, task_id, {
                    "status": "failed",
                    "error": str(ex),
                    "duration_sec": duration,
                    "finished_at": datetime.now().isoformat()
                })

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return task

    def handle_api_generate(self, stem):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}

            task = self.start_generation_task(stem, payload)
            self.send_json_response({
                "success": True,
                "task_id": task["id"],
                "status": "running",
                "tag_id": task.get("tag_id"),
                "section": task.get("section"),
                "type": task.get("type"),
                "message": f"Started generation task {task['id']} for {task.get('tag_id') or 'all'}"
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_get_tasks(self, stem, is_head=False):
        tasks = self.task_manager.load_tasks(self.outputs_dir, stem)
        self.send_json_response({"success": True, "tasks": tasks}, is_head=is_head)

    def handle_api_clear_tasks(self, stem):
        remaining = self.task_manager.clear_tasks(self.outputs_dir, stem)
        self.send_json_response({"success": True, "tasks": remaining})

    def handle_api_retry_task(self, stem):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
            task_id = payload.get("task_id")
            tasks = self.task_manager.load_tasks(self.outputs_dir, stem)
            target = next((t for t in tasks if t.get("id") == task_id), None)
            if not target:
                self.send_json_response({"error": f"Task '{task_id}' not found"}, status=404)
                return
            original_payload = target.get("payload") or {}
            new_task = self.start_generation_task(stem, original_payload)
            self.send_json_response({"success": True, "task_id": new_task["id"], "status": "running"})
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_cancel_task(self, stem):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
            task_id = payload.get("task_id")
            cancelled = self.task_manager.cancel_task(self.outputs_dir, stem, task_id)
            self.send_json_response({"success": True, "cancelled": cancelled})
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def get_workspace_markdown_path(self, stem: str) -> Optional[Path]:
        ws_dir = self.outputs_dir / stem
        if not ws_dir.exists():
            return None
        output_md = ws_dir / f"{stem}-output.md"
        if output_md.exists():
            return output_md
        md_files = [f for f in ws_dir.glob("*.md") if not f.name.startswith(".")]
        if md_files:
            return md_files[0]
        return None

    def handle_api_build_prompt(self, stem: str):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}

            tag_type = payload.get("type", "image")
            section = payload.get("section", "")
            before_text = payload.get("before_text", "")
            after_text = payload.get("after_text", "")
            tag_id = payload.get("tag_id", "")
            use_ai = payload.get("use_ai", False)

            ws_dir = self.outputs_dir / stem

            # Resolve narrative context from workspace markdown if before_text or after_text are missing
            if tag_id and (not before_text or not after_text):
                md_files = list(ws_dir.glob("*-output.md")) + list(ws_dir.glob("*.md"))
                for md_file in md_files:
                    if md_file.name.endswith(".backup.md"):
                        continue
                    try:
                        with open(md_file, "r", encoding="utf-8") as mf:
                            md_content = mf.read()
                        if tag_id in md_content and extract_tag_context:
                            ctx = extract_tag_context(md_content, tag_id)
                            if not before_text and ctx.get("before_text"):
                                before_text = ctx["before_text"]
                            if not after_text and ctx.get("after_text"):
                                after_text = ctx["after_text"]
                            if not section and ctx.get("section"):
                                section = ctx["section"]
                            break
                    except Exception:
                        pass

            # Load characters from workspace
            characters = []
            for char_base in ["char-ref", "characters"]:
                c_json = ws_dir / char_base / "characters.json"
                if c_json.exists():
                    try:
                        with open(c_json, "r", encoding="utf-8") as f:
                            characters = json.load(f).get("characters", [])
                            break
                    except Exception:
                        pass

            # Load style prompt from workspace
            style_prompt = None
            for s_base in ["style-ref", "style"]:
                s_json = ws_dir / s_base / "style.json"
                if s_json.exists():
                    try:
                        with open(s_json, "r", encoding="utf-8") as f:
                            style_prompt = json.load(f).get("style_prompt")
                            break
                    except Exception:
                        pass

            if build_prompt:
                prompt = build_prompt(
                    tag_type=tag_type,
                    section_title=section,
                    before_text=before_text,
                    after_text=after_text,
                    characters=characters,
                    style_prompt=style_prompt,
                    tag_id=tag_id,
                    story_title=stem,
                    use_ai=use_ai
                )
            else:
                prompt = f"[{tag_type.upper()}] {section}: {before_text} {after_text}".strip()

            # AI enrichment: use Gemini to refine the template prompt
            ai_refined = False
            start_time = time.time()
            start_iso = datetime.now().isoformat()
            if use_ai and prompt:
                try:
                    from google import genai
                    resolved_key = (payload.get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
                    if resolved_key:
                        os.environ["GEMINI_API_KEY"] = resolved_key
                        ai_client = genai.Client(api_key=resolved_key, http_options={"timeout": 60000})

                        primary_focus = after_text if after_text else before_text
                        sec_env = before_text if (after_text and before_text) else ""

                        # Match characters from workspace in primary and secondary context
                        matched_primary_chars = []
                        for c in characters:
                            cname = c.get("name", "")
                            if not cname:
                                continue
                            tokens = [cname]
                            if "·" in cname:
                                tokens.extend([part.strip() for part in cname.split("·") if len(part.strip()) >= 2])
                            role = c.get("role", "")
                            for en_alias in re.findall(r'\b[A-Z][a-z]+\b', role):
                                if len(en_alias) >= 4 and en_alias not in ["Main", "Character", "Protagonist", "Warrior", "Healer", "Wizard", "Adventurer"]:
                                    tokens.append(en_alias)
                            if any(tok in primary_focus for tok in tokens):
                                matched_primary_chars.append(c)

                        matched_sec_chars = []
                        for c in characters:
                            if c in matched_primary_chars:
                                continue
                            cname = c.get("name", "")
                            if not cname:
                                continue
                            tokens = [cname]
                            if "·" in cname:
                                tokens.extend([part.strip() for part in cname.split("·") if len(part.strip()) >= 2])
                            if any(tok in sec_env for tok in tokens):
                                matched_sec_chars.append(c)

                        ai_contents = [
                            "You are a master Art Director for animated feature films and fantasy storybooks. "
                            "Transform this narrative scene description into a visually stunning, production-ready image generation prompt.\n"
                            f"Scene Description Draft: '{prompt}'.\n"
                            f"PRIMARY FOCAL ACTION & SUBJECT (1st Priority): '{primary_focus}'.\n"
                        ]
                        if sec_env:
                            ai_contents.append(f"SECONDARY / BACKGROUND CONTEXT (2nd Priority): '{sec_env}'.\n")

                        if matched_primary_chars:
                            char_info = []
                            for c in matched_primary_chars:
                                c_name = c.get("name")
                                c_dna = c.get("visual_dna") or c.get("portrait_prompt") or ""
                                char_info.append(f"- Character: {c_name} (Role: {c.get('role', '')})\n  Visual DNA / Features: {c_dna}")
                            ai_contents.append(
                                "\nCRITICAL HERO IDENTITY REQUIREMENTS:\n"
                                f"The primary focus features this specific hero:\n" + "\n".join(char_info) + "\n"
                                "1. You MUST feature this exact character as the main focal subject.\n"
                                "2. You MUST explicitly name them in the prompt.\n"
                                "3. You MUST faithfully incorporate their Visual DNA (age, build, clothing, beard/hair, props, magical effects).\n"
                                "4. STRICTLY PROHIBITED: NEVER replace them with a generic adventurer, swordsman, or change their class/appearance.\n\n"
                            )

                        if matched_sec_chars:
                            sec_char_names = ", ".join(c.get("name", "") for c in matched_sec_chars)
                            ai_contents.append(f"Secondary character(s) present in background: {sec_char_names}.\n")

                        ai_contents.append(
                            "Requirements:\n"
                            "1) The PRIMARY focal action and subject MUST strictly be the main focus of the composition.\n"
                            "2) If a named hero is specified above, you MUST retain their exact name and physical traits.\n"
                            "3) Specify precise camera framing and shot composition.\n"
                            "4) Describe characters with concrete physical appearance details (hair, clothing, accessories, expressions).\n"
                            "5) Detail the environment and props with tangible visual elements.\n"
                            "6) Specify lighting quality, direction, color temperature, and atmospheric mood.\n"
                            "7) Include the art style description.\n"
                            "8) No spoken dialogue quotes. Purely visual and cinematic.\n"
                            "9) Keep the same language as the input (Chinese stays Chinese, English stays English).\n"
                            "10) Output ONLY the refined prompt text — no explanations, no labels, no quotation marks."
                        )

                        resp = ai_client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents="".join(ai_contents)
                        )
                        if resp and resp.text:
                            candidate_text = resp.text.strip()
                            # Check character fidelity: if primary characters were matched, ensure at least one is mentioned
                            if matched_primary_chars:
                                valid_hero = False
                                for c in matched_primary_chars:
                                    cname = c.get("name", "")
                                    check_tokens = [cname]
                                    if "·" in cname:
                                        check_tokens.extend([part.strip() for part in cname.split("·") if len(part.strip()) >= 2])
                                    if any(tok in candidate_text for tok in check_tokens):
                                        valid_hero = True
                                        break
                                if valid_hero:
                                    prompt = candidate_text
                                    ai_refined = True
                                else:
                                    # Gemini omitted the hero name, do not discard the valid hero prompt
                                    logger.warning("AI refinement omitted primary hero %s, preserving template prompt", [c.get("name") for c in matched_primary_chars])
                            else:
                                prompt = candidate_text
                                ai_refined = True
                except Exception as e:
                    logger.warning("Error during AI prompt enrichment: %s", e)

            # Record prompt task in history
            task_id = f"prompt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            duration = round(time.time() - start_time, 2)
            self.task_manager.add_task(self.outputs_dir, stem, {
                "id": task_id,
                "stem": stem,
                "type": "prompt",
                "tag_id": tag_id,
                "section": section,
                "prompt": prompt,
                "model": "gemini-2.5-flash" if ai_refined else "template",
                "status": "completed",
                "started_at": start_iso,
                "finished_at": datetime.now().isoformat(),
                "duration_sec": duration,
                "ai_refined": ai_refined,
                "stdout": f"Prompt generated for tag '{tag_id or 'new'}' ({'AI refined via gemini-2.5-flash' if ai_refined else 'Template based'}).",
                "stderr": "",
                "error": None
            })

            self.send_json_response({
                "success": True,
                "prompt": prompt,
                "tag_id": tag_id,
                "section": section,
                "type": tag_type,
                "ai_refined": ai_refined
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_insert_tag(self, stem: str):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}

            tag_id = payload.get("tag_id", "").strip()
            tag_type = payload.get("type", "image").strip().lower()
            section = payload.get("section", "").strip()
            prompt = payload.get("prompt", "").strip()
            insert_after_text = payload.get("insert_after_text", "").strip()
            after_tag_id = payload.get("after_tag_id", "").strip()

            if not tag_id:
                self.send_json_response({"error": "tag_id is required"}, status=400)
                return

            md_path = self.get_workspace_markdown_path(stem)
            if not md_path or not md_path.exists():
                self.send_json_response({"error": f"Story markdown file not found for workspace '{stem}'"}, status=404)
                return

            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()

            # Format the new tag as standard JSON comment
            tag_dict = {
                "type": tag_type,
                "id": tag_id,
                "section": section,
                "prompt": prompt
            }
            tag_str = f"<!-- storybook-media: {json.dumps(tag_dict, ensure_ascii=False)} -->"

            inserted = False
            # 1. Insert after specific existing tag if requested
            if after_tag_id:
                pattern = re.compile(rf'(<!--\s*storybook-media.*?id[\"\'=:\s]+{re.escape(after_tag_id)}.*?-->)', re.DOTALL)
                m = pattern.search(md_text)
                if m:
                    pos = m.end()
                    md_text = md_text[:pos] + "\n\n" + tag_str + md_text[pos:]
                    inserted = True

            # 2. Insert after specific paragraph text
            if not inserted and insert_after_text:
                idx = md_text.find(insert_after_text)
                if idx == -1 and len(insert_after_text) > 30:
                    idx = md_text.find(insert_after_text[:30])
                if idx != -1:
                    end_pos = idx + len(insert_after_text) if md_text.find(insert_after_text) != -1 else idx + 30
                    while end_pos < len(md_text) and md_text[end_pos] not in '\r\n':
                        end_pos += 1
                    while end_pos < len(md_text) and md_text[end_pos] in '\r\n':
                        end_pos += 1
                    md_text = md_text[:end_pos] + "\n\n" + tag_str + "\n\n" + md_text[end_pos:].lstrip('\r\n')
                    inserted = True

            # 3. Insert under section heading
            if not inserted and section:
                clean_sec = section.lstrip('#').strip()
                m = re.search(rf'^(#{{1,6}}\s+.*?{re.escape(clean_sec)}.*?)$', md_text, re.MULTILINE)
                if m:
                    pos = m.end()
                    md_text = md_text[:pos] + "\n\n" + tag_str + "\n\n" + md_text[pos:].lstrip('\r\n')
                    inserted = True

            # 4. Fallback: append at the end of story
            if not inserted:
                md_text = md_text.rstrip() + "\n\n" + tag_str + "\n"

            # Normalize multiple consecutive blank lines
            md_text = re.sub(r'\n{3,}', '\n\n', md_text)

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_text)

            self.send_json_response({
                "success": True,
                "message": f"Successfully inserted tag '{tag_id}' into story markdown",
                "tag_id": tag_id,
                "tag_str": tag_str
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_update_tag_prompt(self, stem: str):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}

            tag_id = payload.get("tag_id", "").strip()
            new_prompt = payload.get("prompt", "").strip()

            if not tag_id:
                self.send_json_response({"error": "tag_id is required"}, status=400)
                return

            md_path = self.get_workspace_markdown_path(stem)
            if not md_path or not md_path.exists():
                self.send_json_response({"error": f"Story markdown file not found for workspace '{stem}'"}, status=404)
                return

            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()

            def repl_json(m):
                raw = m.group(1)
                try:
                    data = json.loads(raw)
                    if data.get("id") == tag_id:
                        data["prompt"] = new_prompt
                        return f"<!-- storybook-media: {json.dumps(data, ensure_ascii=False)} -->"
                except Exception:
                    pass
                return m.group(0)

            updated = re.sub(r'<!--\s*storybook-media:\s*(\{.*?\})\s*-->', repl_json, md_text, flags=re.DOTALL)

            if updated == md_text:
                def repl_kv(m):
                    tag_content = m.group(1)
                    if f'id="{tag_id}"' in tag_content or f"id='{tag_id}'" in tag_content:
                        if 'prompt="' in tag_content:
                            return re.sub(r'prompt=".*?"', f'prompt={json.dumps(new_prompt)}', m.group(0))
                        elif "prompt='" in tag_content:
                            return re.sub(r"prompt='.*?'", f'prompt={json.dumps(new_prompt)}', m.group(0))
                        else:
                            return m.group(0).replace("-->", f' prompt={json.dumps(new_prompt)} -->')
                    return m.group(0)

                updated = re.sub(r'<!--\s*storybook-media\s+([^>]*?)\s*-->', repl_kv, md_text, flags=re.DOTALL)

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(updated)

            self.send_json_response({
                "success": True,
                "message": f"Updated prompt for tag '{tag_id}'",
                "tag_id": tag_id,
                "prompt": new_prompt
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_api_enrich_prompts(self, stem: str):
        start_time = time.time()
        start_iso = datetime.now().isoformat()
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}

            force = payload.get("force", False)
            use_ai = payload.get("use_ai", False)
            api_key = (payload.get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key

            md_path = self.get_workspace_markdown_path(stem)
            if not md_path or not md_path.exists():
                self.send_json_response({"error": f"Story markdown file not found for workspace '{stem}'"}, status=404)
                return

            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()

            if update_media_tag_prompts:
                ws = StoryWorkspace(self.outputs_dir / stem) if StoryWorkspace else None
                updated = update_media_tag_prompts(md_text, force=force, use_ai=use_ai, workspace=ws)
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(updated)

            # Record batch prompt task
            task_id = f"batch_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            duration = round(time.time() - start_time, 2)
            self.task_manager.add_task(self.outputs_dir, stem, {
                "id": task_id,
                "stem": stem,
                "type": "batch_prompt",
                "tag_id": "All Tags",
                "section": "",
                "prompt": f"Batch enrich prompts (force={force}, use_ai={use_ai})",
                "model": "gemini-2.5-flash" if use_ai else "template",
                "status": "completed",
                "started_at": start_iso,
                "finished_at": datetime.now().isoformat(),
                "duration_sec": duration,
                "stdout": "Successfully enriched all media prompts in workspace markdown.",
                "stderr": "",
                "error": None
            })

            self.send_json_response({
                "success": True,
                "message": "Enriched media prompts successfully"
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_spa_static(self, pathname, is_head=False):
        # If dist doesn't exist, provide a helpful fallback page
        if not self.dist_dir.exists():
            msg = """<!DOCTYPE html>
<html>
<head><title>Storybook Craft Viewer</title><meta charset="utf-8"></head>
<body style="font-family: sans-serif; padding: 2rem; max-width: 600px; margin: auto;">
  <h2>Storybook Craft Viewer</h2>
  <p>The frontend production build was not found at <code>viewer/dist</code>.</p>
  <p>To build or run in dev mode:</p>
  <pre style="background: #f4f4f4; padding: 1rem; border-radius: 8px;">
cd viewer
npm install
npm run build   # for static dist serving
npm run dev     # for hot-reloading dev server
</pre>
</body>
</html>""".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            if not is_head:
                self.wfile.write(msg)
            return

        # Clean pathname
        rel_path = pathname.lstrip("/")
        if not rel_path or rel_path == "":
            target = self.dist_dir / "index.html"
        else:
            target = (self.dist_dir / rel_path).resolve()

        if not str(target).startswith(str(self.dist_dir.resolve())) or not target.exists() or not target.is_file():
            # SPA fallback to index.html
            target = self.dist_dir / "index.html"

        mime_type, _ = mimetypes.guess_type(str(target))
        if not mime_type:
            mime_type = "text/html; charset=utf-8"

        file_size = target.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(file_size))
        self.end_headers()

        if not is_head:
            with open(target, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)


def run_server(port=5173, open_browser=True, outputs_dir=None):
    if outputs_dir:
        StorybookViewerHandler.outputs_dir = Path(outputs_dir).resolve()

    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, StorybookViewerHandler)
    url = f"http://localhost:{port}"

    print(f"📖 Storybook Craft Viewer running at: {url}")
    print(f"📁 Outputs directory: {StorybookViewerHandler.outputs_dir}")
    print("Press Ctrl+C to stop.")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping viewer server...")
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Storybook Craft Viewer Server")
    parser.add_argument("--port", type=int, default=5173, help="Port to listen on (default: 5173)")
    parser.add_argument("--no-open", action="store_true", help="Do not automatically open browser")
    parser.add_argument("--outputs-dir", type=str, default=None, help="Custom outputs directory")
    args = parser.parse_args()

    run_server(port=args.port, open_browser=not args.no_open, outputs_dir=args.outputs_dir)
