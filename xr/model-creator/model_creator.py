#!/usr/bin/env python3
"""
Model Creator CLI.
Generates 3D assets from text prompts or reference images across multiple providers (Hyper3D, etc.).
"""

import sys
import os
import argparse
import json
import time
from pathlib import Path
from typing import Optional, List

# Ensure package modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.factory import get_provider, list_providers
from core.models import TaskStatus
from core.recenter import recenter_model_to_foot
from core.exceptions import (
    ModelCreatorError,
    AuthenticationError,
    InsufficientCreditsError,
    RateLimitError,
    InvalidRequestError,
    TaskFailedError,
    TaskTimeoutError,
)


def parse_key_value_pairs(pairs: Optional[List[str]]) -> dict:
    """Parse a list of KEY=VALUE strings into a dictionary with typed values."""
    res = {}
    if not pairs:
        return res
    for p in pairs:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = k.strip()
        v = v.strip()
        # Parse booleans and numbers
        if v.lower() == "true":
            res[k] = True
        elif v.lower() == "false":
            res[k] = False
        else:
            try:
                res[k] = int(v)
            except ValueError:
                try:
                    res[k] = float(v)
                except ValueError:
                    res[k] = v
    return res


def print_status_update(status: TaskStatus, elapsed: float):
    """Callback to print live status while polling."""
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    time_str = f"[{mins:02d}:{secs:02d}]"
    print(f"\r{time_str} Status: {status.summary}...", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="3D Model Creator - Generate 3D models from text or images using Hyper3D and other providers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Provider & Auth
    parser.add_argument(
        "--provider",
        default="hyper3d",
        help=f"Provider name (default: hyper3d). Available: {', '.join(list_providers()) or 'hyper3d'}",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="API Key for the provider. Can also be set via HYPER3D_API_KEY or RODIN_API_KEY env vars.",
    )

    # Input modes
    input_group = parser.add_argument_group("Input Options")
    input_group.add_argument(
        "-p", "--prompt",
        type=str,
        help="Text prompt description for Text-to-3D (or guidance prompt for Image-to-3D).",
    )
    input_group.add_argument(
        "-i", "--images",
        nargs="+",
        help="One or more reference image paths (1-5 images) for Image-to-3D.",
    )
    input_group.add_argument(
        "--image-labels",
        nargs="+",
        help="Viewing direction labels for images (e.g. F B L R).",
    )
    input_group.add_argument(
        "--no-optimize-images",
        action="store_true",
        help="Disable automatic client-side image optimization (resizing huge 4K images to 2048 and compressing).",
    )
    input_group.add_argument(
        "--max-image-dimension",
        type=int,
        default=2048,
        help="Max resolution dimension for uploaded images (default: 2048).",
    )
    input_group.add_argument(
        "--upload-timeout",
        type=int,
        default=300,
        help="Timeout in seconds for uploading images (default: 300s).",
    )

    # Output & formats
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "-o", "--output-dir",
        default="./outputs",
        help="Target output directory for downloaded 3D assets (default: ./outputs).",
    )
    output_group.add_argument(
        "-f", "--format", "--download-type",
        dest="format",
        default="glb",
        help="Output 3D geometry format / download type: glb, usdz, fbx, obj, stl (default: glb).",
    )

    # Provider-specific generation parameters
    gen_group = parser.add_argument_group("Generation Parameters")
    gen_group.add_argument(
        "--triangles", "--mesh-complexity", "--faces",
        dest="triangles",
        type=int,
        default=None,
        help="Target mesh complexity in triangles (e.g. 5000, 10000, 50000, 100000). Directly sets face count in Raw mode. Valid range: 500 - 2,000,000.",
    )
    gen_group.add_argument(
        "--tier",
        default="Gen-2.5-Medium",
        help="Generation tier (e.g. Gen-2.5-Medium, Gen-2.5-High, Gen-2.5-Extreme-High, Gen-2.5-Low, Gen-2.5-Extreme-Low). Default: Gen-2.5-Medium.",
    )
    gen_group.add_argument(
        "--mesh-mode",
        choices=["Raw", "Quad"],
        default=None,
        help="Mesh topology: 'Raw' (triangles) or 'Quad' (quads). Defaults to 'Raw' for triangle targets.",
    )
    gen_group.add_argument(
        "--quality",
        choices=["high", "medium", "low", "extra-low"],
        default="medium",
        help="Target face count quality preset (default: medium).",
    )
    gen_group.add_argument(
        "--quality-override",
        type=int,
        default=None,
        help="Custom target face count (500 - 2000000), overrides --quality.",
    )
    gen_group.add_argument(
        "--texture-mode",
        choices=["legacy", "minimum", "extreme-low", "low", "medium", "high", "extreme-high"],
        default=None,
        help="Texture effort level.",
    )
    gen_group.add_argument(
        "--material",
        choices=["PBR", "Shaded", "All", "Hybrid", "None"],
        default="PBR",
        help="Material type (default: PBR).",
    )
    gen_group.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for generation reproducible results (0-65535).",
    )
    gen_group.add_argument(
        "--ta-pose",
        action="store_true",
        help="Generate humanoid models in T/A-pose suitable for rigging.",
    )
    gen_group.add_argument(
        "--preview-render",
        action="store_true",
        help="Generate and download an additional high-quality preview render image.",
    )
    gen_group.add_argument(
        "--symmetry",
        choices=["symmetric", "balanced", "asymmetric", "unknown"],
        default=None,
        help="Symmetry setting for geometry generation.",
    )
    gen_group.add_argument(
        "--instruct-mode",
        choices=["creative", "faithful"],
        default=None,
        help="Geometry strategy: 'creative' or 'faithful'.",
    )
    gen_group.add_argument(
        "--root", "--origin",
        dest="root",
        choices=["center", "foot", "bottom"],
        default="center",
        help="Root/pivot placement: 'center' (default) or 'foot'/'bottom' (ground plane min Z/Y=0 at feet).",
    )
    gen_group.add_argument(
        "--root-at-foot", "--foot-origin",
        dest="root_at_foot",
        action="store_true",
        help="Position root/pivot at the character's feet (ground plane min Z/Y=0) instead of model center.",
    )
    gen_group.add_argument(
        "--addons",
        nargs="+",
        help="Optional addons (e.g. HighPack for 4K textures).",
    )
    gen_group.add_argument(
        "--param",
        action="append",
        metavar="KEY=VALUE",
        help="Pass additional provider-specific parameters as KEY=VALUE.",
    )

    # Operational actions
    action_group = parser.add_argument_group("Actions & Execution")
    action_group.add_argument(
        "--recenter",
        metavar="FILE",
        help="Recenter an existing 3D model file so its root origin is at the character's feet (ground plane min Z/Y=0).",
    )
    action_group.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit generation task asynchronously and exit without waiting for completion.",
    )
    action_group.add_argument(
        "--timeout",
        type=float,
        default=1200.0,
        help="Maximum polling duration in seconds before timing out (default: 1200s / 20 mins).",
    )
    action_group.add_argument(
        "--status",
        metavar="SUBSCRIPTION_KEY",
        help="Query status of an in-progress task using its subscription key.",
    )
    action_group.add_argument(
        "--download",
        metavar="TASK_UUID",
        help="Download generated result files for a completed task using its task UUID.",
    )
    action_group.add_argument(
        "--balance",
        action="store_true",
        help="Check remaining credits/balance for the selected provider.",
    )
    action_group.add_argument(
        "--list", "--history",
        dest="list_tasks",
        action="store_true",
        help="List created models and generation tasks from account history.",
    )
    action_group.add_argument(
        "--page",
        type=int,
        default=1,
        help="Page number when querying task history/list (default: 1).",
    )

    args = parser.parse_args()

    # Handle Standalone Recenter Action
    if args.recenter:
        try:
            target_p = Path(args.recenter).resolve()
            out_p = Path(args.output_dir) / target_p.name if args.output_dir and args.output_dir != "./outputs" else None
            res_path = recenter_model_to_foot(target_p, out_p)
            print(f"Model successfully recentered to foot: {res_path}")
            sys.exit(0)
        except Exception as e:
            print(f"Error recentering model: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        provider = get_provider(name=args.provider, api_key=args.api_key)
    except Exception as e:
        print(f"Error initializing provider '{args.provider}': {e}", file=sys.stderr)
        sys.exit(1)

    # Handle Balance Action
    if args.balance:
        try:
            print(f"Checking balance for provider '{provider.provider_name}'...")
            bal = provider.check_balance()
            print(json.dumps(bal, indent=2))
            sys.exit(0)
        except Exception as e:
            print(f"Error checking balance: {e}", file=sys.stderr)
            sys.exit(1)

    # Handle List Tasks Action
    if args.list_tasks:
        try:
            print(f"Fetching task history for provider '{provider.provider_name}' (page {args.page})...")
            res = provider.check_balance(usage_page=args.page)
            usage_list = res.get("usage", [])
            bal = res.get("balance")
            if bal is not None:
                print(f"Remaining Credits: {bal}\n")
            if not usage_list:
                print(f"No generation tasks found on page {args.page}.")
            else:
                print(f"{'#':<4} {'Task UUID':<38} {'Time (UTC)':<22} {'Item / Tier':<30} {'Credits':<8}")
                print("-" * 105)
                for idx, item in enumerate(usage_list, start=1):
                    uuid = item.get("task_uuid", "N/A")
                    t_str = item.get("time", "")[:19].replace("T", " ")
                    item_name = item.get("item", "")
                    amt = item.get("amount", "")
                    print(f"{idx:<4} {uuid:<38} {t_str:<22} {item_name:<30} {amt:<8}")
                print("-" * 105)
                print("\nTo download any model by task UUID:")
                print(f"  model-creator --download <TASK_UUID> -o {args.output_dir}")
            sys.exit(0)
        except Exception as e:
            print(f"Error fetching task list: {e}", file=sys.stderr)
            sys.exit(1)

    # Handle Status Query Action
    if args.status:
        try:
            print(f"Checking status for subscription key: {args.status}...")
            st = provider.get_task_status(args.status)
            print(f"Summary: {st.summary}")
            print(f"Done: {st.is_done}, Failed: {st.is_failed}, Pending: {st.is_pending}")
            if st.jobs:
                print("Jobs:")
                for j in st.jobs:
                    q_str = f" (queue: {j.queue_length})" if j.queue_length is not None else ""
                    print(f"  - [{j.status}] {j.uuid}{q_str}")
            sys.exit(0)
        except Exception as e:
            print(f"Error querying status: {e}", file=sys.stderr)
            sys.exit(1)

    # Handle Direct Download Action
    if args.download:
        try:
            out_dir = Path(args.output_dir) / args.download
            file_filter = None
            if args.format and args.format.lower() not in ("all", "*"):
                file_filter = [args.format]
            print(f"Downloading results for task {args.download} into {out_dir}...")
            files = provider.download_results(args.download, out_dir, file_types=file_filter)
            if (args.root in ("foot", "bottom") or args.root_at_foot) and files:
                for f in files:
                    if f.suffix.lower() in (".usdz", ".usdc", ".usda", ".glb", ".gltf", ".fbx", ".obj", ".stl"):
                        recenter_model_to_foot(f)
            print(f"\nDownloaded {len(files)} files:")
            for f in files:
                print(f"  - {f}")
            sys.exit(0)
        except Exception as e:
            print(f"Error downloading results: {e}", file=sys.stderr)
            sys.exit(1)

    # Must provide either prompt or images
    if not args.prompt and not args.images:
        parser.print_help()
        print("\nError: Please specify either --prompt (for Text-to-3D) or --images (for Image-to-3D).", file=sys.stderr)
        sys.exit(1)

    # Normalize format (supports typo 'udsz' -> 'usdz')
    norm_format = args.format.lower().lstrip(".")
    if norm_format == "udsz":
        norm_format = "usdz"

    # Assemble extra params
    extra_params = parse_key_value_pairs(args.param)
    if args.quality_override is not None:
        extra_params["quality_override"] = args.quality_override
    if args.addons:
        extra_params["addons"] = args.addons
    if args.image_labels:
        extra_params["image_label"] = args.image_labels

    common_gen_kwargs = {
        "tier": args.tier,
        "geometry_file_format": norm_format,
        "mesh_mode": args.mesh_mode,
        "quality": args.quality,
        "triangles": args.triangles,
        "texture_mode": args.texture_mode,
        "material": args.material,
        "seed": args.seed,
        "ta_pose": args.ta_pose,
        "preview_render": args.preview_render,
        "is_symmetric": args.symmetry,
        "geometry_instruct_mode": args.instruct_mode,
        "optimize_images": not args.no_optimize_images,
        "max_image_dimension": args.max_image_dimension,
        "upload_timeout": args.upload_timeout,
        **extra_params,
    }

    # Execute Generation
    try:
        if args.images:
            mode_desc = f"Image-to-3D with {len(args.images)} image(s)"
            if args.prompt:
                mode_desc += f" and prompt: '{args.prompt}'"
            print(f"Submitting {mode_desc} to {provider.provider_name}...")

            if args.no_wait:
                task = provider.generate_from_image(
                    images=args.images,
                    prompt=args.prompt,
                    **common_gen_kwargs,
                )
                print("\nTask submitted successfully!")
                print(f"Task UUID:         {task.task_uuid}")
                print(f"Subscription Key:  {task.subscription_key}")
                if task.consumed_credits is not None:
                    print(f"Consumed Credits:  {task.consumed_credits}")
                print("\nYou can check status later using:")
                print(f"  python3 model_creator.py --status {task.subscription_key}")
                print(f"Or download results when done using:")
                print(f"  python3 model_creator.py --download {task.task_uuid} -o {args.output_dir}")
                return
            else:
                out_dir = Path(args.output_dir)
                res = provider.create_from_image(
                    images=args.images,
                    output_dir=out_dir,
                    prompt=args.prompt,
                    wait=True,
                    timeout=args.timeout,
                    status_callback=print_status_update,
                    **common_gen_kwargs,
                )
        else:
            print(f"Submitting Text-to-3D: '{args.prompt}' to {provider.provider_name}...")

            if args.no_wait:
                task = provider.generate_from_text(
                    prompt=args.prompt,
                    **common_gen_kwargs,
                )
                print("\nTask submitted successfully!")
                print(f"Task UUID:         {task.task_uuid}")
                print(f"Subscription Key:  {task.subscription_key}")
                if task.consumed_credits is not None:
                    print(f"Consumed Credits:  {task.consumed_credits}")
                print("\nYou can check status later using:")
                print(f"  python3 model_creator.py --status {task.subscription_key}")
                print(f"Or download results when done using:")
                print(f"  python3 model_creator.py --download {task.task_uuid} -o {args.output_dir}")
                return
            else:
                out_dir = Path(args.output_dir)
                res = provider.create_from_text(
                    prompt=args.prompt,
                    output_dir=out_dir,
                    wait=True,
                    timeout=args.timeout,
                    status_callback=print_status_update,
                    **common_gen_kwargs,
                )

        should_recenter = (args.root in ("foot", "bottom")) or args.root_at_foot
        if should_recenter and res.primary_model_file and res.primary_model_file.exists():
            print("\nRecentering root origin to character feet (ground plane min Z/Y=0)...")
            recenter_model_to_foot(res.primary_model_file)

        print("\n\n3D Model Generation completed successfully!")
        print(f"Task UUID:          {res.task.task_uuid}")
        print(f"Total Duration:     {res.duration_seconds:.1f}s")
        print(f"Output Directory:   {res.output_dir}")
        if res.primary_model_file:
            print(f"Primary 3D Model:   {res.primary_model_file}")
        if res.preview_file:
            print(f"Preview Render:     {res.preview_file}")
        print("\nAll Downloaded Files:")
        for f in res.downloaded_files:
            print(f"  - {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    except AuthenticationError as e:
        print(f"\nAuthentication Error: {e}", file=sys.stderr)
        print("Please verify your API key using --api-key or set HYPER3D_API_KEY / RODIN_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)
    except InsufficientCreditsError as e:
        print(f"\nBilling Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RateLimitError as e:
        print(f"\nRate Limit Exceeded: {e}", file=sys.stderr)
        sys.exit(1)
    except TaskFailedError as e:
        print(f"\nGeneration Failed: {e}", file=sys.stderr)
        sys.exit(1)
    except TaskTimeoutError as e:
        print(f"\nOperation Timed Out: {e}", file=sys.stderr)
        sys.exit(1)
    except ModelCreatorError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
