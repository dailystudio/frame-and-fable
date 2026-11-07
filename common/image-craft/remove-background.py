#!/usr/bin/env python3
"""
remove-background: CLI tool for removing solid / chroma-key backgrounds from images.

Uses the same OpenCV / Pillow HSV range chroma-key mechanism as
`gemini-image --transparent-background`, generalized to support any target
background color (defaulting to "green") and tolerating non-pure AI-generated
shades around the target color.
"""

import argparse
import colorsys
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple


# Popular named colors and chroma-key aliases (RGB 0-255)
NAMED_COLORS = {
    # Chroma-key primary defaults (pure chroma values so HSV range covers full shade spectrum)
    "green": (0, 255, 0),
    "chromagreen": (0, 255, 0),
    "greenscreen": (0, 255, 0),
    "lime": (0, 255, 0),
    "limegreen": (50, 205, 50),
    "brightgreen": (0, 255, 0),
    "darkgreen": (0, 100, 0),
    "forestgreen": (34, 139, 34),
    "lightgreen": (144, 238, 144),
    "blue": (0, 0, 255),
    "chromablue": (0, 0, 255),
    "bluescreen": (0, 0, 255),
    "red": (255, 0, 0),
    "chromared": (255, 0, 0),
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "cyan": (0, 255, 255),
    "aqua": (0, 255, 255),
    "magenta": (255, 0, 255),
    "fuchsia": (255, 0, 255),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "violet": (238, 130, 238),
    "pink": (255, 192, 203),
    "hotpink": (255, 105, 180),
    "brown": (165, 42, 42),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "lightgray": (211, 211, 211),
    "lightgrey": (211, 211, 211),
    "silver": (192, 192, 192),
    "darkgray": (169, 169, 169),
    "darkgrey": (169, 169, 169),
    "navy": (0, 0, 128),
    "teal": (0, 128, 128),
    "olive": (128, 128, 0),
    "maroon": (128, 0, 0),
    "coral": (255, 127, 80),
    "gold": (255, 215, 0),
    "indigo": (75, 0, 130),
    "ivory": (255, 255, 240),
    "khaki": (240, 230, 140),
    "lavender": (230, 230, 250),
    "beige": (245, 245, 220),
    "turquoise": (64, 224, 208),
    "skyblue": (135, 206, 235),
}


def _clamp_byte(val: float) -> int:
    return max(0, min(255, int(round(val))))


def parse_color(color_str: str) -> Tuple[int, int, int]:
    """
    Parse a color string in popular formats into an (R, G, B) tuple (0-255).

    Supported formats:
      - Named colors: "green", "white", "black", "blue", "red", "cyan", "magenta", "yellow", etc. (plus all CSS3/HTML names)
      - Short/full hex: "#FFF", "#FFFFFF", "#00FF00", "#0f0", "#FFFFFFFF"
      - 0x-prefixed hex: "0x00FF00", "0xFFF", "0xFFFFFF"
      - Bare hex: "FFF", "FFFFFF", "00FF00"
      - Functional RGB/RGBA: "rgb(255, 255, 255)", "rgba(0, 255, 0, 1.0)", "rgb(100%, 100%, 100%)"
      - Functional HSL/HSLA: "hsl(120, 100%, 50%)", "hsla(120, 100%, 50%, 1)"
      - Functional HSV/HSB: "hsv(120, 100%, 100%)", "hsb(120, 100%, 100%)"
      - Comma/space RGB tuples: "0, 255, 0", "(255, 255, 255)"
    """
    if not color_str or not str(color_str).strip():
        return (0, 255, 0)

    raw = str(color_str).strip().strip("'\"")
    lowered = raw.lower()

    # 1. Check built-in named colors & chroma aliases (ignoring spaces, hyphens, underscores)
    normalized_name = re.sub(r"[\s\-_]+", "", lowered)
    if normalized_name in NAMED_COLORS:
        return NAMED_COLORS[normalized_name]

    # 2. Check Hex formats (#RGB, #RGBA, #RRGGBB, #RRGGBBAA, 0xRGB, 0xRRGGBB)
    hex_match = re.fullmatch(r"(?:#|0x)([0-9a-fA-F]{3,8})", lowered)
    if hex_match:
        h = hex_match.group(1)
        if len(h) in (3, 4):
            r = int(h[0] * 2, 16)
            g = int(h[1] * 2, 16)
            b = int(h[2] * 2, 16)
            return (r, g, b)
        elif len(h) in (6, 8):
            r = int(h[0:2], 16)
            g = int(h[2:4], 16)
            b = int(h[4:6], 16)
            return (r, g, b)

    # 3. Functional rgb(...) / rgba(...)
    rgb_match = re.fullmatch(r"rgba?\(\s*([^\)]+?)\s*\)", lowered)
    if rgb_match:
        inner = rgb_match.group(1).replace("/", " ")
        parts = [p.strip() for p in re.split(r"[,;\s]+", inner) if p.strip()]
        if len(parts) >= 3:
            rgb_vals = []
            for p in parts[:3]:
                if p.endswith("%"):
                    rgb_vals.append(_clamp_byte(float(p[:-1]) * 255.0 / 100.0))
                else:
                    rgb_vals.append(_clamp_byte(float(p)))
            return (rgb_vals[0], rgb_vals[1], rgb_vals[2])

    # 4. Functional hsl(...) / hsla(...)
    hsl_match = re.fullmatch(r"hsla?\(\s*([^\)]+?)\s*\)", lowered)
    if hsl_match:
        inner = hsl_match.group(1).replace("/", " ")
        parts = [p.strip() for p in re.split(r"[,;\s]+", inner) if p.strip()]
        if len(parts) >= 3:
            h_deg = float(parts[0].rstrip("deg")) % 360.0
            s_val = float(parts[1].rstrip("%")) / 100.0 if parts[1].endswith("%") else float(parts[1])
            l_val = float(parts[2].rstrip("%")) / 100.0 if parts[2].endswith("%") else float(parts[2])
            if s_val > 1.0:
                s_val /= 100.0
            if l_val > 1.0:
                l_val /= 100.0
            r_f, g_f, b_f = colorsys.hls_to_rgb(h_deg / 360.0, max(0.0, min(1.0, l_val)), max(0.0, min(1.0, s_val)))
            return (_clamp_byte(r_f * 255), _clamp_byte(g_f * 255), _clamp_byte(b_f * 255))

    # 5. Functional hsv(...) / hsb(...)
    hsv_match = re.fullmatch(r"hs[vb]\(\s*([^\)]+?)\s*\)", lowered)
    if hsv_match:
        inner = hsv_match.group(1).replace("/", " ")
        parts = [p.strip() for p in re.split(r"[,;\s]+", inner) if p.strip()]
        if len(parts) >= 3:
            h_deg = float(parts[0].rstrip("deg")) % 360.0
            s_val = float(parts[1].rstrip("%")) / 100.0 if parts[1].endswith("%") else float(parts[1])
            v_val = float(parts[2].rstrip("%")) / 100.0 if parts[2].endswith("%") else float(parts[2])
            if s_val > 1.0:
                s_val /= 100.0
            if v_val > 1.0:
                v_val /= 100.0
            r_f, g_f, b_f = colorsys.hsv_to_rgb(h_deg / 360.0, max(0.0, min(1.0, s_val)), max(0.0, min(1.0, v_val)))
            return (_clamp_byte(r_f * 255), _clamp_byte(g_f * 255), _clamp_byte(b_f * 255))

    # 6. Pillow ImageColor (covers all 148 standard CSS3/X11 color names and formats)
    try:
        from PIL import ImageColor
        for candidate in (raw, normalized_name):
            try:
                rgb = ImageColor.getrgb(candidate)
                return (int(rgb[0]), int(rgb[1]), int(rgb[2]))
            except ValueError:
                pass
    except ImportError:
        pass

    # 7. Bare 3, 4, 6, or 8 character hex string without '#' (e.g. "FFF", "FFFFFF", "00FF00")
    bare_hex_match = re.fullmatch(r"([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", lowered)
    if bare_hex_match:
        h = bare_hex_match.group(1)
        if len(h) in (3, 4):
            return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))
        else:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    # 8. Plain comma- or space-separated RGB numbers: "255, 255, 255" or "(0, 255, 0)"
    tuple_inner = raw.strip("()[]{}")
    tuple_parts = [p.strip() for p in re.split(r"[,;\s]+", tuple_inner) if p.strip()]
    if len(tuple_parts) in (3, 4):
        try:
            vals = [_clamp_byte(float(p)) for p in tuple_parts[:3]]
            return (vals[0], vals[1], vals[2])
        except ValueError:
            pass

    raise ValueError(
        f"Unsupported color string: '{color_str}'. "
        "Examples of supported formats: 'green', 'white', '#FFF', '#00FF00', '0x00FF00', 'rgb(0, 255, 0)', 'hsl(120, 100%, 50%)'."
    )


def rgb_to_opencv_hsv(r: int, g: int, b: int) -> Tuple[int, int, int]:
    """
    Convert (R, G, B) in [0..255] to OpenCV HSV scale:
      H in [0..179], S in [0..255], V in [0..255].
    """
    h_f, s_f, v_f = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h_cv = int(round(h_f * 180.0)) % 180
    s_cv = _clamp_byte(s_f * 255.0)
    v_cv = _clamp_byte(v_f * 255.0)
    return (h_cv, s_cv, v_cv)


def compute_hsv_ranges(
    target_rgb: Tuple[int, int, int],
    tolerance: Optional[float] = None
) -> List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]:
    """
    Compute one or two OpenCV HSV (lower, upper) range pairs for chroma-key masking.

    - For green (H=60, S=255, V=255) with default tolerance, produces the exact
      same range as `gemini-image --transparent-background`:
      lower = (35, 40, 40), upper = (85, 255, 255).
    - If a non-pure green shade is passed (H in [35, 85], S >= 35, V >= 35),
      expands the range to cover both the standard green chroma key [35..85]
      and [H - h_tol .. H + h_tol] so all green variations are captured.
    - For other chromatic colors, centers around H with +/- h_tol (wrapping around
      0/180 for red hues) and accepts S/V variations from AI lighting/shading.
    - For achromatic colors (white/#FFF, black/#000, gray), allows any Hue (0..179)
      and filters by Saturation and Value ranges.
    """
    h_cv, s_cv, v_cv = rgb_to_opencv_hsv(*target_rgb)
    scale = (float(tolerance) / 25.0) if tolerance is not None else 1.0
    scale = max(0.1, scale)

    # Case 1: Dark / Black background (low Value)
    if v_cv < 45:
        v_tol = int(round(40 * scale))
        v_max = min(255, v_cv + v_tol)
        return [((0, 0, 0), (179, 255, v_max))]

    # Case 2: White / Light or Neutral Gray background (low Saturation)
    if s_cv < 35:
        if v_cv > 200:
            # White / near-white (e.g. #FFF, #F5F5F5)
            s_tol = int(round(35 * scale))
            v_tol = int(round(40 * scale))
            s_max = min(255, s_cv + s_tol)
            v_min = max(0, v_cv - v_tol)
            return [((0, 0, v_min), (179, s_max, 255))]
        else:
            # Neutral gray
            s_tol = int(round(30 * scale))
            v_tol = int(round(35 * scale))
            s_max = min(255, s_cv + s_tol)
            v_min = max(0, v_cv - v_tol)
            v_max = min(255, v_cv + v_tol)
            return [((0, 0, v_min), (179, s_max, v_max))]

    # Case 3: Chromatic color (green, blue, red, yellow, cyan, magenta, etc.)
    h_tol = int(round(25 * scale))
    s_min_default = max(0, min(40, int(round(40 / scale)))) if scale >= 1.0 else min(255, int(round(40 / scale)))
    v_min_default = s_min_default

    s_min = min(s_min_default, max(15, s_cv - int(round(45 * scale))))
    v_min = min(v_min_default, max(15, v_cv - int(round(45 * scale))))
    s_max = 255
    v_max = 255

    h_low = h_cv - h_tol
    h_high = h_cv + h_tol

    # If target is in the green family (35 <= H <= 85) and default/wider tolerance is used,
    # ensure the canonical [35, 85] green chroma-key window is fully included.
    if 35 <= h_cv <= 85 and tolerance is None:
        h_low = min(h_low, 35)
        h_high = max(h_high, 85)

    if h_high - h_low >= 179:
        return [((0, s_min, v_min), (179, s_max, v_max))]

    ranges: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = []
    if h_low < 0:
        ranges.append(((0, s_min, v_min), (min(179, h_high), s_max, v_max)))
        ranges.append(((max(0, 180 + h_low), s_min, v_min), (179, s_max, v_max)))
    elif h_high > 179:
        ranges.append(((max(0, h_low), s_min, v_min), (179, s_max, v_max)))
        ranges.append(((0, s_min, v_min), (min(179, h_high - 180), s_max, v_max)))
    else:
        ranges.append(((h_low, s_min, v_min), (h_high, s_max, v_max)))

    return ranges


def remove_background(
    input_path: Path,
    output_path: Optional[Path] = None,
    bg_color: str = "green",
    tolerance: Optional[float] = None,
    verbose: bool = False
) -> bool:
    """
    Removes the specified chroma-key / solid background color from an image
    and saves the result as a transparent PNG (or WEBP).

    Uses the same OpenCV HSV `inRange` mechanism as `gemini-image --transparent-background`,
    with a Pillow fallback when OpenCV is unavailable.
    """
    target_out = output_path if output_path is not None else input_path
    target_out.parent.mkdir(parents=True, exist_ok=True)

    target_rgb = parse_color(bg_color)
    hsv_ranges = compute_hsv_ranges(target_rgb, tolerance=tolerance)

    if verbose:
        h_cv, s_cv, v_cv = rgb_to_opencv_hsv(*target_rgb)
        print(f"[remove-background] Target color '{bg_color}' -> RGB{target_rgb}, OpenCV HSV({h_cv}, {s_cv}, {v_cv})")
        for idx, (low, high) in enumerate(hsv_ranges):
            print(f"[remove-background] HSV Range #{idx + 1}: lower={low}, upper={high}")

    try:
        import cv2
        import numpy as np

        raw_img = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
        if raw_img is None:
            return False

        if raw_img.ndim == 2:
            bgr = cv2.cvtColor(raw_img, cv2.COLOR_GRAY2BGR)
            existing_alpha = None
        elif raw_img.shape[2] == 4:
            bgr = raw_img[:, :, :3]
            existing_alpha = raw_img[:, :, 3]
        else:
            bgr = raw_img[:, :, :3]
            existing_alpha = None

        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for low, high in hsv_ranges:
            lower_arr = np.array(low, dtype=np.uint8)
            upper_arr = np.array(high, dtype=np.uint8)
            range_mask = cv2.inRange(hsv, lower_arr, upper_arr)
            combined_mask = cv2.bitwise_or(combined_mask, range_mask)

        mask_inv = cv2.bitwise_not(combined_mask)
        if existing_alpha is not None:
            mask_inv = cv2.bitwise_and(existing_alpha, mask_inv)

        b, g, r = cv2.split(bgr)
        result = cv2.merge([b, g, r, mask_inv])

        if target_out.suffix.lower() in (".png", ".webp"):
            cv2.imwrite(str(target_out), result)
        else:
            ok, encoded = cv2.imencode(".png", result)
            if not ok:
                return False
            with open(target_out, "wb") as f:
                f.write(encoded.tobytes())
        return True
    except Exception:
        try:
            from PIL import Image
            import numpy as np

            img = Image.open(input_path).convert("RGBA")
            rgba_data = np.array(img)
            hsv_img = img.convert("RGB").convert("HSV")
            hsv_pil = np.array(hsv_img)

            # Pillow HSV uses H in [0..255]; convert to OpenCV's [0..179] scale
            h_cv = (hsv_pil[:, :, 0].astype(np.float32) * 180.0 / 255.0).round().astype(np.int32) % 180
            s_cv = hsv_pil[:, :, 1].astype(np.int32)
            v_cv = hsv_pil[:, :, 2].astype(np.int32)

            bg_mask = np.zeros(h_cv.shape, dtype=bool)
            for low, high in hsv_ranges:
                in_range = (
                    (h_cv >= low[0]) & (h_cv <= high[0]) &
                    (s_cv >= low[1]) & (s_cv <= high[1]) &
                    (v_cv >= low[2]) & (v_cv <= high[2])
                )
                bg_mask |= in_range

            # Also include RGB dominance fallback for green as in gemini-image.py
            h_target, s_target, v_target = rgb_to_opencv_hsv(*target_rgb)
            if 35 <= h_target <= 85 and s_target >= 35 and v_target >= 35:
                r, g, b = rgba_data[:, :, 0], rgba_data[:, :, 1], rgba_data[:, :, 2]
                bg_mask |= (g > 80) & (g > r * 1.1) & (g > b * 1.1)

            rgba_data[:, :, 3][bg_mask] = 0
            result = Image.fromarray(rgba_data)
            pil_fmt = "WEBP" if target_out.suffix.lower() == ".webp" else "PNG"
            result.save(target_out, pil_fmt)
            return True
        except Exception as ex:
            print(f"Warning: Failed to process transparent background: {ex}", file=sys.stderr)
            return False


def resolve_output_path(input_path: Path, output_arg: Optional[str], multi_inputs: bool) -> Path:
    """
    Determine the destination file path for a given input image.
    - If no -o / --output is given:
      Overwrites in-place if input is .png or .webp; otherwise writes <stem>.png alongside input.
    - If -o / --output is a directory (or multiple inputs are given):
      Writes <output_dir>/<input_stem>.png.
    - If -o / --output is a file path:
      Forces .png if the extension does not support alpha (e.g. .jpg/.jpeg).
    """
    if not output_arg:
        if input_path.suffix.lower() in (".png", ".webp"):
            return input_path
        return input_path.with_suffix(".png")

    cleaned = output_arg.strip()
    out_obj = Path(cleaned)

    if multi_inputs or out_obj.is_dir() or cleaned.endswith(os.sep) or cleaned.endswith("/"):
        out_dir = out_obj if (not out_obj.suffix or out_obj.is_dir()) else out_obj.parent
        ext = input_path.suffix.lower() if input_path.suffix.lower() in (".png", ".webp") else ".png"
        return out_dir / f"{input_path.stem}{ext}"

    if not out_obj.suffix:
        return out_obj / f"{input_path.stem}.png"

    if out_obj.suffix.lower() not in (".png", ".webp"):
        return out_obj.with_suffix(".png")

    return out_obj


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="remove-background",
        description=(
            "Remove chroma-key or solid color backgrounds from images using the same "
            "HSV range mechanism as `gemini-image --transparent-background`."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
  # Remove green chroma-key background (default --bg-color "green", modifies in-place):
  remove-background character.png

  # Remove white background using short hex color:
  remove-background sprite.png --bg-color "#FFF"

  # Remove background and save to a new output file:
  remove-background input.png --bg-color "rgb(0, 255, 0)" -o output_transparent.png

  # Remove blue chroma-key background with custom tolerance:
  remove-background actor.png --bg-color "blue" -t 30 -o actor_cutout.png
"""
    )

    parser.add_argument(
        "inputs",
        nargs="*",
        default=[],
        help="Path(s) to input image file(s)."
    )
    parser.add_argument(
        "-i", "--input", "--image",
        dest="input_flags",
        action="append",
        nargs="+",
        metavar="IMAGE_PATH",
        help="Path(s) to input image file(s)."
    )
    parser.add_argument(
        "-c", "--bg-color", "--color", "--background-color",
        dest="bg_color",
        default="green",
        help=(
            "Target background color to remove (default: \"green\").\n"
            "Supports popular color strings: named colors (\"green\", \"white\", \"black\", \"blue\", etc.),\n"
            "hex (\"#FFF\", \"#00FF00\", \"0x00FF00\"), \"rgb(r,g,b)\", \"hsl(h,s%%,l%%)\", or \"hsv(h,s%%,v%%)\"."
        )
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Optional output file path or directory (default: overwrites .png/.webp in-place, or saves as <stem>.png)."
    )
    parser.add_argument(
        "-t", "--tolerance",
        type=float,
        default=None,
        help="Optional HSV color range tolerance (default: 25, matching gemini-image --transparent-background)."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print parsed RGB/HSV values and HSV range bounds."
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    input_paths: List[Path] = []
    if args.input_flags:
        for group in args.input_flags:
            if isinstance(group, list):
                input_paths.extend(Path(p) for p in group)
            else:
                input_paths.append(Path(group))
    if args.inputs:
        input_paths.extend(Path(p) for p in args.inputs)

    if not input_paths:
        print("Error: Please provide at least one input image. Run 'remove-background --help' for usage info.", file=sys.stderr)
        sys.exit(1)

    try:
        parse_color(args.bg_color)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    multi = len(input_paths) > 1
    had_error = False

    for in_path in input_paths:
        if not in_path.exists():
            print(f"Error: Input image file '{in_path}' does not exist.", file=sys.stderr)
            had_error = True
            continue

        out_path = resolve_output_path(in_path, args.output, multi_inputs=multi)
        if remove_background(
            input_path=in_path,
            output_path=out_path,
            bg_color=args.bg_color,
            tolerance=args.tolerance,
            verbose=args.verbose
        ):
            print(f"[remove-background] Successfully removed '{args.bg_color}' background for transparency: {out_path}")
        else:
            print(f"Error: Failed to remove background from '{in_path}'.", file=sys.stderr)
            had_error = True

    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
