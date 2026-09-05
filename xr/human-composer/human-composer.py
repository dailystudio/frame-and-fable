#!/usr/bin/env python3
"""
Human Composer CLI tool.
Binds accessories and hair models with human body models in USDZ format.
"""

import sys
import os
import argparse
import subprocess
import shutil
import json
import tempfile
import zipfile

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

        # Check for duplicate base names in textures
        base_names = [os.path.basename(t) for t in textures]
        if len(base_names) != len(set(base_names)):
            return False, f"Duplicate texture filenames found: {base_names}"

    return True, f"Valid USDZ with {len(textures)} textures: {base_names}"


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

    output_path = args.output
    if not output_path:
        body_stem = os.path.splitext(os.path.basename(args.body))[0]
        output_path = f"{body_stem}_bound.usdz"
    output_path = os.path.abspath(output_path)

    print(f"[Human Composer] Blender: {blender_bin}")
    print(f"[Human Composer] Body: {args.body}")
    print(f"[Human Composer] Hair: {args.hair}")
    print(f"[Human Composer] Output: {output_path}")

    # Analyze reference images if provided
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
        print("[Human Composer] No reference images provided or found. Using geometric scalp alignment.")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    blender_script = os.path.join(script_dir, "core", "blender_binder.py")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        config = {
            "body": os.path.abspath(args.body),
            "hair": os.path.abspath(args.hair),
            "output": output_path,
            "preview_dir": os.path.abspath(args.preview_dir) if args.preview_dir else None,
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
        res = subprocess.run(cmd, check=True)

        # Verify output archive
        valid, msg = verify_usdz_integrity(output_path)
        if not valid:
            print(f"[Error] Output verification failed: {msg}", file=sys.stderr)
            sys.exit(1)

        print(f"[Human Composer] Successfully bound hair to body! Result saved to:")
        print(f"  -> {output_path}")
        print(f"  -> {msg}")

        if args.preview_dir and os.path.exists(args.preview_dir):
            previews = [f for f in os.listdir(args.preview_dir) if f.endswith(".png")]
            print(f"[Human Composer] Previews generated ({len(previews)} images in {args.preview_dir}):")
            for p in sorted(previews):
                print(f"  - {p}")

    except subprocess.CalledProcessError as e:
        print(f"[Error] Blender execution failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(e.returncode)
    finally:
        if os.path.exists(config_path):
            os.remove(config_path)


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
        "--output", default=None, help="Path to output bound USDZ file."
    )
    bind_parser.add_argument(
        "--blender", default=None, help="Path to Blender executable."
    )
    bind_parser.add_argument(
        "--preview-dir", default=None, help="Directory to save rendered multi-angle preview images."
    )

    args = parser.parse_args()
    if args.command == "bind":
        handle_bind(args)


if __name__ == "__main__":
    main()
