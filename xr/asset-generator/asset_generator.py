#!/usr/bin/env python3
"""
==============================================================================
Asset Generator CLI (asset-generator / generate-asset / asset-craft)
==============================================================================
A unified, end-to-end generative 3D asset pipeline for characters and common
objects (furniture, props, items, environment assets).

Orchestrates:
  1. Input Concept: Reference Image or Text Prompt + Optional Style Image/Prompt
  2. Multi-Views: T-Pose Views (Characters) or Object Views (Props/Furniture)
  3. Visual Confirmation: Terminal/GUI inspection & interactive confirmation
  4. 3D Model Generation: Hyper3D Gen-2.5 with 4K textures, root grounding, etc.
  5. Skeletal Rigging & Animation: Pose binding for characters (Mixamo / Rig-Binder)
==============================================================================
"""

import sys
import os
import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# Terminal color styling
BOLD = "\033[1m"
GREEN = "\033[0;32m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
YELLOW = "\033[0;33m"
MAGENTA = "\033[0;35m"
RED = "\033[0;31m"
RESET = "\033[0m"

def load_dotenv():
    """Load API keys from gitignored .env files if not already in os.environ."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path.home() / ".env",
    ]
    for env_path in candidates:
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

load_dotenv()

# Default API keys and configurations (strictly loaded from environment / .env)
DEFAULT_HYPER3D_KEY = os.environ.get("HYPER3D_API_KEY", os.environ.get("RODIN_API_KEY", ""))
DEFAULT_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))

COMMON_OBJECT_KEYWORDS = {
    "table", "desk", "chair", "stool", "sofa", "couch", "bench", "bed", "shelf",
    "cabinet", "cup", "mug", "glass", "bottle", "plate", "bowl", "vase", "pot",
    "pan", "fork", "knife", "spoon", "sword", "shield", "axe", "bow", "arrow",
    "gun", "weapon", "car", "vehicle", "truck", "bike", "bicycle", "motorcycle",
    "airplane", "boat", "ship", "train", "box", "crate", "barrel", "chest",
    "lamp", "lantern", "candle", "light", "clock", "watch", "telephone", "phone",
    "computer", "laptop", "monitor", "keyboard", "mouse", "book", "scroll",
    "guitar", "piano", "drum", "violin", "rock", "stone", "boulder", "tree",
    "plant", "flower", "bush", "building", "house", "tower", "castle", "door",
    "window", "pillar", "column", "statue", "coin", "gem", "ring", "crown"
}

CHARACTER_KEYWORDS = {
    "character", "person", "human", "avatar", "hero", "warrior", "fighter",
    "ninja", "wizard", "mage", "knight", "soldier", "man", "woman", "boy",
    "girl", "kid", "creature", "monster", "alien", "robot", "golem", "beast",
    "t-pose", "tpose", "humanoid", "fighter", "npc"
}


def log_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{CYAN} {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


def log_step(step_num: int, title: str):
    print(f"\n{BOLD}{BLUE}▶ Step {step_num}: {title}{RESET}")
    print(f"{BLUE}{'-' * 50}{RESET}")


def log_info(msg: str):
    print(f" {CYAN}ℹ{RESET} {msg}")


def log_success(msg: str):
    print(f" {GREEN}✓{RESET} {msg}")


def log_warning(msg: str):
    print(f" {YELLOW}⚠{RESET} {msg}")


def log_error(msg: str):
    print(f" {RED}✖{RESET} {msg}", file=sys.stderr)


def find_tool(tool_name: str) -> Optional[str]:
    """Locate tool executable in PATH or ~/.local/bin."""
    path = shutil.which(tool_name)
    if path:
        return path
    candidate = Path.home() / ".local" / "bin" / tool_name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def run_command(cmd: List[str], dry_run: bool = False, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    """Run an external command, supporting dry-run logging."""
    cmd_str = " ".join(f"'{c}'" if " " in c else c for c in cmd)
    if dry_run:
        print(f"  {YELLOW}[DRY-RUN]{RESET} Would execute:\n    {cmd_str}")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    print(f"  {BOLD}Executing:{RESET} {cmd_str}")
    process_env = os.environ.copy()
    if env:
        process_env.update(env)

    result = subprocess.run(cmd, env=process_env)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def infer_asset_type(name: str, prompt: Optional[str], raw_input: Optional[str], requested_type: Optional[str], has_pose_flag: bool) -> str:
    """Infers whether the asset is a 'character' or an 'object'."""
    if requested_type:
        norm = requested_type.strip().lower()
        if norm in ("character", "char", "avatar", "person"):
            return "character"
        if norm in ("object", "prop", "furniture", "item", "scene"):
            return "object"

    if has_pose_flag:
        return "character"

    tokens = set()
    for text_source in (name, prompt, raw_input):
        if text_source:
            for t in text_source.lower().replace("-", " ").replace("_", " ").split():
                cleaned = t.strip(".,;:!?()[]{}'\"")
                if cleaned:
                    tokens.add(cleaned)

    # Check for character keywords first
    if any(k in tokens for k in CHARACTER_KEYWORDS):
        return "character"

    # Check for object keywords
    if any(k in tokens for k in COMMON_OBJECT_KEYWORDS):
        return "object"

    # Default to character
    return "character"


def is_url(s: Optional[str]) -> bool:
    """Check if string is a remote HTTP/HTTPS URL."""
    if not s:
        return False
    s = s.strip()
    return s.startswith("http://") or s.startswith("https://")


def download_url(url: str, output_dir: Path, filename: Optional[str] = None) -> Path:
    """Downloads a URL with a browser User-Agent header."""
    output_dir.mkdir(parents=True, exist_ok=True)
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if not filename:
        filename = Path(parsed.path).name or "downloaded_image.jpg"
    target_path = output_dir / filename

    if target_path.is_file() and target_path.stat().st_size > 0:
        log_info(f"Using previously downloaded file: {target_path}")
        return target_path.resolve()

    log_info(f"Downloading remote image from: {url}")
    cmd = [
        "curl", "-sSL",
        "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-H", f"Referer: {parsed.scheme}://{parsed.netloc}/",
        url,
        "-o", str(target_path)
    ]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        log_error(f"Failed to download image from {url}: {e}")
        sys.exit(1)

    if not target_path.is_file() or target_path.stat().st_size == 0:
        log_error(f"Downloaded file at {target_path} is empty or missing.")
        sys.exit(1)

    log_success(f"Downloaded image to: {target_path} ({target_path.stat().st_size / 1024:.1f} KB)")
    return target_path.resolve()


def is_image_file(path_str: Optional[str]) -> bool:
    """Check if string points to an existing image file or valid image URL."""
    if not path_str:
        return False
    if is_url(path_str):
        return True
    p = Path(path_str)
    if not p.is_file():
        return False
    return p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")


def discover_multiviews(search_dir: Path) -> Dict[str, Path]:
    """Find Front, Back, Left, Right, Top views in a directory."""
    views = {}
    if not search_dir.is_dir():
        return views

    patterns = {
        "F": ["F.png", "f.png", "front.png", "*_front.png", "*_f.png"],
        "B": ["B.png", "b.png", "back.png", "*_back.png", "*_b.png"],
        "L": ["L.png", "l.png", "left.png", "*_left.png", "*_l.png"],
        "R": ["R.png", "r.png", "right.png", "*_right.png", "*_r.png"],
        "T": ["T.png", "t.png", "top.png", "*_top.png", "*_t.png"],
    }

    for tag, file_patterns in patterns.items():
        for pat in file_patterns:
            matches = sorted(search_dir.glob(pat))
            # Exclude files in subdirectories or hidden files
            valid_matches = [m for m in matches if m.is_file() and not m.name.startswith(".")]
            if valid_matches:
                views[tag] = valid_matches[0].resolve()
                break

    return views


def prompt_user_confirmation(views: Dict[str, Path], interactive: bool = True) -> bool:
    """Prompt user to visually confirm generated multi-views."""
    if not interactive or not sys.stdin.isatty():
        log_info("Non-interactive mode or piped input detected. Auto-confirming views.")
        return True

    print(f"\n{BOLD}{YELLOW}------------------------------------------------------------{RESET}")
    print(f"{BOLD}{YELLOW} Multi-View Visual Inspection & Confirmation{RESET}")
    print(f"{BOLD}{YELLOW}------------------------------------------------------------{RESET}")
    for tag in ("F", "L", "R", "B", "T"):
        if tag in views:
            size_kb = views[tag].stat().st_size / 1024.0
            print(f"   [{tag}] {views[tag].name} ({size_kb:.1f} KB) -> {views[tag]}")

    # Attempt to open Preview on macOS
    if sys.platform == "darwin":
        img_paths = [str(v) for v in views.values()]
        try:
            subprocess.Popen(["open", "-a", "Preview"] + img_paths, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log_info("Opened multi-view images in macOS Preview for visual inspection.")
        except Exception:
            pass

    print(f"\n{BOLD}Options:{RESET}")
    print(f"  [{GREEN}Y{RESET}] / Enter  : Confirm views and proceed to 3D model generation")
    print(f"  [{YELLOW}R{RESET}]        : Reject and cancel generation")
    print(f"  [{RED}Q{RESET}]        : Quit immediately\n")

    try:
        response = input(f"{BOLD}Confirm views? [Y/r/q]: {RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted by user.")
        return False

    if response in ("", "y", "yes"):
        log_success("Multi-views confirmed by user.")
        return True
    return False


def query_task_list(api_key: str, page: int = 1):
    """Query and display Hyper3D account task history."""
    import urllib.request
    import ssl

    log_header(f"Hyper3D Rodin - Created 3D Models & Tasks (Page {page})")
    url = f"https://api.hyper3d.com/api/v2/check_balance?usage_page={page}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    ctx = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        log_error(f"Failed to query Hyper3D account: {e}")
        sys.exit(1)

    if "error" in data:
        log_error(f"API Error: {data.get('message', data['error'])}")
        sys.exit(1)

    print(f" Remaining Credits: {BOLD}{GREEN}{data.get('balance', 'N/A')}{RESET}\n")
    usage = data.get("usage", [])
    if not usage:
        print(f" No generation tasks found on page {page}.")
    else:
        print(f" {'#':<3} {'Task UUID':<38} {'Created Time (UTC)':<20} {'Item / Tier':<28} {'Cost':<6}")
        print("-" * 100)
        for i, u in enumerate(usage, 1):
            uuid = u.get("task_uuid", "N/A")
            t = u.get("time", "")[:19].replace("T", " ")
            item = u.get("item", "")
            amt = str(u.get("amount", ""))
            print(f" {i:<3} {uuid:<38} {t:<20} {item:<28} {amt:<6}")
        print("-" * 100)

    print(f"\n{BOLD}To download any model by task UUID:{RESET}")
    print(f"  asset-generator --download <TASK_UUID> -o outputs/<TASK_UUID>")


# ==============================================================================
# Main Pipeline Implementation
# ==============================================================================
class AssetPipeline:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.api_key = args.api_key or DEFAULT_HYPER3D_KEY
        self.gemini_key = args.gemini_key or DEFAULT_GEMINI_KEY
        self.dry_run = args.dry_run

        # Determine target name and category
        self.asset_name = self._resolve_asset_name()
        self.asset_type = infer_asset_type(
            name=self.asset_name,
            prompt=args.prompt,
            raw_input=args.input,
            requested_type=args.type,
            has_pose_flag=args.step == "pose" or args.anim is not None
        )

        # Output directory
        if args.output_dir:
            self.output_dir = Path(args.output_dir).resolve()
        else:
            # Default to outputs/<asset_name>
            self.output_dir = (Path.cwd() / "outputs" / self.asset_name).resolve()

        self.model_dir = self.output_dir / "model"
        self.pose_dir = self.model_dir / "pose"

    def _resolve_asset_name(self) -> str:
        if self.args.name:
            return self.args.name.strip()
        import re
        text = self.args.input or self.args.prompt or ""
        if is_url(text):
            from urllib.parse import urlparse
            url_path = Path(urlparse(text).path)
            stem = re.sub(r"(_ss\d+|_thumb|_preview|_photo|_screen\d*)$", "", url_path.stem.lower())
            if stem in ("f", "b", "l", "r", "front", "back", "left", "right", "ref", "concept", "input", "image") and url_path.parent.name:
                return url_path.parent.name
            return stem or "custom_asset"

        p = Path(text)
        if (p.is_file() or p.is_dir()) and not any(c in text for c in (" ", "\n", "\t")):
            if p.is_file() and p.stem.lower() in ("f", "b", "l", "r", "front", "back", "left", "right", "ref", "concept", "input") and p.parent.name:
                return p.parent.name
            return p.stem

        words = [w for w in re.findall(r"[a-zA-Z0-9]+", text.lower()) if w]
        if words:
            # Take up to 4 words
            return "_".join(words[:4])
        return "custom_asset"

    def run(self):
        log_header(f"Asset Generation Pipeline: {self.asset_name} ({self.asset_type.upper()})")
        print(f" Asset Name      : {BOLD}{self.asset_name}{RESET}")
        print(f" Category        : {BOLD}{self.asset_type.upper()}{RESET}")
        print(f" Target Directory: {self.output_dir}")
        print(f" Format          : {self.args.format} ({self.args.triangles} triangles)")
        print(f" 4K Textures     : {'Enabled (HighPack 4096x4096)' if self.args.texture_4k else 'Disabled (2048x2048)'}")
        print(f" Root Grounding  : {self.args.root}")
        if self.asset_type == "character":
            print(f" Rigging Engine  : {self.args.rig_engine}")

        # Check required executables
        self._check_tools()

        # Step 1: Input Concept & Multi-View Generation
        views = self._step_views()

        # Step 2: 3D Model Creation
        primary_model = self._step_model(views)

        # Step 3: Pose & Animation (Characters only)
        self._step_pose(primary_model)

        log_header(f"Generation Complete: {self.asset_name}")
        log_success(f"All generated assets available in: {self.output_dir}")
        if (self.model_dir / f"{self.asset_name}.{self.args.format}").exists():
            log_success(f"Primary 3D Model: {self.model_dir / f'{self.asset_name}.{self.args.format}'}")

    def _check_tools(self):
        tools = ["model-creator"]
        if self.args.step in ("all", "views") and not self.args.skip_views:
            if self.asset_type == "character":
                tools.append("t-pose-multiviews")
            else:
                tools.append("model-multiviews")
            tools.append("gemini-image")
        if self.asset_type == "character" and self.args.step in ("all", "pose") and not self.args.skip_pose:
            if self.args.rig_engine == "mixamo":
                tools.append("pose-binder")
            else:
                tools.append("rig-binder")

        for t in tools:
            resolved = find_tool(t)
            if not resolved:
                log_error(f"Required command '{t}' not found in PATH or ~/.local/bin.")
                sys.exit(1)

    # --------------------------------------------------------------------------
    # Step 1: Views
    # --------------------------------------------------------------------------
    def _step_views(self) -> Dict[str, Path]:
        if self.args.step not in ("all", "views") or self.args.skip_views:
            log_info("Skipping multi-view generation as requested.")
            return discover_multiviews(self.output_dir)

        log_step(1, f"Multi-View Generation ({self.asset_type.upper()})")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Check if views already exist and force is not set
        existing_views = discover_multiviews(self.output_dir)
        if len(existing_views) >= 3 and not self.args.force:
            log_info(f"Existing multi-views found ({len(existing_views)} views). Use --force to regenerate.")
            for tag, p in existing_views.items():
                print(f"   [{tag}] {p.name}")
            return existing_views

        if not self.dry_run and not self.gemini_key:
            log_error("GEMINI_API_KEY is not set. Please export GEMINI_API_KEY=<your_api_key> (or pass --gemini-key).")
            sys.exit(1)

        # Resolve reference image or synthesize from prompt
        ref_image = self._resolve_or_synthesize_concept()

        # If user requested single-view / direct 3D for objects
        if self.asset_type == "object" and self.args.single_view:
            log_info("Single-view mode requested for object. Skipping multi-view expansion.")
            return {"F": ref_image}

        # Generate multi-views
        if self.asset_type == "character":
            self._generate_character_views(ref_image)
        else:
            self._generate_object_views(ref_image)

        views = discover_multiviews(self.output_dir)
        if not views and not self.dry_run:
            log_error(f"No multi-views were produced in {self.output_dir}.")
            sys.exit(1)

        # Interactive confirmation
        if not self.args.no_confirm and not self.dry_run:
            confirmed = prompt_user_confirmation(views, interactive=True)
            if not confirmed:
                log_warning("Pipeline aborted during view confirmation.")
                sys.exit(0)

        if self.args.step == "views":
            log_success(f"Views step finished. Generated {len(views)} views.")
            sys.exit(0)

        return views

    def _resolve_or_synthesize_concept(self) -> Path:
        """Ensures a reference image exists, generating one via gemini-image if needed."""
        # Check if style image is a URL
        if self.args.style_image and is_url(self.args.style_image):
            self.args.style_image = str(download_url(self.args.style_image, self.output_dir))

        # 1. Check if input is a URL or valid local image path
        if self.args.input and is_url(self.args.input):
            return download_url(self.args.input, self.output_dir)
        if self.args.ref_image and is_url(self.args.ref_image):
            return download_url(self.args.ref_image, self.output_dir)

        if self.args.input and is_image_file(self.args.input):
            return Path(self.args.input).resolve()
        if self.args.ref_image and is_image_file(self.args.ref_image):
            return Path(self.args.ref_image).resolve()

        # 2. Check if output dir already contains concept or F.png
        for cand in ("concept.png", "ref.png", "F.png"):
            cand_p = self.output_dir / cand
            if cand_p.is_file():
                log_info(f"Using existing reference image: {cand_p}")
                return cand_p

        # 3. Synthesize reference concept using gemini-image
        prompt_text = self.args.prompt or self.args.input
        if not prompt_text:
            log_error("No reference image or prompt specified. Please provide an image (-i) or prompt (-p).")
            sys.exit(1)

        log_info(f"Synthesizing reference concept image from text prompt: \"{prompt_text}\"")
        concept_path = self.output_dir / "concept.png"

        if self.asset_type == "character":
            base_prompt = f"Full body concept art of {prompt_text}, facing front in neutral T-pose, arms outstretched horizontally, legs straight shoulder-width apart, pure white background, studio lighting, highly detailed 3D asset model concept, orthographic presentation"
        else:
            base_prompt = f"Product design concept of {prompt_text}, perfectly centered, pure white background, studio lighting, highly detailed 3D asset model concept, clean orthographic presentation, no shadows"

        if self.args.style_prompt:
            base_prompt += f", {self.args.style_prompt}"

        gemini_bin = find_tool("gemini-image")
        cmd = [gemini_bin, base_prompt, "-s", "4K", "-r", "1:1", "-o", str(concept_path)]
        if self.args.style_image and is_image_file(self.args.style_image):
            cmd.extend(["-i", str(Path(self.args.style_image).resolve())])

        run_command(cmd, dry_run=self.dry_run, env={"GEMINI_API_KEY": self.gemini_key})
        log_success(f"Synthesized concept image: {concept_path}")
        return concept_path

    def _generate_character_views(self, ref_image: Path):
        tpose_bin = find_tool("t-pose-multiviews")
        out_stem = str(self.output_dir / self.asset_name)

        extra_prompt = self.args.views_prompt or "pure white background, full body in frame, clean orthographic projection, for 3D modeling"
        if self.args.style_prompt:
            extra_prompt += f", {self.args.style_prompt}"

        cmd = [
            tpose_bin,
            "-i", str(ref_image),
            "-o", f"{out_stem}.png",
            "-p", extra_prompt,
            "-s", "4K",
            "-r", "1:1"
        ]
        if self.args.style_image and is_image_file(self.args.style_image):
            cmd.extend(["-S", str(Path(self.args.style_image).resolve())])
        if self.args.is_front_view:
            cmd.append("--is-front-view")

        run_command(cmd, dry_run=self.dry_run, env={"GEMINI_API_KEY": self.gemini_key})

        # Standardize filenames to F.png, B.png, L.png, R.png in output_dir
        self._standardize_view_filenames(ref_image)

    def _generate_object_views(self, ref_image: Path):
        multiview_bin = find_tool("model-multiviews")
        out_stem = str(self.output_dir / self.asset_name)

        extra_prompt = self.args.views_prompt or "product multi-view, orthographic projection, pure white background, studio lighting, clean geometry, for 3D modeling"
        if self.args.style_prompt:
            extra_prompt += f", {self.args.style_prompt}"

        cmd = [
            multiview_bin,
            "-i", str(ref_image),
            "-o", f"{out_stem}.png",
            "-v", "left; right; back",
            "-p", extra_prompt,
            "-s", "4K",
            "-r", "1:1"
        ]
        if self.args.style_image and is_image_file(self.args.style_image):
            cmd.extend(["-S", str(Path(self.args.style_image).resolve())])

        run_command(cmd, dry_run=self.dry_run, env={"GEMINI_API_KEY": self.gemini_key})

        # Standardize filenames to F.png, B.png, L.png, R.png in output_dir
        self._standardize_view_filenames(ref_image)

    def _standardize_view_filenames(self, ref_image: Optional[Path] = None):
        """Ensures canonical F.png, B.png, L.png, R.png exist in output directory."""
        if self.dry_run:
            return

        mappings = [
            ("F.png", ["*_front.png", "front.png", f"{self.asset_name}_front.png"]),
            ("B.png", ["*_back.png", "back.png", f"{self.asset_name}_back.png"]),
            ("L.png", ["*_left.png", "left.png", f"{self.asset_name}_left.png"]),
            ("R.png", ["*_right.png", "right.png", f"{self.asset_name}_right.png"]),
            ("T.png", ["*_top.png", "top.png", f"{self.asset_name}_top.png"]),
        ]

        for target_name, patterns in mappings:
            target_path = self.output_dir / target_name
            if target_path.exists() and not self.args.force:
                continue
            for pat in patterns:
                matches = list(self.output_dir.glob(pat))
                if matches and matches[0].is_file():
                    shutil.copy2(matches[0], target_path)
                    break

        # If F.png still doesn't exist, use ref_image
        f_path = self.output_dir / "F.png"
        if not f_path.exists() and ref_image and ref_image.is_file():
            shutil.copy2(ref_image, f_path)

    # --------------------------------------------------------------------------
    # Step 2: 3D Model
    # --------------------------------------------------------------------------
    def _step_model(self, views: Dict[str, Path]) -> Path:
        if self.args.step not in ("all", "model") or self.args.skip_model:
            log_info("Skipping 3D model generation as requested.")
            return self._find_primary_model()

        log_step(2, f"3D Model Generation ({self.args.format.upper()} - {'4K Textures' if self.args.texture_4k else '2K Textures'})")
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Check if model already exists and force is not set
        existing_model = self._find_primary_model()
        if existing_model.is_file() and not self.args.force:
            log_info(f"Model already exists at: {existing_model}. Use --force to regenerate.")
            return existing_model

        if not self.dry_run and not self.api_key:
            log_error("HYPER3D_API_KEY (or RODIN_API_KEY) is not set. Please export HYPER3D_API_KEY=<your_api_key> (or pass --api-key).")
            sys.exit(1)

        model_creator_bin = find_tool("model-creator")
        cmd = [
            model_creator_bin,
            "--provider", "hyper3d",
            "--api-key", self.api_key,
            "-f", self.args.format,
            "--triangles", str(self.args.triangles),
            "-o", str(self.model_dir),
            "--root", self.args.root,
        ]

        if self.args.texture_4k:
            cmd.extend(["--addons", "HighPack", "--texture-mode", "high", "--tier", "Gen-2.5-High"])

        # Feed views or prompt
        if views:
            img_list = []
            lbl_list = []
            for tag in ("F", "B", "L", "R", "T"):
                if tag in views and views[tag].is_file():
                    img_list.append(str(views[tag]))
                    lbl_list.append(tag)

            if img_list:
                cmd.extend(["-i"] + img_list)
                cmd.extend(["--image-labels"] + lbl_list)
            else:
                cmd.extend(["-p", self.args.prompt or self.asset_name])
        else:
            cmd.extend(["-p", self.args.prompt or self.asset_name])

        run_log = self.model_dir / ".run.log"
        if not self.dry_run:
            with open(run_log, "w") as log_f:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                task_uuid = None
                for line in process.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    log_f.write(line)
                    if "Task UUID:" in line:
                        task_uuid = line.split("Task UUID:")[-1].strip()

                process.wait()
                if process.returncode != 0:
                    log_error(f"3D Model generation failed with exit code: {process.returncode}")
                    sys.exit(process.returncode)

            # Record task metadata
            primary_file = "base_high_pbr." + self.args.format if (self.model_dir / f"base_high_pbr.{self.args.format}").exists() else f"base_basic_pbr.{self.args.format}"
            symlink_target = self.model_dir / f"{self.asset_name}.{self.args.format}"
            if (self.model_dir / primary_file).exists():
                try:
                    if symlink_target.is_symlink() or symlink_target.is_file():
                        symlink_target.unlink()
                    symlink_target.symlink_to(primary_file)
                except Exception as e:
                    log_warning(f"Could not create symlink {symlink_target}: {e}")

            metadata = {
                "name": self.asset_name,
                "category": self.asset_type,
                "task_uuid": task_uuid or "N/A",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tier": "Gen-2.5-High" if self.args.texture_4k else "Gen-2.5-Medium",
                "texture_resolution": "4K (4096x4096)" if self.args.texture_4k else "2K (2048x2048)",
                "format": self.args.format,
                "triangles": self.args.triangles,
                "root": self.args.root,
                "primary_model": primary_file
            }
            task_info_file = self.model_dir / "task_info.json"
            with open(task_info_file, "w") as f:
                json.dump(metadata, f, indent=2)
            log_success(f"Saved metadata to: {task_info_file}")
            if run_log.exists():
                run_log.unlink()
        else:
            run_command(cmd, dry_run=True)

        primary_model = self._find_primary_model()
        if self.args.step == "model":
            log_success(f"3D Model step finished. Model: {primary_model}")
            sys.exit(0)

        return primary_model

    def _find_primary_model(self) -> Path:
        """Finds primary USDZ or other format model in model directory."""
        cands = [
            self.model_dir / f"{self.asset_name}.{self.args.format}",
            self.model_dir / f"base_high_pbr.{self.args.format}",
            self.model_dir / f"base_basic_pbr.{self.args.format}",
        ]
        for c in cands:
            if c.is_file():
                return c
        return cands[0]

    # --------------------------------------------------------------------------
    # Step 3: Pose & Animation
    # --------------------------------------------------------------------------
    def _step_pose(self, model_file: Path):
        if self.asset_type != "character":
            log_info(f"Category is '{self.asset_type.upper()}'. Skeletal pose/rigging step does not apply. Skipping.")
            return

        if self.args.step not in ("all", "pose") or self.args.skip_pose:
            log_info("Skipping character posing and rigging as requested.")
            return

        log_step(3, f"Skeletal Rigging & Animation ({self.args.rig_engine})")
        self.pose_dir.mkdir(parents=True, exist_ok=True)

        if not model_file.is_file() and not self.dry_run:
            log_error(f"Cannot pose character: 3D model not found at '{model_file}'.")
            sys.exit(1)

        if self.args.rig_engine == "mixamo":
            # Ensure Playwright browser cache path is set so pose-binder finds Chromium
            if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ or os.environ["PLAYWRIGHT_BROWSERS_PATH"] == "0":
                if sys.platform == "darwin":
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expanduser("~/Library/Caches/ms-playwright")
                elif sys.platform == "win32":
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")
                else:
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expanduser("~/.cache/ms-playwright")

            pose_bin = find_tool("pose-binder")
            cmd = [
                pose_bin,
                "--input", str(model_file),
                "--output", str(self.pose_dir),
            ]
            if self.args.no_auto_browser:
                cmd.append("--no-auto-browser")
        else:
            rig_bin = find_tool("rig-binder")
            cmd = [
                rig_bin,
                "--model", str(model_file),
                "--output-dir", str(self.pose_dir),
                "--rig-type", self.args.rig_engine,
                "--name", self.asset_name,
            ]

        run_command(cmd, dry_run=self.dry_run)
        log_success(f"Rigging and animation completed in: {self.pose_dir}")


# ==============================================================================
# CLI Parser Setup
# ==============================================================================
def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asset-generator",
        description="Unified Generative 3D Asset Pipeline for Characters and Common Objects (Props, Furniture, Items).",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  # 1. Generate a character from text prompt with 4K textures end-to-end:
  asset-generator "cyberpunk ninja warrior" --type character -o outputs/ninja

  # 2. Generate a common object (table) from reference image:
  asset-generator table_ref.png --type object -o outputs/table

  # 3. Generate a ceramic cup from prompt with Nordic minimalist style:
  asset-generator "ceramic coffee cup" --type object --style-prompt "Nordic minimalist" -o outputs/cup

  # 4. Generate character views only and confirm visually:
  asset-generator hero.png --step views --style anime_style.png

  # 5. List previously created models in Hyper3D account:
  asset-generator --list
        """
    )

    # Positional input
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Input reference image path, existing character name/folder, or descriptive text prompt."
    )

    # Core identification & category
    core_group = parser.add_argument_group("Asset Specification")
    core_group.add_argument(
        "-n", "--name",
        help="Asset identifier / stem name (default: derived from input file or prompt)."
    )
    core_group.add_argument(
        "-t", "--type", "--category",
        dest="type",
        choices=["character", "object", "prop", "furniture", "item"],
        default=None,
        help="Asset category: 'character' (T-pose views + rigging) or 'object' (product views, bottom grounding, no rigging). Auto-detected if omitted."
    )
    core_group.add_argument(
        "--character",
        action="store_const",
        dest="type",
        const="character",
        help="Shortcut to force category as 'character'."
    )
    core_group.add_argument(
        "--object", "--prop",
        action="store_const",
        dest="type",
        const="object",
        help="Shortcut to force category as 'object'."
    )
    core_group.add_argument(
        "-o", "--output-dir",
        help="Output root directory (default: outputs/<name>)."
    )

    # Reference and style inputs
    input_group = parser.add_argument_group("Reference & Style Inputs")
    input_group.add_argument(
        "-i", "--image", "--ref",
        dest="ref_image",
        help="Explicit path to character/object reference image."
    )
    input_group.add_argument(
        "-p", "--prompt",
        help="Text prompt describing the desired asset (used for concept synthesis or guidance)."
    )
    input_group.add_argument(
        "-S", "--style", "--style-image",
        dest="style_image",
        help="Path to style reference image (e.g. anime art, clay render, realistic bronze)."
    )
    input_group.add_argument(
        "--style-prompt",
        help="Additional textual style description (e.g. 'Nordic minimalist, oak wood', 'cel shaded anime')."
    )

    # Pipeline Steps Control
    step_group = parser.add_argument_group("Step Execution & Control")
    step_group.add_argument(
        "--step",
        choices=["all", "views", "model", "pose"],
        default="all",
        help="Execute only a specific pipeline step (default: all)."
    )
    step_group.add_argument(
        "--skip-views",
        action="store_true",
        help="Skip multi-view generation (use existing view images in output directory)."
    )
    step_group.add_argument(
        "--skip-model",
        action="store_true",
        help="Skip 3D model generation (stop after views confirmation)."
    )
    step_group.add_argument(
        "--skip-pose", "--no-pose",
        dest="skip_pose",
        action="store_true",
        help="Skip character rigging and pose animation binding."
    )
    step_group.add_argument(
        "--single-view", "--direct-3d",
        action="store_true",
        help="For objects: skip multi-view generation and generate 3D directly from single reference image/prompt."
    )
    step_group.add_argument(
        "-y", "--yes", "--no-confirm",
        dest="no_confirm",
        action="store_true",
        help="Skip interactive confirmation prompts (auto-confirm multi-views)."
    )
    step_group.add_argument(
        "--force",
        action="store_true",
        help="Force re-generation of assets even if previous results exist."
    )
    step_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview all planned commands and directory steps without invoking APIs."
    )

    # 3D Model Parameters
    model_group = parser.add_argument_group("3D Model Parameters (Hyper3D)")
    model_group.add_argument(
        "-f", "--format",
        choices=["usdz", "glb", "fbx", "obj", "stl"],
        default="usdz",
        help="Output 3D geometry file format (default: usdz)."
    )
    model_group.add_argument(
        "--triangles",
        type=int,
        default=50000,
        help="Target triangle mesh polygon count (default: 50000)."
    )
    model_group.add_argument(
        "--4k", "--texture-4k",
        dest="texture_4k",
        action="store_true",
        default=True,
        help="Generate with 4K packed textures (HighPack 4096x4096, default: enabled)."
    )
    model_group.add_argument(
        "--no-4k",
        dest="texture_4k",
        action="store_false",
        help="Disable 4K textures (use standard 2048x2048 resolution)."
    )
    model_group.add_argument(
        "--root",
        choices=["foot", "bottom", "center"],
        default="foot",
        help="Root placement: 'foot'/'bottom' (min Z=0 at ground plane, default) or 'center'."
    )

    # Rigging & Pose Parameters
    rig_group = parser.add_argument_group("Rigging & Animation Parameters")
    rig_group.add_argument(
        "--rig-engine",
        choices=["mixamo", "humanoid-65", "biped-24", "shadow-puppet"],
        default="mixamo",
        help="Rigging system for characters: 'mixamo' (pose-binder, default) or 'humanoid-65'/'biped-24' (rig-binder)."
    )
    rig_group.add_argument(
        "--anim", "--motion",
        dest="anim",
        help="Target animation clip / action name (for pose-binder or rig-binder)."
    )
    rig_group.add_argument(
        "--no-auto-browser",
        action="store_true",
        help="Disable automatic headful browser for Mixamo character rigging."
    )

    # Specialized options
    views_group = parser.add_argument_group("Multi-View Details")
    views_group.add_argument(
        "--views-prompt",
        help="Override or append custom prompt for multi-view generation."
    )
    views_group.add_argument(
        "--is-front-view",
        action="store_true",
        help="Input image is already a canonical front view (skips Phase 1 front normalization)."
    )

    # Utility actions
    util_group = parser.add_argument_group("Account & Utility Actions")
    util_group.add_argument(
        "--list", "--history",
        dest="list_tasks",
        action="store_true",
        help="List created 3D models and tasks in Hyper3D account."
    )
    util_group.add_argument(
        "--page",
        type=int,
        default=1,
        help="Page number for --list (default: 1)."
    )
    util_group.add_argument(
        "--download",
        metavar="TASK_UUID",
        help="Download generated result files for an existing task UUID."
    )
    util_group.add_argument(
        "--balance",
        action="store_true",
        help="Check remaining credits in Hyper3D account."
    )
    util_group.add_argument(
        "--api-key",
        help="Hyper3D API key (defaults to HYPER3D_API_KEY environment variable)."
    )
    util_group.add_argument(
        "--gemini-key",
        help="Gemini API key (defaults to GEMINI_API_KEY environment variable)."
    )

    return parser


def main():
    parser = create_argument_parser()
    args = parser.parse_args()

    # Handle Utility Actions
    api_key = args.api_key or DEFAULT_HYPER3D_KEY
    if args.list_tasks or args.balance:
        if not api_key:
            log_error("HYPER3D_API_KEY (or RODIN_API_KEY) is not set. Please export HYPER3D_API_KEY=<your_api_key> (or pass --api-key).")
            sys.exit(1)
        query_task_list(api_key, page=args.page)
        sys.exit(0)

    if args.download:
        out_dir = Path(args.output_dir or f"outputs/{args.download}")
        out_dir.mkdir(parents=True, exist_ok=True)
        model_creator_bin = find_tool("model-creator")
        if not model_creator_bin:
            log_error("model-creator executable not found.")
            sys.exit(1)
        cmd = [model_creator_bin, "--download", args.download, "-f", args.format, "-o", str(out_dir)]
        run_command(cmd, dry_run=args.dry_run)
        sys.exit(0)

    # Ensure input or prompt is given
    if not args.input and not args.prompt and not args.ref_image:
        parser.print_help()
        print(f"\n{RED}Error: Please specify an input reference image or prompt description.{RESET}", file=sys.stderr)
        sys.exit(1)

    pipeline = AssetPipeline(args)
    pipeline.run()


if __name__ == "__main__":
    main()
