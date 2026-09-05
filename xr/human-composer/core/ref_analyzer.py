"""
Reference image analyzer for Human Composer.
Analyzes multi-view reference images to extract character bounds,
head/hair silhouettes, and 3D target proportions.
"""

import os
from typing import Dict, Optional, Any
import numpy as np
from PIL import Image


def analyze_single_ref(image_path: str, view_name: str) -> Optional[Dict[str, Any]]:
    """Analyze a single reference image to detect character and head bounds."""
    if not os.path.exists(image_path):
        return None

    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    H, W, _ = arr.shape

    # Sample background color from border margins
    border_pixels = np.concatenate([
        arr[0:20, :, :].reshape(-1, 3),
        arr[-20:, :, :].reshape(-1, 3),
        arr[:, 0:20, :].reshape(-1, 3),
        arr[:, -20:, :].reshape(-1, 3)
    ], axis=0)
    bg_color = np.median(border_pixels, axis=0)

    # Segment foreground mask
    diff = np.linalg.norm(arr.astype(float) - bg_color.astype(float), axis=2)
    fg_mask = diff > 20.0

    ys, xs = np.where(fg_mask)
    if len(ys) == 0:
        return None

    y_min, y_max = int(ys.min()), int(ys.max())
    char_height = y_max - y_min

    # Arms start lower down (around 35-40% height),
    # so above 25% of character height gives pure head/hair region.
    y_head_only = int(y_min + char_height * 0.25)
    head_ys, head_xs = np.where(fg_mask[:y_head_only, :])

    if len(head_ys) == 0:
        head_x_min, head_x_max = int(xs.min()), int(xs.max())
        head_y_min = y_min
    else:
        head_x_min, head_x_max = int(head_xs.min()), int(head_xs.max())
        head_y_min = int(head_ys.min())

    head_width = head_x_max - head_x_min
    head_x_center = float((head_x_min + head_x_max) / 2.0)

    return {
        "view": view_name,
        "width": W,
        "height": H,
        "char_y_min": y_min,
        "char_y_max": y_max,
        "char_height": char_height,
        "head_y_min": head_y_min,
        "head_x_min": head_x_min,
        "head_x_max": head_x_max,
        "head_width": head_width,
        "head_x_center": head_x_center,
    }


def analyze_all_references(
    ref_front: Optional[str] = None,
    ref_left: Optional[str] = None,
    ref_right: Optional[str] = None,
    ref_back: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze all provided reference views and return consolidated metrics."""
    results = {}
    if ref_front:
        data = analyze_single_ref(ref_front, "front")
        if data:
            results["front"] = data
    if ref_left:
        data = analyze_single_ref(ref_left, "left")
        if data:
            results["left"] = data
    if ref_right:
        data = analyze_single_ref(ref_right, "right")
        if data:
            results["right"] = data
    if ref_back:
        data = analyze_single_ref(ref_back, "back")
        if data:
            results["back"] = data

    return results
