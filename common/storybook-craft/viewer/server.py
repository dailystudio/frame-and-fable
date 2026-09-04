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
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote

VIEWER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = VIEWER_DIR.parent
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DEFAULT_EXAMPLES_DIR = PROJECT_ROOT / "examples"
DIST_DIR = VIEWER_DIR / "dist"


class StorybookViewerHandler(SimpleHTTPRequestHandler):
    outputs_dir = DEFAULT_OUTPUTS_DIR
    examples_dir = DEFAULT_EXAMPLES_DIR
    dist_dir = DIST_DIR

    def end_headers(self):
        # Enable CORS for local dev servers
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_HEAD(self):
        self.handle_request(is_head=True)

    def do_GET(self):
        self.handle_request(is_head=False)

    def handle_request(self, is_head=False):
        parsed = urlparse(self.path)
        pathname = unquote(parsed.path)

        # 1. API: /api/workspaces
        if pathname == "/api/workspaces":
            self.handle_api_workspaces(is_head=is_head)
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
                        generated_images.append({
                            "name": f.name,
                            "id": f.stem,
                            "sizeBytes": f.stat().st_size,
                            "path": f"images/{f.name}",
                            "assetUrl": f"/api/asset/{stem}/images/{f.name}"
                        })

            generated_videos = []
            videos_dir = ws_dir / "videos"
            if videos_dir.exists():
                for f in sorted(videos_dir.iterdir()):
                    if f.is_file() and f.suffix.lower() in {".mp4", ".webm"}:
                        generated_videos.append({
                            "name": f.name,
                            "id": f.stem,
                            "sizeBytes": f.stat().st_size,
                            "path": f"videos/{f.name}",
                            "assetUrl": f"/api/asset/{stem}/videos/{f.name}"
                        })

            # Markdown Content
            markdown_content = ""
            markdown_type = "none"
            candidates = [
                (ws_dir / f"{stem}-output.md", "output"),
                (self.examples_dir / f"{stem}.md", "example"),
                (self.examples_dir / f"{stem}_crafted.md", "example"),
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

            # Extract tags
            tags = []
            tag_regex = re.compile(r'<!--\s*storybook-media:\s*(\{.*?\})\s*-->', re.DOTALL)
            for m in tag_regex.finditer(markdown_content):
                try:
                    tags.append(json.loads(m.group(1)))
                except Exception:
                    pass

            self.send_json_response({
                "stem": stem,
                "characters": characters,
                "style": style,
                "generatedImages": generated_images,
                "generatedVideos": generated_videos,
                "markdownContent": markdown_content,
                "markdownType": markdown_type,
                "tags": tags
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
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()

        if not is_head:
            with open(target, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)

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
    httpd = HTTPServer(server_address, StorybookViewerHandler)
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
