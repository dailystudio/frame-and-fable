#!/usr/bin/env python3
"""
Rig Binder (rig-binder) - Universal 3D/2D Mesh Rigging & Skinning CLI
=====================================================================
Automates skeletal generation, proportional landmark fitting, bone skinning/weighting,
animation routines, and multi-format export for 3D character models across multiple
rigging specifications:
  - Chinese Shadow Play 19-Joint 2D Planar Rig (`shadow-puppet` / `shadow-19`)
  - Standard 65-Joint 3D Mocap Humanoid Skeleton (`humanoid-65` / `humanoid`)
  - Game-Ready 24-Joint Biped Rig (`biped-24` / `biped`)
  - Custom User-Defined Rig Specification (`--custom-rig <path.json>`)

Usage Examples:
    # 1. Rig standard humanoid model (default 65-joint 3D mocap rig with full fingers/toes)
    python3 rig_binder.py --model samples/base_basic_shaded.usdz

    # 2. Rig shadow puppet model (19-joint 2D planar rig + shadow play routine)
    python3 rig_binder.py --model samples/base_basic_shaded.usdz --rig-type shadow-puppet

    # 3. Rig model with custom JSON specification
    python3 rig_binder.py --model character.glb --custom-rig presets/custom_template.json

    # 4. Export only USDZ and GLB without animation
    python3 rig_binder.py --model character.fbx --formats usdz,glb --no-anim
"""

import argparse
import os
import shutil
import subprocess
import sys


PRESET_MAP = {
    # 19-joint 2D Planar Shadow Play
    "shadow-puppet": "shadow_puppet_19.json",
    "shadow_puppet": "shadow_puppet_19.json",
    "shadow-19": "shadow_puppet_19.json",
    "shadowplay": "shadow_puppet_19.json",
    "19": "shadow_puppet_19.json",

    # 65-joint 3D Full Humanoid
    "humanoid-65": "humanoid_65.json",
    "humanoid_65": "humanoid_65.json",
    "humanoid": "humanoid_65.json",
    "standard-65": "humanoid_65.json",
    "standard": "humanoid_65.json",
    "mixamo": "humanoid_65.json",
    "65": "humanoid_65.json",

    # 24-joint Standard Game Biped
    "biped-24": "biped_24.json",
    "biped_24": "biped_24.json",
    "biped": "biped_24.json",
    "game": "biped_24.json",
    "24": "biped_24.json",
}


def find_blender(custom_path=None):
    """Locate Blender executable across platform standard locations."""
    if custom_path and os.path.exists(custom_path):
        return custom_path

    which_blender = shutil.which("blender")
    if which_blender:
        return which_blender

    macos_candidates = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender"),
        "/Applications/Blender 4.4.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.3.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.2.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.1.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.0.app/Contents/MacOS/Blender",
    ]
    for p in macos_candidates:
        if os.path.exists(p):
            return p

    linux_candidates = [
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "/snap/bin/blender",
        os.path.expanduser("~/.local/bin/blender"),
    ]
    for p in linux_candidates:
        if os.path.exists(p):
            return p

    if sys.platform == "win32":
        for ver in ["Blender 4.4", "Blender 4.3", "Blender 4.2", "Blender 4.1", "Blender 4.0", "Blender 3.6"]:
            p = os.path.join(
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                "Blender Foundation", ver, "blender.exe"
            )
            if os.path.exists(p):
                return p

    return None


def resolve_rig_config(rig_type, custom_rig_path, script_dir):
    """Resolves rig configuration JSON path from preset name or custom path."""
    if custom_rig_path:
        custom_path = os.path.abspath(custom_rig_path)
        if not os.path.exists(custom_path):
            raise FileNotFoundError(f"Custom rig JSON configuration not found at: {custom_path}")
        return custom_path

    key = rig_type.strip().lower()
    if key in PRESET_MAP:
        preset_file = PRESET_MAP[key]
        preset_path = os.path.join(script_dir, "presets", preset_file)
        if os.path.exists(preset_path):
            return preset_path
        raise FileNotFoundError(f"Built-in preset file missing: {preset_path}")

    # Check if rig_type was given directly as a path
    if os.path.exists(rig_type):
        return os.path.abspath(rig_type)

    valid_keys = ", ".join(sorted(set(PRESET_MAP.keys())))
    raise ValueError(f"Unknown rig preset '{rig_type}'. Available presets: {valid_keys} or specify --custom-rig <path.json>")


def main():
    parser = argparse.ArgumentParser(
        description="Rig Binder (rig-binder): Universal 3D/2D Mesh Rigging, Skinning, and Animation Pipeline"
    )
    parser.add_argument(
        "--model", "-m",
        required=True,
        help="Path to input 3D model file (.usdz, .glb, .gltf, .fbx, .obj)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="outputs",
        help="Output directory for generated files (default: outputs/)"
    )
    parser.add_argument(
        "--name", "-n",
        default=None,
        help="Base name for outputs (default: derived from input file name)"
    )
    parser.add_argument(
        "--rig-type", "-r",
        default="humanoid-65",
        help="Rig preset to apply: 'humanoid-65' (65 joints standard humanoid 3D), 'shadow-puppet' (19 joints, 2D planar), 'biped-24' (24 joints game biped). Default: humanoid-65"
    )
    parser.add_argument(
        "--custom-rig", "-c",
        default=None,
        help="Path to custom user-defined rig configuration JSON file"
    )
    parser.add_argument(
        "--formats", "-f",
        default="usdz,glb,blend",
        help="Comma-separated list of export formats (supported: usdz, glb, blend, fbx. default: usdz,glb,blend)"
    )
    parser.add_argument(
        "--no-anim",
        action="store_true",
        help="Generate only pure rigged model without animation routine"
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Disable generating PNG contact sheet and MP4 preview video"
    )
    parser.add_argument(
        "--blender-path",
        default=None,
        help="Custom path to Blender executable binary"
    )

    args = parser.parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Locate Blender
    blender_bin = find_blender(args.blender_path)
    if not blender_bin:
        print("[ERROR] Blender executable not found! Please install Blender 4.x or specify --blender-path.")
        sys.exit(1)
    print(f"[*] Located Blender binary: {blender_bin}")

    # 2. Resolve Input Model
    input_path = args.model
    if not os.path.isabs(input_path):
        input_path = os.path.abspath(input_path)

    if not os.path.exists(input_path):
        print(f"[ERROR] Input model file not found: {input_path}")
        sys.exit(1)

    # 3. Resolve Output Directory & Name
    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    base_name = args.name
    if not base_name:
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        # Clean name
        base_name = base_name.replace(" ", "_").lower()

    # 4. Resolve Rig Configuration
    try:
        rig_config_path = resolve_rig_config(args.rig_type, args.custom_rig, script_dir)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    print(f"[*] Using Rig Configuration: {rig_config_path}")

    # 5. Execute Backend Engine
    engine_script = os.path.join(script_dir, "rig_engine.py")
    if not os.path.exists(engine_script):
        print(f"[ERROR] Backend engine script not found: {engine_script}")
        sys.exit(1)

    cmd = [
        blender_bin,
        "--background",
        "--python", engine_script,
        "--",
        "--input", input_path,
        "--output-dir", out_dir,
        "--name", base_name,
        "--rig-config", rig_config_path,
        "--formats", args.formats
    ]
    if args.no_anim:
        cmd.append("--no-anim")
    if args.no_preview:
        cmd.append("--no-preview")

    print(f"[*] Executing Rig Binder pipeline on '{input_path}'...")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n" + "=" * 60)
        print(" [SUCCESS] RIG BINDER PIPELINE FINISHED SUCCESSFULLY!")
        print("=" * 60)
        formats = [fmt.strip().lower() for fmt in args.formats.split(",") if fmt.strip()]
        print(f" 1. Pure Rigged Model (Rest Pose):")
        for fmt in formats:
            print(f"    - {os.path.join(out_dir, f'{base_name}_rigged.{fmt}')}")

        if not args.no_anim:
            print(f" 2. Animated Model (Routine Included):")
            for fmt in formats:
                print(f"    - {os.path.join(out_dir, f'{base_name}_animated.{fmt}')}")

            if not args.no_preview:
                print(f" 3. Visual Previews:")
                print(f"    - Contact Sheet: {os.path.join(out_dir, f'{base_name}_preview_grid.png')}")
                print(f"    - Video Preview: {os.path.join(out_dir, f'{base_name}_preview_anim.mp4')}")
        print("=" * 60)
    else:
        print(f"\n[FAILED] Pipeline exited with code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
