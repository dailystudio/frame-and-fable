#!/usr/bin/env python3
"""
gemini-image: CLI tool for generating and editing images using the Gemini API (Nano Banana / Gemini 3 Image models).

Based on Google Gemini API Image Generation documentation:
https://ai.google.dev/gemini-api/docs/image-generation
"""

import sys
import os
import re
import secrets
import argparse
import base64
import mimetypes
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: 'google-genai' package is not installed.", file=sys.stderr)
    print("Please install it using: pip install google-genai pillow", file=sys.stderr)
    sys.exit(1)


MODEL_ALIASES: Dict[str, str] = {
    "3.1-flash": "gemini-3.1-flash-image",
    "flash": "gemini-3.1-flash-image",
    "nano-banana-2": "gemini-3.1-flash-image",
    "3.1-lite": "gemini-3.1-flash-lite-image",
    "lite": "gemini-3.1-flash-lite-image",
    "nano-banana-2-lite": "gemini-3.1-flash-lite-image",
    "3-pro": "gemini-3-pro-image",
    "3.1-pro": "gemini-3-pro-image",
    "pro": "gemini-3-pro-image",
    "nano-banana-pro": "gemini-3-pro-image",
    "nano-banana-2-pro": "gemini-3-pro-image",
    "2.5-flash": "gemini-2.5-flash-image",
    "nano-banana": "gemini-2.5-flash-image",
    "imagen3": "imagen-3.0-generate-002",
    "imagen": "imagen-3.0-generate-002",
}

AVAILABLE_MODELS = [
    "gemini-3.1-flash-image",      # Default (Nano Banana 2) - versatile, 4K, up to 14 reference images
    "gemini-3.1-flash-lite-image", # Nano Banana 2 Lite - fast, low latency, 1K resolution only
    "gemini-3-pro-image",          # Nano Banana Pro - professional assets, complex reasoning, 4K
    "gemini-2.5-flash-image",      # Nano Banana 1 - legacy (1024px)
    "imagen-3.0-generate-002",     # Dedicated Imagen 3 text-to-image model
]

SUPPORTED_RATIOS = [
    "1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9"
]

SUPPORTED_SIZES = [
    "0.5K", "512", "1K", "2K", "4K"
]


def resolve_model_name(model_arg: str) -> str:
    """Resolve model alias or return exact model name."""
    lowered = model_arg.strip().lower()
    if lowered in MODEL_ALIASES:
        return MODEL_ALIASES[lowered]
    return model_arg


def get_image_mime_type(file_path: str) -> Optional[str]:
    """Detect image MIME type or return None if not an image."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and mime_type.startswith("image/"):
        return mime_type
    ext = Path(file_path).suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif ext == ".webp":
        return "image/webp"
    elif ext == ".gif":
        return "image/gif"
    elif ext == ".png":
        return "image/png"
    return None


def load_image_input(file_path: str) -> Dict[str, Any]:
    """Load an image file and return base64 encoded data dict for Gemini API."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: Input image file '{file_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    mime_type = get_image_mime_type(file_path) or "image/png"
    try:
        with open(path, "rb") as f:
            img_bytes = f.read()
        b64_data = base64.b64encode(img_bytes).decode("utf-8")
        return {
            "type": "image",
            "data": b64_data,
            "mime_type": mime_type
        }
    except Exception as e:
        print(f"Error reading image '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)


def load_video_input(video_arg: str) -> Dict[str, Any]:
    """Load video input from YouTube URL or local video file."""
    if video_arg.startswith("http://") or video_arg.startswith("https://"):
        return {
            "type": "video",
            "uri": video_arg,
            "mime_type": "video/mp4"
        }
    path = Path(video_arg)
    if not path.exists():
        print(f"Error: Input video file '{video_arg}' does not exist.", file=sys.stderr)
        sys.exit(1)
    mime_type, _ = mimetypes.guess_type(video_arg)
    mime_type = mime_type or "video/mp4"
    try:
        with open(path, "rb") as f:
            video_bytes = f.read()
        b64_data = base64.b64encode(video_bytes).decode("utf-8")
        return {
            "type": "video",
            "data": b64_data,
            "mime_type": mime_type
        }
    except Exception as e:
        print(f"Error reading video '{video_arg}': {e}", file=sys.stderr)
        sys.exit(1)


def list_models_info():
    """Print available models and descriptions."""
    print("\nAvailable Gemini Image Models:")
    print("--------------------------------------------------------------------------------")
    print("  gemini-3.1-flash-image      (default / alias: 3.1-flash, flash)")
    print("      Nano Banana 2 - Versatile flagship model. Supports up to 4K resolution,")
    print("      14 reference images, video input, Google Search & Image Search grounding.")
    print("  gemini-3.1-flash-lite-image (alias: 3.1-lite, lite)")
    print("      Nano Banana 2 Lite - Ultra-low latency, cost-effective for speed/scale.")
    print("      Supports 1K resolution and up to 14 object reference images.")
    print("  gemini-3-pro-image          (alias: 3-pro, pro, nano-banana-pro)")
    print("      Nano Banana Pro - Premium choice for complex tasks, search grounding,")
    print("      interleaved text/image generation, and up to 4K resolution.")
    print("  gemini-2.5-flash-image      (alias: 2.5-flash)")
    print("      Nano Banana 1 - Speed & efficiency model (1024px).")
    print("  imagen-3.0-generate-002     (alias: imagen3)")
    print("      Imagen 3 dedicated text-to-image model.")
    print("--------------------------------------------------------------------------------\n")


def list_ratios_info():
    """Print available aspect ratios and resolution specifications."""
    print("\nSupported Aspect Ratios & Resolutions:")
    print("--------------------------------------------------------------------------------")
    print("Aspect Ratios: 1:1, 1:4, 1:8, 3:2, 2:3, 3:4, 4:1, 4:3, 4:5, 5:4, 8:1, 9:16, 16:9, 21:9")
    print("Output Sizes:  0.5K (512px), 1K (1024px), 2K (~2048px), 4K (~4096px)")
    print("Note: gemini-3.1-flash-lite-image supports 1K resolution only.")
    print("--------------------------------------------------------------------------------\n")


def save_image_bytes(img_bytes: bytes, output_path: Path, target_mime_type: str):
    """Save image bytes to file, converting JPEG to PNG/WEBP if needed using Pillow."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if target_mime_type in ["image/jpeg", "image/jpg"]:
        with open(output_path, "wb") as f:
            f.write(img_bytes)
    else:
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(img_bytes))
            pil_format = "PNG"
            if "webp" in target_mime_type:
                pil_format = "WEBP"
            img.save(output_path, format=pil_format)
        except Exception:
            with open(output_path, "wb") as f:
                f.write(img_bytes)


def remove_green_background(input_path: Path) -> bool:
    """
    Removes the green 0x00FF00 chroma key background from an image and saves it as a transparent PNG.
    Matches algorithm in create-sprites-transparent skill.
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(str(input_path))
        if img is None:
            return False

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])

        mask = cv2.inRange(hsv, lower_green, upper_green)
        mask_inv = cv2.bitwise_not(mask)

        b, g, r = cv2.split(img)
        rgba = [b, g, r, mask_inv]
        result = cv2.merge(rgba)

        cv2.imwrite(str(input_path), result)
        return True
    except Exception:
        try:
            from PIL import Image
            import numpy as np

            img = Image.open(input_path).convert("RGBA")
            data = np.array(img)

            r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
            green_mask = (g > 80) & (g > r * 1.1) & (g > b * 1.1)
            data[:, :, 3][green_mask] = 0

            result = Image.fromarray(data)
            result.save(input_path, "PNG")
            return True
        except Exception as ex:
            print(f"Warning: Failed to process transparent background: {ex}", file=sys.stderr)
            return False


def sanitize_id_for_filename(raw_id: Optional[str]) -> str:
    """Extract and sanitize interaction ID or generate a random hex token if unavailable."""
    if raw_id:
        base_id = str(raw_id).strip().split("/")[-1]
        cleaned = re.sub(r"[^\w\-]", "_", base_id).strip("_")
        if cleaned:
            return cleaned
    return secrets.token_hex(8)


def save_generated_images(
    images: List[bytes],
    out_dir: Path,
    custom_stem: Optional[str],
    custom_ext: Optional[str],
    default_ext: str,
    target_mime_type: str,
    raw_id: Optional[str],
    transparent_bg: bool = False
) -> List[Path]:
    """
    Save one or multiple generated images to disk.
    If single image and custom stem specified: <custom_stem>.<ext>
    If single image and default/dir: <interaction_id>.<ext>
    If multiple images (a series): <prefix>_0.<ext>, <prefix>_1.<ext>, ...
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = custom_ext if custom_ext else default_ext
    if not ext.startswith("."):
        ext = f".{ext}"
    if transparent_bg and ext.lower() != ".png":
        ext = ".png"

    base_prefix = custom_stem if custom_stem else sanitize_id_for_filename(raw_id)
    saved_files: List[Path] = []

    if len(images) == 1:
        file_path = out_dir / f"{base_prefix}{ext}"
        save_image_bytes(images[0], file_path, target_mime_type)
        if transparent_bg:
            if remove_green_background(file_path):
                print(f"[gemini-image] Successfully removed green chroma key background for transparency: {file_path}")
        print(f"Successfully saved generated image to {file_path}")
        saved_files.append(file_path)
    elif len(images) > 1:
        for idx, img_bytes in enumerate(images):
            file_path = out_dir / f"{base_prefix}_{idx}{ext}"
            save_image_bytes(img_bytes, file_path, target_mime_type)
            if transparent_bg:
                if remove_green_background(file_path):
                    print(f"[gemini-image] Successfully removed green chroma key background for transparency: {file_path}")
            print(f"Successfully saved generated image ({idx + 1}/{len(images)}) to {file_path}")
            saved_files.append(file_path)

    return saved_files


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="gemini-image",
        description="Generate or edit images using Google Gemini API (Gemini 3 Image / Nano Banana models).",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
  # Text-to-Image with 4K resolution and 16:9 ratio:
  gemini-image "A majestic dragon sitting on a snow-peaked mountain at dusk" -r 16:9 -s 4K -o dragon.png

  # Generate transparent PNG sprite:
  gemini-image "A cute pixel art potions bottle sprite" --transparent -s 2K -o potion.png

  # Image-to-Image editing:
  gemini-image "Transform this portrait into a futuristic cybernetic character" -i person.jpg -o cyberpunk.png
"""
    )

    parser.add_argument(
        "positional_inputs",
        nargs="*",
        default=[],
        help="Text prompt describing the image to generate or paths to input reference images."
    )
    parser.add_argument(
        "-p", "--prompt", "--prompt-text",
        dest="prompt_flags",
        action="append",
        nargs="+",
        help="Specify text prompt or input image path."
    )
    parser.add_argument(
        "-i", "--image", "--images",
        dest="input_images",
        action="append",
        nargs="+",
        metavar="IMAGE_PATH",
        help="Path to input reference image file(s). Can be specified multiple times or as multiple paths for multi-image input."
    )
    parser.add_argument(
        "-video", "--video",
        dest="video_inputs",
        action="append",
        metavar="VIDEO_ARG",
        help="Path to local video file or YouTube URL for video-to-image generation (Gemini 3.1 Flash Image)."
    )
    parser.add_argument(
        "-m", "--model",
        default="gemini-3.1-flash-image",
        help="Model to use (default: gemini-3.1-flash-image). Aliases: 3.1-flash, 3.1-lite, 3-pro, 2.5-flash, imagen3."
    )
    parser.add_argument(
        "-r", "-a", "--ratio", "--aspect-ratio",
        dest="aspect_ratio",
        choices=SUPPORTED_RATIOS,
        help=f"Aspect ratio for the generated image. Supported: {', '.join(SUPPORTED_RATIOS)}"
    )
    parser.add_argument(
        "-s", "--size", "--resolution",
        dest="image_size",
        type=lambda v: v.upper() if isinstance(v, str) else v,
        choices=SUPPORTED_SIZES,
        help="Output resolution / size: 0.5K (512), 1K, 2K, 4K."
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Target output directory (e.g., ./outputs or -o ./dir/) or specific image file path (default: ./outputs/<interaction_id>.png)."
    )
    parser.add_argument(
        "-f", "--format",
        dest="mime_format",
        choices=["png", "jpeg", "jpg", "webp"],
        help="Output image format (png, jpeg, webp). Default is inferred from output filename extension."
    )
    parser.add_argument(
        "--transparent-background", "--transparent",
        dest="transparent_bg",
        action="store_true",
        help="Automatically generate with a 0x00FF00 chroma key background and remove it to output a transparent PNG."
    )
    parser.add_argument(
        "--previous-id", "--prev", "--interaction-id",
        dest="previous_id",
        help="ID of previous interaction for multi-turn image creation and editing."
    )
    parser.add_argument(
        "--search", "--grounding",
        dest="search_grounding",
        action="store_true",
        help="Enable Google Search grounding to incorporate real-time data into image generation."
    )
    parser.add_argument(
        "--image-search",
        dest="image_search",
        action="store_true",
        help="Enable Google Image Search grounding (Gemini 3.1 Flash Image only)."
    )
    parser.add_argument(
        "--thinking-level",
        choices=["minimal", "high"],
        help="Control model thinking level (minimal or high)."
    )
    parser.add_argument(
        "--api-key",
        help="Gemini API Key. Can also be set via GEMINI_API_KEY or GOOGLE_API_KEY environment variable."
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available Gemini image generation models and exit."
    )
    parser.add_argument(
        "--list-ratios",
        action="store_true",
        help="List supported aspect ratios and sizes and exit."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed execution progress and model thinking steps."
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    if args.list_models:
        list_models_info()
        sys.exit(0)

    if args.list_ratios:
        list_ratios_info()
        sys.exit(0)

    # Collect raw input images, videos, and text prompts
    raw_image_paths = []
    video_args = []
    text_prompts = []

    # 1. Process explicit -i / --image flags
    if args.input_images:
        for item in args.input_images:
            if isinstance(item, list):
                for p in item:
                    if p.strip().lower() not in ["image", "images"]:
                        raw_image_paths.append(p)
            elif item.strip().lower() not in ["image", "images"]:
                raw_image_paths.append(item)

    # 2. Process video inputs
    if args.video_inputs:
        for v in args.video_inputs:
            if isinstance(v, list):
                video_args.extend(v)
            else:
                video_args.append(v)

    # 3. Gather positional arguments and -p flags
    all_raw_inputs = []
    if args.prompt_flags:
        for pf in args.prompt_flags:
            if isinstance(pf, list):
                all_raw_inputs.extend(pf)
            else:
                all_raw_inputs.append(pf)

    if args.positional_inputs:
        all_raw_inputs.extend(args.positional_inputs)

    # Auto-detect existing image files vs text prompts
    for item in all_raw_inputs:
        if not item:
            continue
        cleaned = item.strip("'\"")
        if cleaned.lower() in ["image", "images"]:
            continue
        
        path_candidate = Path(cleaned)
        if path_candidate.exists() and path_candidate.is_file() and get_image_mime_type(str(path_candidate)):
            raw_image_paths.append(str(path_candidate))
        else:
            text_prompts.append(item)

    prompt = " ".join(text_prompts).strip()

    # Apply transparent background prompt modifier if enabled
    if args.transparent_bg:
        chroma_suffix = "use 0x00FF00 chroma key background."
        if prompt:
            if not prompt.endswith("."):
                prompt += "."
            prompt += f" {chroma_suffix}"
        else:
            prompt = chroma_suffix

    if not prompt and not raw_image_paths and not video_args:
        print("Error: Please provide a prompt, input image(s), or video. Run 'gemini-image --help' for usage info.", file=sys.stderr)
        sys.exit(1)

    # Resolve API Key
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: Gemini API Key is required.", file=sys.stderr)
        print("Set GEMINI_API_KEY in your environment or pass --api-key YOUR_KEY.", file=sys.stderr)
        print("Example: export GEMINI_API_KEY=\"AIzaSy...\"", file=sys.stderr)
        sys.exit(1)

    # Resolve Model
    model_name = resolve_model_name(args.model)

    # Validate model-specific resolution limits
    image_size = args.image_size
    if image_size == "512":
        image_size = "0.5K"

    if model_name == "gemini-3.1-flash-lite-image" and image_size and image_size != "1K":
        print("[gemini-image] Note: gemini-3.1-flash-lite-image only supports 1K resolution. Setting image_size to 1K.")
        image_size = "1K"

    # Resolve Output Path & Target Format (Default directory: ./outputs)
    default_dir = Path("outputs")
    custom_stem: Optional[str] = None
    custom_ext: Optional[str] = None
    out_dir: Path = default_dir

    if args.output:
        output_arg = args.output.strip()
        path_obj = Path(output_arg)
        if path_obj.is_dir() or output_arg.endswith(os.sep) or output_arg.endswith("/"):
            out_dir = path_obj
        elif path_obj.suffix:
            out_dir = path_obj.parent
            custom_stem = path_obj.stem
            custom_ext = path_obj.suffix.lower()
        else:
            out_dir = path_obj

    # Infer output format / target_mime_type and default extension
    if args.transparent_bg:
        target_mime_type = "image/png"
        default_ext = ".png"
    elif args.mime_format:
        fmt = args.mime_format.lower()
        if fmt in ["jpeg", "jpg"]:
            target_mime_type = "image/jpeg"
            default_ext = ".jpg"
        elif fmt == "webp":
            target_mime_type = "image/webp"
            default_ext = ".webp"
        else:
            target_mime_type = "image/png"
            default_ext = ".png"
    elif custom_ext:
        if custom_ext in [".jpg", ".jpeg"]:
            target_mime_type = "image/jpeg"
            default_ext = custom_ext
        elif custom_ext == ".webp":
            target_mime_type = "image/webp"
            default_ext = ".webp"
        else:
            target_mime_type = "image/png"
            default_ext = ".png"
    else:
        target_mime_type = "image/png"
        default_ext = ".png"

    # Prepare Client
    client = genai.Client(api_key=api_key)

    if args.verbose:
        print(f"[gemini-image] Using Model: {model_name}")
        if prompt:
            print(f"[gemini-image] Prompt: \"{prompt}\"")
        if raw_image_paths:
            print(f"[gemini-image] Input Images ({len(raw_image_paths)}): {', '.join(raw_image_paths)}")
        if video_args:
            print(f"[gemini-image] Input Video: {', '.join(video_args)}")
        if args.aspect_ratio:
            print(f"[gemini-image] Aspect Ratio: {args.aspect_ratio}")
        if image_size:
            print(f"[gemini-image] Output Size: {image_size}")
        if args.previous_id:
            print(f"[gemini-image] Previous Interaction ID: {args.previous_id}")
        if custom_stem:
            expected_target = out_dir / f"{custom_stem}{custom_ext or default_ext}"
            print(f"[gemini-image] Output Target: {expected_target} ({target_mime_type})")
        else:
            print(f"[gemini-image] Output Directory: {out_dir} (default naming by interaction ID, format: {default_ext})")

    # Handle Imagen 3 vs Gemini Nano Banana models
    if "imagen" in model_name.lower():
        config = {"output_mime_type": target_mime_type}
        if args.aspect_ratio:
            config["aspect_ratio"] = args.aspect_ratio
        
        try:
            print(f"Generating image with {model_name}...")
            result = client.models.generate_images(
                model=model_name,
                prompt=prompt or "",
                config=config
            )
            extracted_images: List[bytes] = []
            if hasattr(result, "generated_images") and result.generated_images:
                for gen_img in result.generated_images:
                    if hasattr(gen_img, "image") and hasattr(gen_img.image, "image_bytes") and gen_img.image.image_bytes:
                        extracted_images.append(gen_img.image.image_bytes)

            if extracted_images:
                save_generated_images(
                    images=extracted_images,
                    out_dir=out_dir,
                    custom_stem=custom_stem,
                    custom_ext=custom_ext,
                    default_ext=default_ext,
                    target_mime_type=target_mime_type,
                    raw_id=None,
                    transparent_bg=args.transparent_bg
                )
            else:
                print("Error: No image returned from Imagen API.", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"API Error ({model_name}): {e}", file=sys.stderr)
            sys.exit(1)

    else:
        # Gemini 3 & 2.5 Image models (interactions API)
        input_payload = []

        # Add videos
        for v_arg in video_args:
            input_payload.append(load_video_input(v_arg))

        # Add images
        for img_path in raw_image_paths:
            img_data = load_image_input(img_path)
            input_payload.append(img_data)

        # Add prompt text
        if prompt:
            input_payload.append({"type": "text", "text": prompt})

        # Build response_format configuration - Gemini API requires image/jpeg
        response_format = {
            "type": "image",
            "mime_type": "image/jpeg"
        }
        if args.aspect_ratio:
            response_format["aspect_ratio"] = args.aspect_ratio
        if image_size:
            response_format["image_size"] = image_size

        interaction_args: Dict[str, Any] = {
            "model": model_name,
            "input": input_payload if len(input_payload) > 1 else (prompt if not raw_image_paths and not video_args else input_payload),
            "response_format": response_format
        }

        if args.previous_id:
            interaction_args["previous_interaction_id"] = args.previous_id

        # Tools: Search & Image Search
        if args.search_grounding or args.image_search:
            search_types = ["web_search"]
            if args.image_search:
                search_types.append("image_search")
            interaction_args["tools"] = [{
                "type": "google_search",
                "search_types": search_types
            }]

        if args.thinking_level:
            interaction_args["generation_config"] = {"thinking_level": args.thinking_level}

        try:
            print(f"Generating image with {model_name}...")
            interaction = client.interactions.create(**interaction_args)

            raw_interaction_id = None
            if hasattr(interaction, "id") and interaction.id:
                raw_interaction_id = interaction.id
                print(f"Interaction ID: {interaction.id}")

            # Process output thinking steps if verbose
            if args.verbose and hasattr(interaction, "steps"):
                for step in interaction.steps:
                    if getattr(step, "type", None) == "thought":
                        print("\n--- Model Thought ---")
                        for block in getattr(step, "summary", []):
                            if getattr(block, "type", None) == "text":
                                print(block.text)

            # Extract output image(s) from interaction steps
            extracted_images = []

            if hasattr(interaction, "steps"):
                for step in interaction.steps:
                    if getattr(step, "type", None) == "model_output":
                        for block in getattr(step, "content", []):
                            if getattr(block, "type", None) == "text" and args.verbose:
                                print(block.text)
                            elif getattr(block, "type", None) == "image" and hasattr(block, "data"):
                                extracted_images.append(base64.b64decode(block.data))

            # Fallback to output_image convenience property if no images in steps
            if not extracted_images and hasattr(interaction, "output_image") and interaction.output_image:
                extracted_images.append(base64.b64decode(interaction.output_image.data))

            if extracted_images:
                save_generated_images(
                    images=extracted_images,
                    out_dir=out_dir,
                    custom_stem=custom_stem,
                    custom_ext=custom_ext,
                    default_ext=default_ext,
                    target_mime_type=target_mime_type,
                    raw_id=raw_interaction_id,
                    transparent_bg=args.transparent_bg
                )
            else:
                if hasattr(interaction, "output_text") and interaction.output_text:
                    print(f"Model output text: {interaction.output_text}")
                print("Error: Failed to retrieve generated image data from response.", file=sys.stderr)
                sys.exit(1)

        except Exception as e:
            print(f"API Error ({model_name}): {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
