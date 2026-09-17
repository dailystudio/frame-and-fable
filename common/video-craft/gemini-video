#!/usr/bin/env python3
"""
gemini-video: CLI tool for generating videos using the Google Gemini / Veo API.

Supports:
- Text-to-Video generation
- Reference Images-guided generation (up to 3 reference images, style & asset references)
- Image-to-Video animation (starting frame)
- Frame Interpolation (first frame and last frame)
- Video Extension
- Native synchronized audio generation (dialogue, sound effects, ambience)
- Aspect ratio (16:9 landscape, 9:16 portrait) & resolution (720p, 1080p, 4K) control

Based on Google Gemini API Veo documentation:
https://ai.google.dev/gemini-api/docs/veo
"""

import sys
import os
import re
import time
import secrets
import argparse
import mimetypes
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: 'google-genai' package is not installed.", file=sys.stderr)
    print("Please install it using: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


MODEL_ALIASES: Dict[str, str] = {
    "3.1": "veo-3.1-generate-preview",
    "veo-3.1": "veo-3.1-generate-preview",
    "veo3.1": "veo-3.1-generate-preview",
    "veo3": "veo-3.1-generate-preview",
    "3.1-preview": "veo-3.1-generate-preview",
    "3.1-fast": "veo-3.1-fast-generate-preview",
    "veo-3.1-fast": "veo-3.1-fast-generate-preview",
    "fast": "veo-3.1-fast-generate-preview",
    "3.1-lite": "veo-3.1-lite-generate-preview",
    "veo-3.1-lite": "veo-3.1-lite-generate-preview",
    "lite": "veo-3.1-lite-generate-preview",
    "3.0": "veo-3.0-generate-001",
    "veo-3.0": "veo-3.0-generate-001",
    "veo3.0": "veo-3.0-generate-001",
    "3": "veo-3.0-generate-001",
    "3.0-fast": "veo-3.0-fast-generate-001",
    "veo-3.0-fast": "veo-3.0-fast-generate-001",
    "2.0": "veo-2.0-generate-001",
    "veo-2.0": "veo-2.0-generate-001",
    "veo2": "veo-2.0-generate-001",
    "2": "veo-2.0-generate-001",
}

AVAILABLE_MODELS = [
    "veo-3.1-generate-preview",       # Default: Veo 3.1 - Flagship video model, up to 4K, native audio, reference images
    "veo-3.1-fast-generate-preview",  # Veo 3.1 Fast - High fidelity, fast generation, up to 4K, native audio, reference images
    "veo-3.1-lite-generate-preview",  # Veo 3.1 Lite - Low latency, cost-effective, up to 1080p, text/image-to-video
    "veo-3.0-generate-001",           # Veo 3.0 - Stable 720p/1080p
    "veo-3.0-fast-generate-001",      # Veo 3.0 Fast - Stable fast 720p/1080p
    "veo-2.0-generate-001",           # Veo 2.0 - Legacy video generation
]

SUPPORTED_RATIOS = ["16:9", "9:16"]
SUPPORTED_RESOLUTIONS = ["720p", "1080p", "4k"]
SUPPORTED_DURATIONS = [4, 6, 8]
SUPPORTED_REF_TYPES = ["asset", "style"]


def resolve_model_name(model_arg: str) -> str:
    """Resolve model alias or return exact model name."""
    lowered = model_arg.strip().lower()
    if lowered in MODEL_ALIASES:
        return MODEL_ALIASES[lowered]
    return model_arg


def get_image_mime_type(file_path: str) -> Optional[str]:
    """Detect image MIME type or return None if not recognized as an image."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and mime_type.startswith("image/"):
        return mime_type
    ext = Path(file_path).suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif ext == ".png":
        return "image/png"
    elif ext == ".webp":
        return "image/webp"
    elif ext == ".gif":
        return "image/gif"
    elif ext in [".bmp", ".tiff"]:
        return f"image/{ext.lstrip('.')}"
    return None


def load_image_object(image_source: str) -> types.Image:
    """Load an image from a local file, Google Cloud Storage URI, or web URL."""
    if image_source.startswith("gs://") or ("storage.googleapis.com" in image_source):
        return types.Image.from_file(location=image_source)

    if image_source.startswith("http://") or image_source.startswith("https://"):
        try:
            import requests
            resp = requests.get(image_source, timeout=30)
            resp.raise_for_status()
            mime_type = resp.headers.get("Content-Type") or get_image_mime_type(image_source) or "image/png"
            # Strip charset if present
            mime_type = mime_type.split(";")[0].strip()
            return types.Image(image_bytes=resp.content, mime_type=mime_type)
        except Exception as e:
            print(f"Error fetching image from URL '{image_source}': {e}", file=sys.stderr)
            sys.exit(1)

    path = Path(image_source)
    if not path.exists():
        print(f"Error: Input image file '{image_source}' does not exist.", file=sys.stderr)
        sys.exit(1)

    mime_type = get_image_mime_type(image_source) or "image/png"
    try:
        with open(path, "rb") as f:
            data = f.read()
        return types.Image(image_bytes=data, mime_type=mime_type)
    except Exception as e:
        print(f"Error reading image '{image_source}': {e}", file=sys.stderr)
        sys.exit(1)


def load_video_object(video_source: str) -> types.Video:
    """Load a video object from a local file, GCS URI, or remote URI."""
    if video_source.startswith("gs://") or video_source.startswith("http://") or video_source.startswith("https://"):
        return types.Video(uri=video_source)

    path = Path(video_source)
    if not path.exists():
        print(f"Error: Input video file '{video_source}' does not exist.", file=sys.stderr)
        sys.exit(1)

    mime_type, _ = mimetypes.guess_type(video_source)
    mime_type = mime_type or "video/mp4"
    try:
        with open(path, "rb") as f:
            data = f.read()
        return types.Video(video_bytes=data, mime_type=mime_type)
    except Exception as e:
        print(f"Error reading video '{video_source}': {e}", file=sys.stderr)
        sys.exit(1)


def sanitize_id_for_filename(raw_id: Optional[str]) -> str:
    """Extract and sanitize interaction or operation ID or generate a random hex token."""
    if raw_id:
        base_id = str(raw_id).strip().split("/")[-1]
        cleaned = re.sub(r"[^\w\-]", "_", base_id).strip("_")
        if cleaned:
            return cleaned
    return secrets.token_hex(8)


def list_models_info():
    """Print available models and specifications."""
    print("\nAvailable Gemini / Veo Video Models:")
    print("-" * 80)
    print("  veo-3.1-generate-preview      (default / aliases: 3.1, veo-3.1, veo3.1, veo3)")
    print("      Veo 3.1 Preview - Flagship video model. Supports up to 4K resolution,")
    print("      up to 3 reference images (style & asset), first/last frame interpolation,")
    print("      video extension, and native synchronized audio (speech, SFX, ambience).")
    print("  veo-3.1-fast-generate-preview (aliases: 3.1-fast, veo-3.1-fast, fast)")
    print("      Veo 3.1 Fast Preview - High-speed generation with high fidelity, native audio,")
    print("      up to 4K resolution, and reference images.")
    print("  veo-3.1-lite-generate-preview (aliases: 3.1-lite, veo-3.1-lite, lite)")
    print("      Veo 3.1 Lite Preview - Low latency, cost-effective for high-volume generation,")
    print("      supports up to 1080p, text-to-video and image-to-video.")
    print("  veo-3.0-generate-001          (aliases: 3.0, veo-3.0, veo3.0, 3)")
    print("      Veo 3.0 Stable - 720p & 1080p generation with native audio.")
    print("  veo-3.0-fast-generate-001     (aliases: 3.0-fast, veo-3.0-fast)")
    print("      Veo 3.0 Fast Stable - Accelerated 720p & 1080p generation.")
    print("  veo-2.0-generate-001          (aliases: 2.0, veo-2.0, veo2, 2)")
    print("      Veo 2.0 - Legacy video generation model.")
    print("-" * 80 + "\n")


def list_ratios_info():
    """Print supported aspect ratios, resolutions, durations, and constraints."""
    print("\nSupported Aspect Ratios, Resolutions & Durations:")
    print("-" * 80)
    print("Aspect Ratios:")
    print("  16:9 (Landscape - default)")
    print("  9:16 (Portrait - optimized for mobile, shorts, reels, TikTok)")
    print("\nResolutions:")
    print("  720p  (1280x720 / 720x1280 - default, supports 4s, 6s, 8s)")
    print("  1080p (1920x1080 / 1080x1920 - requires 8s duration)")
    print("  4k    (3840x2160 / 2160x3840 - requires 8s duration, Veo 3.1 / 3.1 Fast only)")
    print("\nDurations:")
    print("  4s, 6s, 8s (default: 8s)")
    print("  * Note: 1080p, 4K, and reference image guidance require durationSeconds=8.")
    print("\nPerson Generation:")
    print("  allow_adult (default for reference images, image-to-video, and interpolation)")
    print("  allow_all   (available for text-to-video in supported regions)")
    print("-" * 80 + "\n")


def poll_operation(
    client: genai.Client,
    operation: Any,
    poll_interval: int = 10,
    timeout_seconds: int = 600,
    verbose: bool = False
) -> Any:
    """Poll long running operation until done, reporting progress."""
    start_time = time.time()
    spinner_chars = ["|", "/", "-", "\\"]
    spin_idx = 0

    while not operation.done:
        elapsed = int(time.time() - start_time)
        if elapsed > timeout_seconds:
            print(f"\nError: Operation timed out after {elapsed} seconds.", file=sys.stderr)
            sys.exit(1)

        char = spinner_chars[spin_idx % len(spinner_chars)]
        spin_idx += 1
        print(f"\r[{char}] Waiting for video generation to complete... ({elapsed}s elapsed)", end="", flush=True)
        time.sleep(poll_interval)
        try:
            operation = client.operations.get(operation)
        except Exception as e:
            if verbose:
                print(f"\n[gemini-video] Warning during polling: {e}")

    total_time = int(time.time() - start_time)
    print(f"\r[gemini-video] Video generation completed in {total_time}s!                      ")
    return operation


def download_and_save_video(
    client: genai.Client,
    api_key: str,
    generated_video: Any,
    output_path: Path,
    verbose: bool = False
) -> Path:
    """Download video content and save to destination file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video_obj = getattr(generated_video, "video", None) or generated_video

    video_bytes: Optional[bytes] = None

    # Method 1: Check if video_bytes already present
    if hasattr(video_obj, "video_bytes") and video_obj.video_bytes:
        video_bytes = video_obj.video_bytes

    # Method 2: client.files.download
    if not video_bytes:
        try:
            if verbose:
                print("[gemini-video] Downloading video via client.files.download...")
            video_bytes = client.files.download(file=video_obj)
        except Exception as err:
            if verbose:
                print(f"[gemini-video] client.files.download failed ({err}), trying direct URI download...")

    # Method 3: Direct HTTP download from video.uri with API key header
    if not video_bytes and hasattr(video_obj, "uri") and video_obj.uri:
        try:
            import requests
            if verbose:
                print(f"[gemini-video] Downloading from URI: {video_obj.uri}")
            headers = {"x-goog-api-key": api_key}
            resp = requests.get(video_obj.uri, headers=headers, stream=True, timeout=180)
            if resp.status_code == 200:
                video_bytes = resp.content
            else:
                print(f"Warning: HTTP download failed with status {resp.status_code}: {resp.text}", file=sys.stderr)
        except Exception as err:
            print(f"Warning: Direct URI download failed: {err}", file=sys.stderr)

    if not video_bytes:
        print("Error: Could not retrieve video bytes from generation result.", file=sys.stderr)
        sys.exit(1)

    with open(output_path, "wb") as f:
        f.write(video_bytes)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Successfully saved generated video to {output_path} ({size_mb:.2f} MB)")
    return output_path


def concatenate_videos(video_paths: List[Path], output_path: Path, verbose: bool = False) -> bool:
    """Concatenate multiple video clips sequentially into a single video file using ffmpeg."""
    import subprocess
    import tempfile

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        list_file = Path(f.name)
        for vp in video_paths:
            escaped_path = str(vp.resolve()).replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")

    try:
        # First attempt lossless stream copy concat
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output_path)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            if verbose:
                print("[gemini-video] Stream copy concat failed, re-encoding clips with ffmpeg...")
            # Fallback to re-encoding if stream copy fails
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), str(output_path)]
            res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode == 0:
            return True
        else:
            if verbose:
                print(f"[gemini-video] ffmpeg error: {res.stderr}", file=sys.stderr)
            return False
    except FileNotFoundError:
        print("Warning: 'ffmpeg' not found in PATH. Generated video segments were saved but could not be automatically concatenated.", file=sys.stderr)
        return False
    except Exception as ex:
        if verbose:
            print(f"[gemini-video] Concat exception: {ex}", file=sys.stderr)
        return False
    finally:
        if list_file.exists():
            list_file.unlink()


def enhance_prompt_with_gemini(client: genai.Client, prompt: str, verbose: bool = False) -> str:
    """Enhance and expand user prompt using Gemini Flash for cinematic video generation."""
    try:
        print("[gemini-video] Enhancing prompt with Gemini...")
        system_instruction = (
            "You are an expert cinematic director. Expand the following prompt into a vivid, visually descriptive "
            "prompt optimized for Veo 3.1 video generation. Detail the camera angles, lighting, motion, and atmosphere "
            "while strictly respecting any constraints (such as 'no human voice' or sound specifications). "
            "Return only the enhanced prompt without markdown headers or quotation marks."
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{system_instruction}\n\nOriginal prompt: {prompt}"
        )
        enhanced = resp.text.strip()
        if enhanced:
            if verbose:
                print(f"[gemini-video] Original Prompt: \"{prompt}\"")
                print(f"[gemini-video] Enhanced Prompt: \"{enhanced}\"")
            else:
                summary = enhanced[:120] + "..." if len(enhanced) > 120 else enhanced
                print(f"[gemini-video] Enhanced Prompt: \"{summary}\"")
            return enhanced
    except Exception as e:
        print(f"[gemini-video] Warning: Failed to enhance prompt via Gemini ({e}). Using original prompt.", file=sys.stderr)
    return prompt


def generate_single_video(
    client: genai.Client,
    api_key: str,
    model_name: str,
    prompt: str,
    first_frame_path: Optional[str],
    last_frame_path: Optional[str],
    ref_image_objects: List[types.VideoGenerationReferenceImage],
    video_input_path: Optional[str],
    aspect_ratio: str,
    resolution: str,
    duration_seconds: int,
    person_generation: str,
    negative_prompt: Optional[str],
    enhance_prompt: Optional[bool],
    fps: Optional[int],
    seed: Optional[int],
    generate_audio: bool,
    output_path: Optional[Path],
    out_dir: Path,
    poll_interval: int = 10,
    timeout_seconds: int = 600,
    verbose: bool = False,
) -> Path:
    """Generate a single video clip and save to output_path."""
    config_kwargs: Dict[str, Any] = {
        "aspect_ratio": aspect_ratio,
        "duration_seconds": duration_seconds,
        "resolution": resolution,
        "person_generation": person_generation,
    }

    if ref_image_objects:
        config_kwargs["reference_images"] = ref_image_objects

    if last_frame_path:
        config_kwargs["last_frame"] = load_image_object(last_frame_path)

    if negative_prompt:
        config_kwargs["negative_prompt"] = negative_prompt

    if getattr(client._api_client, "vertexai", False):
        if fps is not None:
            config_kwargs["fps"] = fps
        if seed is not None:
            config_kwargs["seed"] = seed
        if generate_audio is not None:
            config_kwargs["generate_audio"] = generate_audio
        if enhance_prompt is not None:
            config_kwargs["enhance_prompt"] = enhance_prompt

    config = types.GenerateVideosConfig(**config_kwargs)

    primary_image = load_image_object(first_frame_path) if first_frame_path else None
    primary_video = load_video_object(video_input_path) if video_input_path else None

    source_kwargs: Dict[str, Any] = {}
    if prompt:
        source_kwargs["prompt"] = prompt
    if primary_image:
        source_kwargs["image"] = primary_image
    if primary_video:
        source_kwargs["video"] = primary_video

    source = types.GenerateVideosSource(**source_kwargs) if source_kwargs else None

    generate_args: Dict[str, Any] = {
        "model": model_name,
        "config": config,
    }
    if source:
        generate_args["source"] = source

    if verbose or not last_frame_path:
        print(f"Generating video with {model_name}...", flush=True)
        if first_frame_path:
            print(f"Start Frame: {first_frame_path}", flush=True)
        if last_frame_path:
            print(f"End Frame (Interpolation): {last_frame_path}", flush=True)
        if ref_image_objects:
            print(f"Guided by {len(ref_image_objects)} reference image(s)", flush=True)
        if prompt:
            print(f"Prompt: \"{prompt}\"", flush=True)

    try:
        operation = client.models.generate_videos(**generate_args)
    except Exception as e:
        print(f"API Error ({model_name}): {e}", file=sys.stderr, flush=True)
        sys.exit(1)

    operation_name = getattr(operation, "name", None)
    if operation_name and verbose:
        print(f"[gemini-video] Operation Name: {operation_name}")

    operation = poll_operation(
        client=client,
        operation=operation,
        poll_interval=poll_interval,
        timeout_seconds=timeout_seconds,
        verbose=verbose
    )

    if getattr(operation, "error", None):
        print(f"Generation Error: {operation.error}", file=sys.stderr)
        sys.exit(1)

    response = getattr(operation, "response", None) or getattr(operation, "result", None)
    if not response or not hasattr(response, "generated_videos") or not response.generated_videos:
        print("Error: No generated video returned by the operation.", file=sys.stderr)
        if hasattr(response, "rai_media_filtered_reasons") and response.rai_media_filtered_reasons:
            print(f"Filtered reasons: {response.rai_media_filtered_reasons}", file=sys.stderr)
        sys.exit(1)

    generated_video = response.generated_videos[0]

    if not output_path:
        out_dir.mkdir(parents=True, exist_ok=True)
        filename_stem = sanitize_id_for_filename(operation_name)
        output_path = out_dir / f"{filename_stem}.mp4"

    return download_and_save_video(
        client=client,
        api_key=api_key,
        generated_video=generated_video,
        output_path=output_path,
        verbose=verbose
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="gemini-video",
        description="Generate videos using Google Gemini / Veo API with prompt and reference images.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
  # Generate video with reference images and prompt:
  gemini-video "A graceful dancer performing in an ethereal palace hall" -i character.png dress.png -o dance.mp4

  # Text-to-Video with 4K resolution and 16:9 ratio:
  gemini-video "Drone shot of a red vintage convertible cruising along coastal cliffs at sunset" -r 16:9 -s 4k -o sunset.mp4

  # Portrait video (9:16) for TikTok / Reels / Shorts:
  gemini-video "A barista brewing pour-over coffee in warm morning sunlight" -r 9:16 -o coffee.mp4

  # Image-to-Video (animate starting frame):
  gemini-video "The sleeping kitten wakes up, stretches, and yawns cutely" --start-frame kitten.png -o kitten_wakes.mp4

  # Frame Interpolation (transition from first frame to last frame):
  gemini-video "Fog swirls around the clearing as the figure vanishes" --start-frame frame1.png --last-frame frame2.png -o vanish.mp4

  # Fast generation with Veo 3.1 Fast:
  gemini-video "Cyberpunk hovercraft speeding through neon rainy streets" -m fast -o hovercraft.mp4
"""
    )

    parser.add_argument(
        "positional_inputs",
        nargs="*",
        default=[],
        help="Text prompt describing the video or paths to reference image file(s)."
    )
    parser.add_argument(
        "-p", "--prompt", "--prompt-text",
        dest="prompt_flags",
        action="append",
        nargs="+",
        help="Specify text prompt description."
    )
    parser.add_argument(
        "-i", "--image", "--images", "--ref", "--reference-image", "--reference-images",
        dest="ref_images",
        action="append",
        nargs="+",
        metavar="IMAGE_PATH",
        help="Path(s) to reference images guiding generation (up to 3 reference images for Veo 3.1)."
    )
    parser.add_argument(
        "--ref-type", "--reference-type",
        dest="ref_type",
        choices=SUPPORTED_REF_TYPES,
        default="asset",
        help="Type of reference image: 'asset' (subject/character/item, default) or 'style' (visual aesthetic)."
    )
    parser.add_argument(
        "--ref-style",
        dest="style_images",
        action="append",
        nargs="+",
        metavar="STYLE_IMAGE",
        help="Reference image(s) specifically treated with style guidance."
    )
    parser.add_argument(
        "--ref-asset",
        dest="asset_images",
        action="append",
        nargs="+",
        metavar="ASSET_IMAGE",
        help="Reference image(s) specifically treated with asset/subject guidance."
    )
    parser.add_argument(
        "--first-frame", "--start-frame", "--start-image",
        dest="first_frame",
        metavar="FIRST_FRAME",
        help="Path to initial image to animate (Image-to-Video or start frame for interpolation)."
    )
    parser.add_argument(
        "--mid-frame", "--mid-frames", "--middle-frame", "--middle-frames", "--middle-images",
        dest="mid_frames",
        action="append",
        nargs="+",
        metavar="MID_FRAME",
        help="Middle keyframe(s) between start and end frames for multi-step sequence interpolation."
    )
    parser.add_argument(
        "--last-frame", "--end-frame", "--end-image",
        dest="last_frame",
        metavar="LAST_FRAME",
        help="Path to final image for frame interpolation (used in combination with --first-frame)."
    )
    parser.add_argument(
        "--keyframes", "--sequence",
        dest="keyframes",
        action="append",
        nargs="+",
        metavar="KEYFRAME_IMAGE",
        help="Ordered list of keyframe images (e.g. start mid1 mid2 end). Generates sequential transitions and stitches them into a full video."
    )
    parser.add_argument(
        "-m", "--model",
        default="veo-3.1-generate-preview",
        help="Model to use (default: veo-3.1-generate-preview). Aliases: 3.1, 3.1-fast, 3.1-lite, 3.0, 3.0-fast, 2.0."
    )
    parser.add_argument(
        "-r", "-a", "--ratio", "--aspect-ratio",
        dest="aspect_ratio",
        choices=SUPPORTED_RATIOS,
        default="16:9",
        help="Video aspect ratio: 16:9 (landscape, default) or 9:16 (portrait)."
    )
    parser.add_argument(
        "-d", "--duration", "--duration-seconds",
        dest="duration_seconds",
        type=int,
        choices=SUPPORTED_DURATIONS,
        default=8,
        help="Length of the video in seconds: 4, 6, 8 (default: 8. Note: 1080p, 4K, and reference images require 8s)."
    )
    parser.add_argument(
        "-s", "--size", "--resolution",
        dest="resolution",
        type=lambda v: v.lower() if isinstance(v, str) else v,
        choices=SUPPORTED_RESOLUTIONS,
        default="720p",
        help="Output resolution: 720p (default), 1080p, 4k (Veo 3.1 / 3.1 Fast only)."
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=24,
        help="Video frames per second (default: 24)."
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Target output directory (e.g. ./outputs) or specific mp4 file path (default: ./outputs/<operation_id>.mp4)."
    )
    parser.add_argument(
        "--audio", "--generate-audio",
        dest="generate_audio",
        action="store_true",
        default=True,
        help="Generate native synchronized audio with dialogue, sound effects and ambience (default: enabled)."
    )
    parser.add_argument(
        "--no-audio",
        dest="generate_audio",
        action="store_false",
        help="Disable audio generation in the video."
    )
    parser.add_argument(
        "--negative-prompt",
        dest="negative_prompt",
        help="Negative prompt describing visual elements or sound to avoid."
    )
    parser.add_argument(
        "--enhance-prompt",
        action="store_true",
        default=None,
        help="Enable automatic prompt enhancement."
    )
    parser.add_argument(
        "--person-generation",
        choices=["allow_adult", "allow_all"],
        default=None,
        help="Control person generation: 'allow_adult' (required for reference images/image-to-video) or 'allow_all'."
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Integer seed for generation reproducibility."
    )
    parser.add_argument(
        "--video", "--extend",
        dest="video_input",
        metavar="VIDEO_SOURCE",
        help="Input video file or URI for video extension (Veo 3.1 only)."
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "reference", "start-frame", "interpolate"],
        default="auto",
        help="Image handling mode: 'auto' (default), 'reference' (use images as references), 'start-frame' (animate image), 'interpolate' (first/last frame)."
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between polling operation status (default: 10)."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Maximum seconds to wait for generation (default: 600)."
    )
    parser.add_argument(
        "--api-key",
        help="Gemini API Key. Can also be set via GEMINI_API_KEY or GOOGLE_API_KEY environment variable."
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available Gemini / Veo video generation models and exit."
    )
    parser.add_argument(
        "--list-ratios",
        action="store_true",
        help="List supported aspect ratios, resolutions, and durations and exit."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed execution progress and configuration."
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

    # Resolve API Key
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: Gemini API Key is required.", file=sys.stderr)
        print("Set GEMINI_API_KEY in your environment or pass --api-key YOUR_KEY.", file=sys.stderr)
        print("Example: export GEMINI_API_KEY=\"AIzaSy...\"", file=sys.stderr)
        sys.exit(1)

    # 1. Collect reference images, start frame, and text prompt
    raw_ref_images: List[Tuple[str, str]] = []  # (path_or_url, ref_type)
    text_prompts: List[str] = []

    # Process explicit reference images (-i)
    if args.ref_images:
        for item in args.ref_images:
            if isinstance(item, list):
                for p in item:
                    if p.strip().lower() not in ["image", "images"]:
                        raw_ref_images.append((p.strip(), args.ref_type))
            elif item.strip().lower() not in ["image", "images"]:
                raw_ref_images.append((item.strip(), args.ref_type))

    # Process explicit asset images
    if args.asset_images:
        for item in args.asset_images:
            if isinstance(item, list):
                for p in item:
                    raw_ref_images.append((p.strip(), "asset"))
            else:
                raw_ref_images.append((item.strip(), "asset"))

    # Process explicit middle frames
    mid_frame_paths: List[str] = []
    if args.mid_frames:
        for item in args.mid_frames:
            if isinstance(item, list):
                for p in item:
                    mid_frame_paths.append(p.strip())
            else:
                mid_frame_paths.append(item.strip())

    # Process explicit style images
    if args.style_images:
        for item in args.style_images:
            if isinstance(item, list):
                for p in item:
                    raw_ref_images.append((p.strip(), "style"))
            else:
                raw_ref_images.append((item.strip(), "style"))

    # Process prompt flags (-p)
    if args.prompt_flags:
        for pf in args.prompt_flags:
            if isinstance(pf, list):
                text_prompts.extend(pf)
            else:
                text_prompts.append(pf)

    # Process positional inputs (auto-detect existing image files vs text prompt)
    if args.positional_inputs:
        for item in args.positional_inputs:
            if not item:
                continue
            cleaned = item.strip("'\"")
            if cleaned.lower() in ["image", "images", "video"]:
                continue

            path_candidate = Path(cleaned)
            if path_candidate.exists() and path_candidate.is_file() and get_image_mime_type(str(path_candidate)):
                raw_ref_images.append((str(path_candidate), args.ref_type))
            else:
                text_prompts.append(item)

    prompt = " ".join(text_prompts).strip()

    # Collect keyframe sequence if provided
    keyframe_paths: List[str] = []
    if args.keyframes:
        for item in args.keyframes:
            if isinstance(item, list):
                for p in item:
                    keyframe_paths.append(p.strip())
            else:
                keyframe_paths.append(item.strip())

    # Determine first_frame and last_frame
    first_frame_path = args.first_frame
    last_frame_path = args.last_frame

    # If mid-frames are provided, construct ordered keyframe sequence
    if mid_frame_paths:
        if first_frame_path or last_frame_path:
            seq: List[str] = []
            if first_frame_path:
                seq.append(first_frame_path)
            seq.extend(mid_frame_paths)
            if last_frame_path:
                seq.append(last_frame_path)
            keyframe_paths = seq + keyframe_paths
            first_frame_path = None
            last_frame_path = None
        elif len(mid_frame_paths) >= 2:
            keyframe_paths = mid_frame_paths + keyframe_paths
        else:
            raw_ref_images.append((mid_frame_paths[0], "asset"))

    # Handle mode flag
    if args.mode == "start-frame" and not first_frame_path and raw_ref_images:
        first_frame_path = raw_ref_images.pop(0)[0]
    elif args.mode == "interpolate" and not first_frame_path and len(raw_ref_images) >= 2:
        first_frame_path = raw_ref_images.pop(0)[0]
        last_frame_path = raw_ref_images.pop(0)[0]

    # Validate mutually exclusive modalities for Veo API
    if (first_frame_path or last_frame_path or keyframe_paths) and raw_ref_images:
        print("Error: Veo API does not support combining reference images (-i / --ref) with start/end frames (--start-frame / --last-frame) or keyframes.", file=sys.stderr)
        print("  - To interpolate between keyframes in sequence, use: --keyframes img1.png img2.png (or --start-frame, --mid-frame, --end-frame).", file=sys.stderr)
        print("  - To guide character/style using reference images, use: -i ref1.png -p \"Your prompt\" (without --start-frame / --end-frame).", file=sys.stderr)
        sys.exit(1)

    # Validate inputs: must have at least prompt, image, or keyframes
    if not prompt and not raw_ref_images and not first_frame_path and not args.video_input and not keyframe_paths:
        print("Error: Please provide a prompt description, reference image(s), or --keyframes. Run 'gemini-video --help' for usage info.", file=sys.stderr)
        sys.exit(1)

    # Resolve Model
    model_name = resolve_model_name(args.model)

    # Check model compatibility with reference images
    if raw_ref_images and model_name not in ["veo-3.1-generate-preview", "veo-3.1-fast-generate-preview"]:
        print(f"[gemini-video] Note: Reference images are supported on Veo 3.1 models. Switching to veo-3.1-generate-preview.")
        model_name = "veo-3.1-generate-preview"

    # Enforce constraints for reference images & high resolutions (1080p, 4K):
    duration_seconds = args.duration_seconds
    resolution = args.resolution

    if raw_ref_images and duration_seconds != 8:
        if args.verbose:
            print(f"[gemini-video] Note: Veo 3.1 reference images require durationSeconds=8. Automatically setting duration to 8s.")
        duration_seconds = 8

    if resolution in ["1080p", "4k"] and duration_seconds != 8:
        if args.verbose:
            print(f"[gemini-video] Note: {resolution} resolution requires durationSeconds=8. Automatically setting duration to 8s.")
        duration_seconds = 8

    # Resolve person generation
    person_generation = args.person_generation
    if not person_generation:
        if raw_ref_images or first_frame_path or last_frame_path or keyframe_paths:
            person_generation = "allow_adult"
        else:
            person_generation = "allow_all"

    # Resolve Output Path
    default_dir = Path("outputs")
    default_dir.mkdir(parents=True, exist_ok=True)
    custom_output = args.output
    output_path: Optional[Path] = None
    out_dir = default_dir

    if custom_output:
        p_obj = Path(custom_output.strip())
        if p_obj.is_dir() or custom_output.endswith(os.sep) or custom_output.endswith("/"):
            out_dir = p_obj
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = None
        elif p_obj.suffix:
            output_path = p_obj
            out_dir = p_obj.parent
            out_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_path = p_obj.with_suffix(".mp4")
            out_dir = output_path.parent
            out_dir.mkdir(parents=True, exist_ok=True)

    # Initialize Gemini Client
    client = genai.Client(api_key=api_key, http_options={"timeout": 300000})

    # Enhance prompt with Gemini if requested
    if args.enhance_prompt and prompt:
        prompt = enhance_prompt_with_gemini(client, prompt, verbose=args.verbose)

    # =========================================================================
    # Branch 1: Sequential Keyframes Workflow (--keyframes start mid1 mid2 end)
    # =========================================================================
    if keyframe_paths:
        if len(keyframe_paths) < 2:
            print("Error: --keyframes requires at least 2 images (e.g. --keyframes start.png end.png).", file=sys.stderr)
            sys.exit(1)

        # Validate that all keyframe files exist
        for kfp in keyframe_paths:
            if not Path(kfp).exists() and not kfp.startswith("http://") and not kfp.startswith("https://") and not kfp.startswith("gs://"):
                print(f"Error: Keyframe image '{kfp}' does not exist.", file=sys.stderr)
                sys.exit(1)

        final_output_path = output_path or (out_dir / f"sequence_{secrets.token_hex(6)}.mp4")
        base_stem = final_output_path.stem
        num_segments = len(keyframe_paths) - 1
        segment_paths: List[Path] = []

        print(f"\n[gemini-video] Starting Sequential Keyframe Video Generation ({len(keyframe_paths)} keyframes -> {num_segments} scenes)...")
        print(f"Keyframes: {' -> '.join(keyframe_paths)}")
        if prompt:
            print(f"Shared Prompt: \"{prompt}\"")

        for idx in range(num_segments):
            k_start = keyframe_paths[idx]
            k_end = keyframe_paths[idx + 1]
            seg_path = out_dir / f"{base_stem}_seg{idx + 1}.mp4"
            segment_paths.append(seg_path)

            print(f"\n" + "=" * 80)
            print(f"Scene {idx + 1}/{num_segments}: {k_start}  --->  {k_end}")
            print("=" * 80)

            generate_single_video(
                client=client,
                api_key=api_key,
                model_name=model_name,
                prompt=prompt,
                first_frame_path=k_start,
                last_frame_path=k_end,
                ref_image_objects=[],
                video_input_path=None,
                aspect_ratio=args.aspect_ratio,
                resolution=resolution,
                duration_seconds=duration_seconds,
                person_generation=person_generation,
                negative_prompt=args.negative_prompt,
                enhance_prompt=None,
                fps=args.fps,
                seed=args.seed,
                generate_audio=args.generate_audio,
                output_path=seg_path,
                out_dir=out_dir,
                poll_interval=args.poll_interval,
                timeout_seconds=args.timeout,
                verbose=args.verbose
            )

        print(f"\n[gemini-video] All {num_segments} scenes generated. Concatenating with ffmpeg...")
        if concatenate_videos(segment_paths, final_output_path, verbose=args.verbose):
            size_mb = final_output_path.stat().st_size / (1024 * 1024)
            print(f"\n[gemini-video] Complete! Stitched {num_segments} scenes into {final_output_path} ({size_mb:.2f} MB)")
        else:
            print(f"\n[gemini-video] Video segments saved to: {', '.join([str(p) for p in segment_paths])}")
            print(f"Note: Run 'ffmpeg -f concat -safe 0 -i list.txt -c copy {final_output_path}' to merge them.")
        return

    # =========================================================================
    # Branch 2: Single-Shot Video Generation (Start + Middle Refs + End)
    # =========================================================================

    # Limit reference images to 3 (Veo 3.1 API constraint)
    if len(raw_ref_images) > 3:
        print(f"[gemini-video] Warning: Veo 3.1 accepts at most 3 reference images. Using first 3 of {len(raw_ref_images)}.")
        raw_ref_images = raw_ref_images[:3]

    # Prepare reference images objects
    ref_image_objects: List[types.VideoGenerationReferenceImage] = []
    for img_path, r_type in raw_ref_images:
        img_obj = load_image_object(img_path)
        ref_image_objects.append(
            types.VideoGenerationReferenceImage(
                image=img_obj,
                reference_type=r_type.lower()
            )
        )

    # Print summary
    if args.verbose:
        print(f"[gemini-video] Model: {model_name}")
        if prompt:
            print(f"[gemini-video] Prompt: \"{prompt}\"")
        if first_frame_path:
            print(f"[gemini-video] First / Start Frame: {first_frame_path}")
        if last_frame_path:
            print(f"[gemini-video] Last Frame: {last_frame_path}")
        if raw_ref_images:
            refs_desc = ", ".join([f"{p} ({t})" for p, t in raw_ref_images])
            print(f"[gemini-video] Reference Images ({len(raw_ref_images)}): {refs_desc}")
        if args.video_input:
            print(f"[gemini-video] Video Input (Extension): {args.video_input}")
        print(f"[gemini-video] Aspect Ratio: {args.aspect_ratio}")
        print(f"[gemini-video] Resolution: {resolution}")
        print(f"[gemini-video] Duration: {duration_seconds}s")
        print(f"[gemini-video] Person Generation: {person_generation}")

    print(f"Generating video with {model_name}...")
    if first_frame_path:
        print(f"Start Frame: {first_frame_path}")
    if raw_ref_images:
        print(f"Guided by {len(raw_ref_images)} reference image(s): {', '.join([p for p, _ in raw_ref_images])}")
    if last_frame_path:
        print(f"End Frame (Interpolation): {last_frame_path}")
    if prompt:
        print(f"Prompt: \"{prompt}\"")

    generate_single_video(
        client=client,
        api_key=api_key,
        model_name=model_name,
        prompt=prompt,
        first_frame_path=first_frame_path,
        last_frame_path=last_frame_path,
        ref_image_objects=ref_image_objects,
        video_input_path=args.video_input,
        aspect_ratio=args.aspect_ratio,
        resolution=resolution,
        duration_seconds=duration_seconds,
        person_generation=person_generation,
        negative_prompt=args.negative_prompt,
        enhance_prompt=None,
        fps=args.fps,
        seed=args.seed,
        generate_audio=args.generate_audio,
        output_path=output_path,
        out_dir=out_dir,
        poll_interval=args.poll_interval,
        timeout_seconds=args.timeout,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
