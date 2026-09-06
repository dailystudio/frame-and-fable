#!/usr/bin/env python3
"""
Human Composer CLI tool.
Binds accessories and hair models with human body models in USDZ format,
generating bound models, static previews, MP4 turntable animations,
and intermediate comparison images.
"""

import sys
import os
import argparse
import subprocess
import shutil
import json
import tempfile
import zipfile
from PIL import Image, ImageDraw

from core.ref_analyzer import analyze_all_references


def find_blender(custom_path=None):
    """Locate Blender executable."""
    if custom_path and os.path.isfile(custom_path) and os.access(custom_path, os.X_OK):
        return custom_path

    env_path = os.environ.get("BLENDER_PATH")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return env_path

    mac_app = "/Applications/Blender.app/Contents/MacOS/Blender"
    if os.path.isfile(mac_app) and os.access(mac_app, os.X_OK):
        return mac_app

    which_blender = shutil.which("blender")
    if which_blender:
        return which_blender

    return None


def derive_model_name(body_path, custom_name=None):
    """Derive clean model name from body filename."""
    if custom_name:
        return custom_name
    stem = os.path.splitext(os.path.basename(body_path))[0]
    # Remove common suffixes like _anim_base, _base
    for suffix in ["_anim_base", "_base"]:
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    return stem


def verify_usdz_integrity(usdz_path):
    """Inspect exported USDZ archive to verify files and distinct textures."""
    if not os.path.exists(usdz_path):
        return False, "File does not exist."

    with zipfile.ZipFile(usdz_path, "r") as z:
        names = z.namelist()
        has_usdc = any(n.endswith((".usdc", ".usd", ".usda")) for n in names)
        textures = [n for n in names if n.lower().endswith((".png", ".jpg", ".jpeg", ".hdr"))]

        if not has_usdc:
            return False, "USDZ archive does not contain a USD scene file."

        base_names = [os.path.basename(t) for t in textures]
        if len(base_names) != len(set(base_names)):
            return False, f"Duplicate texture filenames found: {base_names}"

    return True, f"Valid USDZ with {len(textures)} textures: {base_names}"


def create_side_by_side_comparison(ref_path, render_path, output_path, view_name):
    """Generate a clean side-by-side comparison between reference and 3D render."""
    if not os.path.exists(ref_path) or not os.path.exists(render_path):
        return

    ref_img = Image.open(ref_path).convert("RGB")
    ren_img = Image.open(render_path).convert("RGB")

    target_h = 1024
    ref_w = int(ref_img.width * target_h / ref_img.height)
    ren_w = int(ren_img.width * target_h / ren_img.height)

    ref_resized = ref_img.resize((ref_w, target_h), Image.Resampling.LANCZOS)
    ren_resized = ren_img.resize((ren_w, target_h), Image.Resampling.LANCZOS)

    header_h = 40
    margin = 8
    total_w = ref_w + ren_w + margin
    total_h = target_h + header_h

    comp = Image.new("RGB", (total_w, total_h), (245, 245, 245))
    comp.paste(ref_resized, (0, header_h))
    comp.paste(ren_resized, (ref_w + margin, header_h))

    draw = ImageDraw.Draw(comp)
    draw.text((20, 12), f"Reference Image ({view_name.capitalize()})", fill=(40, 40, 40))
    draw.text((ref_w + margin + 20, 12), f"3D Bound Model ({view_name.capitalize()})", fill=(40, 40, 40))

    comp.save(output_path)


def generate_all_comparisons(intermediate_dir, ref_map):
    """Generate side-by-side comparisons for all available reference views."""
    comparison_files = []
    for view_name, ref_path in ref_map.items():
        if not ref_path or not os.path.exists(ref_path):
            continue
        render_path = os.path.join(intermediate_dir, f"render_{view_name}.png")
        if os.path.exists(render_path):
            comp_path = os.path.join(intermediate_dir, f"comparison_{view_name}.png")
            create_side_by_side_comparison(ref_path, render_path, comp_path, view_name)
            comparison_files.append(comp_path)
    return comparison_files


def handle_bind(args):
    blender_bin = find_blender(args.blender)
    if not blender_bin:
        print("[Error] Blender executable not found.", file=sys.stderr)
        print("Please install Blender or pass --blender /path/to/blender.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.body):
        print(f"[Error] Body model not found: {args.body}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.hair):
        print(f"[Error] Hair model not found: {args.hair}", file=sys.stderr)
        sys.exit(1)

    model_name = derive_model_name(args.body, args.name)

    # Determine destination directory
    if args.output:
        if args.output.endswith(".usdz"):
            output_usdz = os.path.abspath(args.output)
            model_dir = os.path.dirname(output_usdz)
        else:
            model_dir = os.path.abspath(args.output)
            output_usdz = os.path.join(model_dir, f"{model_name}_bound.usdz")
    else:
        root_outputs = os.path.abspath(args.output_dir)
        model_dir = os.path.join(root_outputs, model_name)
        output_usdz = os.path.join(model_dir, f"{model_name}_bound.usdz")

    os.makedirs(model_dir, exist_ok=True)

    # Optional preview outputs
    generate_preview = args.preview
    generate_preview_anim = args.preview_anim or bool(args.anim)

    preview_img_path = os.path.join(model_dir, "preview.png") if generate_preview else None
    preview_vid_path = os.path.join(model_dir, "preview_animation.mp4") if generate_preview_anim else None

    # Intermediate handling
    is_intermediate = args.intermediate
    intermediate_dir = os.path.join(model_dir, "intermediates") if is_intermediate else None
    if intermediate_dir:
        os.makedirs(intermediate_dir, exist_ok=True)

    print(f"[Human Composer] Blender: {blender_bin}")
    print(f"[Human Composer] Body: {args.body}")
    print(f"[Human Composer] Hair: {args.hair}")
    print(f"[Human Composer] Model Directory: {model_dir}")
    print(f"[Human Composer] Target USDZ: {output_usdz}")
    if preview_img_path:
        print(f"[Human Composer] Static Preview: {preview_img_path}")
    if preview_vid_path:
        print(f"[Human Composer] Preview Animation: {preview_vid_path}")
    if is_intermediate:
        print(f"[Human Composer] Intermediates Directory: {intermediate_dir}")

    # Analyze reference images
    ref_map = {
        "front": args.ref_front,
        "left": args.ref_left,
        "right": args.ref_right,
        "back": args.ref_back,
    }
    ref_data = analyze_all_references(
        ref_front=args.ref_front,
        ref_left=args.ref_left,
        ref_right=args.ref_right,
        ref_back=args.ref_back,
    )
    if ref_data:
        print(f"[Human Composer] Analyzed reference views: {list(ref_data.keys())}")
        for v, d in ref_data.items():
            print(f"  - {v}: head width={d['head_width']}px, center={d['head_x_center']:.1f}px")
    else:
        print("[Human Composer] No reference images provided. Using geometric scalp alignment.")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    blender_script = os.path.join(script_dir, "core", "blender_binder.py")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        config = {
            "body": os.path.abspath(args.body),
            "hair": os.path.abspath(args.hair),
            "anim": os.path.abspath(args.anim) if args.anim else None,
            "output_usdz": output_usdz,
            "preview_image_path": preview_img_path,
            "preview_video_path": preview_vid_path,
            "intermediate_dir": intermediate_dir,
            "render_intermediate": is_intermediate,
            "ref_data": ref_data,
        }
        json.dump(config, f, indent=2)
        config_path = f.name

    try:
        cmd = [
            blender_bin,
            "-b",
            "-P",
            blender_script,
            "--",
            "--config",
            config_path,
        ]
        print("[Human Composer] Running Blender binding process...")
        subprocess.run(cmd, check=True)

        # Verify output archive
        valid, msg = verify_usdz_integrity(output_usdz)
        if not valid:
            print(f"[Error] Output verification failed: {msg}", file=sys.stderr)
            sys.exit(1)

        # Generate comparison images if intermediate requested
        if is_intermediate and ref_data:
            comp_files = generate_all_comparisons(intermediate_dir, ref_map)
            print(f"[Human Composer] Generated {len(comp_files)} side-by-side comparison files.")

        print("\n========================================================")
        print("  [Human Composer] Binding Pipeline Completed!")
        print("========================================================")
        print(f"  Model Output Directory: {model_dir}")
        print(f"  -> Bound Model (USDZ) : {output_usdz}")
        if preview_img_path:
            print(f"  -> Static Preview     : {preview_img_path}")
        if preview_vid_path:
            print(f"  -> Animation (MP4)    : {preview_vid_path}")
        if is_intermediate:
            inter_items = os.listdir(intermediate_dir)
            print(f"  -> Intermediates ({len(inter_items)} files): {intermediate_dir}")
            for item in sorted(inter_items):
                print(f"     * {item}")
        print("========================================================\n")

    except subprocess.CalledProcessError as e:
        print(f"[Error] Blender execution failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(e.returncode)
    finally:
        if os.path.exists(config_path):
            os.remove(config_path)


def handle_info(args):
    model_path = args.model or args.model_opt
    if not model_path:
        print("[Error] Please specify the path to a 3D model: python human-composer.py info <model.usdz>", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(model_path):
        print(f"[Error] Model file not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    blender_bin = find_blender(args.blender)
    if not blender_bin:
        print("[Error] Blender executable not found. Please install Blender or pass --blender.", file=sys.stderr)
        sys.exit(1)

    from core.model_inspector import inspect_model, format_model_info

    try:
        data = inspect_model(model_path, blender_bin)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(format_model_info(data, selected_part=args.part))
    except Exception as e:
        print(f"[Error] Failed to inspect model: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Human Composer: 3D human composition and accessory binding tool."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: bind
    bind_parser = subparsers.add_parser(
        "bind", help="Bind a hair model to a human body model with alignment."
    )
    bind_parser.add_argument(
        "--body", required=True, help="Path to input body USDZ model."
    )
    bind_parser.add_argument(
        "--hair", required=True, help="Path to input hair USDZ model."
    )
    bind_parser.add_argument(
        "--ref-front", default=None, help="Path to front reference image."
    )
    bind_parser.add_argument(
        "--ref-left", default=None, help="Path to left reference image."
    )
    bind_parser.add_argument(
        "--ref-right", default=None, help="Path to right reference image."
    )
    bind_parser.add_argument(
        "--ref-back", default=None, help="Path to back reference image."
    )
    bind_parser.add_argument(
        "--output-dir", default="outputs", help="Root outputs directory (default: 'outputs')."
    )
    bind_parser.add_argument(
        "--output", default=None, help="Explicit output USDZ path or directory."
    )
    bind_parser.add_argument(
        "--name", default=None, help="Model name for subdir (default: inferred from body filename)."
    )
    bind_parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate a high-resolution static preview image (preview.png)."
    )
    bind_parser.add_argument(
        "--preview-anim",
        action="store_true",
        help="Generate a sequenced preview showcase animation video (preview_animation.mp4)."
    )
    bind_parser.add_argument(
        "--intermediate",
        action="store_true",
        help="Also output all intermediate multi-angle renders and reference comparison images."
    )
    bind_parser.add_argument(
        "--anim", default=None, help="Path to optional skeletal animation file (USDZ/USDC) to showcase in preview MP4."
    )
    bind_parser.add_argument(
        "--blender", default=None, help="Path to Blender executable."
    )

    # Subcommand: info
    info_parser = subparsers.add_parser(
        "info", help="Inspect and list 3D model information (parts, bounding box, vertices, textures, skeleton)."
    )
    info_parser.add_argument(
        "model", nargs="?", default=None, help="Path to 3D model (USDZ, USDC, OBJ, etc.)."
    )
    info_parser.add_argument(
        "--model", dest="model_opt", default=None, help="Path to 3D model (alternative to positional argument)."
    )
    info_parser.add_argument(
        "--part", default=None, help="Specific part/mesh name, material name, or index to inspect."
    )
    info_parser.add_argument(
        "--json", action="store_true", help="Output information in raw JSON format."
    )
    info_parser.add_argument(
        "--blender", default=None, help="Path to custom Blender executable."
    )

    args = parser.parse_args()
    if args.command == "bind":
        handle_bind(args)
    elif args.command == "info":
        handle_info(args)


if __name__ == "__main__":
    main()
