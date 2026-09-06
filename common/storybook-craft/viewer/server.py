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
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote

VIEWER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = VIEWER_DIR.parent
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DEFAULT_EXAMPLES_DIR = PROJECT_ROOT / "examples"
DIST_DIR = VIEWER_DIR / "dist"

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
        StoryWorkspace
    )
except Exception:
    compose_reference_prompt = None
    match_characters_for_tag = None
    find_python_for_gemini = None
    build_prompt = None
    update_media_tag_prompts = None
    extract_media_tags = None
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
    "scenes": {}
}


class StorybookViewerHandler(SimpleHTTPRequestHandler):
    outputs_dir = DEFAULT_OUTPUTS_DIR
    examples_dir = DEFAULT_EXAMPLES_DIR
    dist_dir = DIST_DIR

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

        self.send_json_response({"error": "POST endpoint not found"}, status=404)


    def handle_request(self, is_head=False):
        parsed = urlparse(self.path)
        pathname = unquote(parsed.path)

        # 1. API: /api/workspaces
        if pathname == "/api/workspaces":
            self.handle_api_workspaces(is_head=is_head)
            return

        # 1.5 API: /api/workspace/<stem>/settings
        if pathname.startswith("/api/workspace/") and pathname.endswith("/settings"):
            stem = pathname[len("/api/workspace/"):-len("/settings")].strip("/")
            self.handle_api_get_settings(stem, is_head=is_head)
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

                        if not existing:
                            characters.append({
                                "name": cd.name,
                                "role": c_json.get("role", "Character"),
                                "visual_dna": c_json.get("visual_dna", ""),
                                "portrait_prompt": c_json.get("portrait_prompt", ""),
                                "images": imgs,
                                "source": c_json.get("source", "collected")
                            })
                        else:
                            if not existing.get("images"):
                                existing["images"] = imgs
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
                if style_imgs and not style.get("images"):
                    style["images"] = style_imgs

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
            tags = []
            for rt in raw_tags:
                tag_id = rt.get("id", "")
                tag_type = rt.get("type", "image")
                matched = next((
                    a for a in all_generated
                    if a["id"] == tag_id or
                    a["name"].startswith(tag_id + ".") or
                    tag_id in a["name"] or
                    (rt.get("asset") and a["name"] == Path(rt["asset"]).name)
                ), None)

                rt_clean = {k: v for k, v in rt.items() if not k.startswith("_")}
                rt_clean["type"] = tag_type
                rt_clean["section"] = rt_clean.get("section") or rt_clean.get("title") or "Story Scene"
                rt_clean["prompt"] = rt_clean.get("prompt", "")
                rt_clean["context_hint"] = rt_clean.get("context_hint", "")
                rt_clean["isGenerated"] = matched is not None
                rt_clean["matchedAsset"] = matched

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
                    char_refs_data.append({
                        "name": cname,
                        "role": ch.get("role", "Character"),
                        "visual_dna": ch.get("visual_dna", ""),
                        "image": c_img,
                        "assetUrl": f"/api/asset/{stem}/char-ref/{cname}/{c_img}" if c_img else None,
                        "role_guide": f"Character Identity Reference: {cname} (Context Matched)"
                    })

                # Style Reference
                style_imgs = style.get("images", [])
                style_img = style_imgs[0] if style_imgs else None
                style_ref_data = {
                    "name": style_img,
                    "assetUrl": f"/api/asset/{stem}/style-ref/{style_img}" if style_img else None,
                    "style_name": style.get("style_name", "Art Style"),
                    "style_prompt": style.get("style_prompt", ""),
                    "role": "Style Reference (Always Active)"
                } if style_img else None

                # Composed prompt with strict anti-modification template
                composed_prompt = ""
                if compose_reference_prompt:
                    composed_prompt = compose_reference_prompt(
                        context_prompt=rt_clean["prompt"],
                        style_prompt=style.get("style_prompt", ""),
                        has_style_image=style_img is not None,
                        character_refs=char_refs_data,
                        tag_type=tag_type
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

    def handle_api_generate(self, stem):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}

            tag_id = payload.get("tag_id")
            section = payload.get("section")
            media_type = payload.get("type", "image")
            ratio = payload.get("ratio")
            size = payload.get("size")
            model = payload.get("model")

            ws_dir = self.outputs_dir / stem
            output_md = ws_dir / f"{stem}-output.md"
            if not output_md.exists():
                md_files = list(ws_dir.glob("*.md"))
                if md_files:
                    output_md = md_files[0]
                else:
                    self.send_json_response({"error": f"No storybook markdown found in {ws_dir}"}, status=404)
                    return

            ws_settings = self.load_workspace_settings(stem)
            scene_override = ws_settings.get("scenes", {}).get(tag_id, {}) if tag_id else {}
            global_type_cfg = ws_settings.get("global", {}).get(media_type, {})

            effective_ratio = (
                ratio if ratio and ratio != "inherit"
                else scene_override.get("ratio")
                or global_type_cfg.get("ratio")
                or "16:9"
            )

            effective_size = (
                size if size and size != "inherit"
                else scene_override.get("size")
                or global_type_cfg.get("size")
                or "1K"
            )

            effective_model = (
                model if model and model != "inherit"
                else scene_override.get("model")
                or global_type_cfg.get("model")
                or ("gemini-3.1-flash-image" if media_type == "image" else "veo-2.0-generate-001")
            )

            py_exe = find_python_for_gemini() if find_python_for_gemini else sys.executable
            storybook_script = Path(__file__).resolve().parent.parent / "storybook.py"
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

            # Execute generation
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                self.send_json_response({
                    "success": False,
                    "error": res.stderr.strip() or res.stdout.strip(),
                    "stdout": res.stdout,
                    "stderr": res.stderr
                }, status=500)
            else:
                self.send_json_response({
                    "success": True,
                    "message": f"Generated successfully for {tag_id or section or 'all'}",
                    "stdout": res.stdout,
                    "tag_id": tag_id,
                    "section": section
                })
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

            self.send_json_response({
                "success": True,
                "prompt": prompt,
                "tag_id": tag_id,
                "section": section,
                "type": tag_type
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
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}

            force = payload.get("force", False)
            use_ai = payload.get("use_ai", False)

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
