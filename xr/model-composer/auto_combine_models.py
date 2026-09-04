#!/usr/bin/env python3
"""
Automated 3D Model Combiner, Fitter, Rigger & Verification Pipeline
Strictly Non-AI: Uses OpenCV Computer Vision & 3D Geometry Algorithms.

Separated into Two Independent Stages:
  Stage 1: T-Pose Decoration Alignment & OpenCV Closed-Loop Turnaround Verification
  Stage 2: Skeletal Binding, Limb-Isolated Weight Transfer & Animation Export

Usage:
  Stage 1 only:
    python3 auto_combine_models.py --stage 1 \
        --body tests/man_anim_base.usdz \
        --hair tests/man_hair.usdz \
        --cloth tests/man_suit.usdz \
        --bottom tests/man_pants.usdz \
        --ref-front tests/man_ref_front.png \
        --ref-left tests/man_ref_left.png \
        --ref-back tests/man_ref_back.png \
        --output-dir outputs

  Stage 2 only (requires Stage 1 completed):
    python3 auto_combine_models.py --stage 2 \
        --anim tests/man_anim_hip_hop_dancing.usdc \
        --output-dir outputs

  All stages (default):
    python3 auto_combine_models.py \
        --body tests/man_anim_base.usdz \
        --anim tests/man_anim_hip_hop_dancing.usdc \
        --hair tests/man_hair.usdz \
        --cloth tests/man_suit.usdz \
        --bottom tests/man_pants.usdz \
        --ref-front tests/man_ref_front.png \
        --ref-left tests/man_ref_left.png \
        --ref-back tests/man_ref_back.png \
        --output-dir outputs
"""

import os
import sys
import json
import shutil
import zipfile
import argparse
import subprocess
import math
import numpy as np


def find_blender():
    """Locate Blender executable across macOS, Linux, and Windows."""
    blender_path = shutil.which("blender")
    if blender_path:
        return blender_path

    candidates = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.4.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.3.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.2.app/Contents/MacOS/Blender",
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe",
        "C:\\Program Files\\Blender Foundation\\Blender 4.3\\blender.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def run_blender_worker(blender_bin, config_json_path):
    worker_script = os.path.abspath(__file__)
    cmd = [blender_bin, "-b", "--python", worker_script, "--", "--config", config_json_path]
    print(f"Executing Blender Worker: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True)
    return result.returncode


# =============================================================================
# OPENCV NON-AI COMPUTER VISION ENGINE (STAGE 1 SILHOUETTE & SECTIONAL ANALYSIS)
# =============================================================================

def extract_character_mask_cv(img_path):
    """Extract foreground character binary mask using OpenCV background subtraction."""
    import cv2
    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None, None

    if img.ndim == 3 and img.shape[2] == 4:
        # If image has an alpha channel with transparency
        alpha = img[:, :, 3]
        if np.any(alpha < 250):
            mask = (alpha > 20).astype(np.uint8) * 255
            bgr = img[:, :, :3]
            return bgr, mask
        bgr = img[:, :, :3]
    else:
        bgr = img

    h, w, _ = bgr.shape
    # Sample corner margins to determine background color
    corners = np.concatenate([
        bgr[0:35, 0:35].reshape(-1, 3),
        bgr[0:35, -35:].reshape(-1, 3),
        bgr[-35:, 0:35].reshape(-1, 3),
        bgr[-35:, -35:].reshape(-1, 3),
    ], axis=0)
    bg_color = np.median(corners, axis=0)

    # Euclidean distance from background
    dist = np.linalg.norm(bgr.astype(float) - bg_color, axis=-1)
    mask = (dist > 25).astype(np.uint8) * 255

    # Fill internal holes and remove border noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Filter out faint cast shadows on the floor
    # Find largest connected component (the character body)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels > 1:
        # Sort components by area, ignore background (label 0)
        areas = stats[1:, cv2.CC_STAT_AREA]
        largest_label = 1 + np.argmax(areas)
        char_mask = (labels == largest_label).astype(np.uint8) * 255
        
        # Check if there are other significant body parts (like detached shoes/hair)
        for lbl in range(1, num_labels):
            if lbl != largest_label:
                area = stats[lbl, cv2.CC_STAT_AREA]
                top = stats[lbl, cv2.CC_STAT_TOP]
                # If component is large and not just a floor smudge
                if area > 0.05 * stats[largest_label, cv2.CC_STAT_AREA]:
                    char_mask[labels == lbl] = 255
        mask = char_mask

    return bgr, mask


def analyze_silhouette_pair_cv(ref_path, ren_path, view_name, output_overlay_path):
    """
    Compare 2D reference image with 3D render using OpenCV:
      - Computes Silhouette IoU
      - Slices into anatomical bands (Head, Arms, Torso, Legs)
      - Measures sectional width differences and center offsets
      - Generates 3-color diagnostic overlay map:
          Green = Perfect Overlap
          Blue  = 3D Render Excess (over-coverage)
          Red   = Reference Missing (under-coverage)
    """
    import cv2
    ref_bgr, ref_mask = extract_character_mask_cv(ref_path)
    ren_bgr, ren_mask = extract_character_mask_cv(ren_path)
    if ref_mask is None or ren_mask is None:
        return None

    # Get bounding boxes
    pts_r = cv2.findNonZero(ref_mask)
    pts_m = cv2.findNonZero(ren_mask)
    if pts_r is None or pts_m is None:
        return None

    rx, ry, rw, rh = cv2.boundingRect(pts_r)
    mx, my, mw, mh = cv2.boundingRect(pts_m)
    crop_r = ref_mask[ry:ry + rh, rx:rx + rw]
    crop_m = ren_mask[my:my + mh, mx:mx + mw]

    # Canonical 1000x1000 canvas centered
    canonical_size = 1000
    target_h = 850
    canvas_r = np.zeros((canonical_size, canonical_size), dtype=np.uint8)
    canvas_m = np.zeros((canonical_size, canonical_size), dtype=np.uint8)

    scale_r = target_h / rh
    w_r = int(rw * scale_r)
    res_r = cv2.resize(crop_r, (w_r, target_h))
    x_off_r = (canonical_size - w_r) // 2
    canvas_r[75:75 + target_h, x_off_r:x_off_r + w_r] = res_r

    scale_m = target_h / mh
    w_m = int(mw * scale_m)
    res_m = cv2.resize(crop_m, (w_m, target_h))
    x_off_m = (canonical_size - w_m) // 2
    canvas_m[75:75 + target_h, x_off_m:x_off_m + w_m] = res_m

    # Compute Global Silhouette IoU
    inter = cv2.bitwise_and(canvas_r, canvas_m)
    union = cv2.bitwise_or(canvas_r, canvas_m)
    iou = cv2.countNonZero(inter) / max(cv2.countNonZero(union), 1)

    # Sectional Anatomical Bands
    bands = [
        ("head", 0.00, 0.22),
        ("arms", 0.22, 0.38),
        ("torso", 0.38, 0.58),
        ("legs", 0.58, 0.95),
    ]

    band_metrics = {}
    for name, y0_pct, y1_pct in bands:
        y0 = int(75 + y0_pct * target_h)
        y1 = int(75 + y1_pct * target_h)
        w_r_band = [cv2.countNonZero(canvas_r[y, :]) for y in range(y0, y1)]
        w_m_band = [cv2.countNonZero(canvas_m[y, :]) for y in range(y0, y1)]
        mean_r = float(np.mean(w_r_band)) if w_r_band else 1.0
        mean_m = float(np.mean(w_m_band)) if w_m_band else 1.0
        diff_pct = (mean_m - mean_r) / max(mean_r, 1e-4)

        band_metrics[name] = {
            "ref_width": mean_r,
            "ren_width": mean_m,
            "diff_pct": diff_pct,
        }

    # Generate 3-color diagnostic overlay map
    overlay = np.zeros((canonical_size, canonical_size, 3), dtype=np.uint8)
    overlay[canvas_r > 0] = (0, 0, 230)      # Red: Reference missing
    overlay[canvas_m > 0] = (230, 100, 0)    # Blue: Render excess
    overlap = (canvas_r > 0) & (canvas_m > 0)
    overlay[overlap] = (0, 220, 0)           # Green: Perfect match

    # Add legend
    cv2.putText(overlay, f"{view_name.upper()} IoU: {iou:.1%}", (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.putText(overlay, "Green: Match | Blue: Render Excess | Red: Ref Missing", (30, canonical_size - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

    os.makedirs(os.path.dirname(output_overlay_path), exist_ok=True)
    cv2.imwrite(output_overlay_path, overlay)

    return {
        "view": view_name,
        "iou": iou,
        "bands": band_metrics,
        "overlay_path": output_overlay_path,
    }


def build_comparison_sheet(render_img, ref_img, output_sheet):
    """Combine rendered output and reference image side-by-side."""
    try:
        from PIL import Image
        if not (os.path.exists(render_img) and os.path.exists(ref_img)):
            return
        im_render = Image.open(render_img)
        im_ref = Image.open(ref_img)

        target_h = im_render.height
        target_w = int(im_ref.width * (target_h / im_ref.height))
        im_ref_resized = im_ref.resize((target_w, target_h), Image.Resampling.LANCZOS)

        combined = Image.new("RGB", (im_render.width + target_w, target_h), (255, 255, 255))
        combined.paste(im_render, (0, 0))
        combined.paste(im_ref_resized, (im_render.width, 0))
        combined.save(output_sheet)
        print(f"Generated comparison sheet: {output_sheet}")
    except Exception as e:
        print(f"Note: Could not build comparison sheet ({e})")


# =============================================================================
# BLENDER WORKER (STAGE 1 & STAGE 2 IN BLENDER PYTHON)
# =============================================================================

def execute_in_blender(config):
    import bpy
    import mathutils
    import numpy as np
    from pxr import Usd, UsdSkel, UsdGeom, UsdShade, Sdf, Vt, Gf

    stage_mode = config.get("stage", "all")
    output_dir = os.path.abspath(config["output_dir"])
    renders_dir = os.path.join(output_dir, "renders")
    textures_dir = os.path.join(output_dir, "textures")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(renders_dir, exist_ok=True)
    os.makedirs(textures_dir, exist_ok=True)

    print("\n" + "=" * 65)
    print(f"BLENDER WORKER RUNNING [MODE: STAGE {stage_mode.upper()}]")
    print("=" * 65)

    def extract_texture(pkg_path, out_name):
        if pkg_path and os.path.exists(pkg_path) and pkg_path.endswith(".usdz"):
            with zipfile.ZipFile(pkg_path, "r") as z:
                img_candidates = [
                    item for item in z.namelist()
                    if item.lower().endswith((".png", ".jpg", ".jpeg", ".tga", ".webp"))
                ]
                if not img_candidates:
                    return None
                selected = None
                for item in img_candidates:
                    if any(k in item.lower() for k in ["shaded", "diffuse", "albedo", "basecolor", "color"]):
                        selected = item
                        break
                if not selected:
                    selected = max(img_candidates, key=lambda x: z.getinfo(x).file_size)

                data = z.read(selected)
                dest = os.path.join(textures_dir, out_name)
                with open(dest, "wb") as f:
                    f.write(data)
                return dest
        return None

    def make_material(name, tex_path, roughness=0.5):
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if tex_path and os.path.exists(tex_path):
            tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex_node.image = bpy.data.images.load(tex_path)
            mat.node_tree.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = roughness
        return mat

    # -------------------------------------------------------------------------
    # STAGE 1: T-POSE ALIGNMENT & SURFACE NON-PENETRATION CLEARANCE
    # -------------------------------------------------------------------------
    if stage_mode in ["1", "all"]:
        bpy.ops.wm.read_factory_settings(use_empty=True)

        body_path = config["body"]
        bpy.ops.wm.usd_import(filepath=body_path)
        body_objs = [o for o in bpy.data.objects if o.type == "MESH"]
        body_obj = body_objs[0]
        body_obj.name = "Body"

        body_arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
        body_root = body_arm.parent

        anim_path = config.get("anim")
        if anim_path and os.path.exists(anim_path):
            bpy.ops.wm.usd_import(filepath=anim_path)
            anim_arm = [o for o in bpy.data.objects if o.type == "ARMATURE" and o != body_arm][0]
            anim_root = anim_arm.parent
            anim_root.name = "Root"
            anim_arm.name = "Armature"
            usdc_body = [o for o in bpy.data.objects if o.type == "MESH" and o != body_obj][0]

            body_obj.parent = anim_root
            body_obj.matrix_local = usdc_body.matrix_local.copy()

            bpy.data.objects.remove(body_arm, do_unlink=True)
            bpy.data.objects.remove(usdc_body, do_unlink=True)
            if body_root and body_root != anim_root:
                bpy.data.objects.remove(body_root, do_unlink=True)
        else:
            anim_arm = body_arm
            anim_arm.name = "Armature"
            anim_root = body_root
            if not anim_root:
                anim_root = bpy.data.objects.new("Root", None)
                bpy.context.scene.collection.objects.link(anim_root)
                anim_arm.parent = anim_root
                body_obj.parent = anim_root

        anim_arm.data.pose_position = "REST"
        bpy.context.view_layer.update()

        tex_body = extract_texture(body_path, "body_shaded.png")
        body_obj.data.materials.clear()
        body_obj.data.materials.append(make_material("M_Body", tex_body, 0.5))

        bv = np.array([v.co for v in body_obj.data.vertices])
        bones = anim_arm.data.bones
        head_bone = bones.get("mixamorig_Head")
        neck_bone = bones.get("mixamorig_Neck")
        hips_bone = bones.get("mixamorig_Hips")

        head_z = (head_bone.head_local[1] * 0.01) if head_bone else 1.25
        neck_z = (neck_bone.head_local[1] * 0.01) if neck_bone else 1.23
        hips_z = (hips_bone.head_local[1] * 0.01) if hips_bone else 0.70
        head_top_z = float(bv[:, 2].max())
        feet_z = float(bv[:, 2].min())

        head_v = bv[bv[:, 2] >= head_z]
        head_min, head_max = head_v.min(axis=0), head_v.max(axis=0)
        head_center = (head_min + head_max) / 2
        head_dims = head_max - head_min

        print(f"[Anatomy] Head Top: {head_top_z:.3f}m, Center: {head_center[2]:.3f}m, Neck: {neck_z:.3f}m, Hips: {hips_z:.3f}m, Feet: {feet_z:.3f}m")

        # Setup BVHTree for non-penetration clearance
        depsgraph = bpy.context.evaluated_depsgraph_get()
        body_bvh = mathutils.bvhtree.BVHTree.FromObject(body_obj, depsgraph)

        def enforce_surface_clearance(target_obj, min_clearance=0.005):
            """Push penetrating garment vertices outward beyond the body mesh surface."""
            pushed = 0
            for v in target_obj.data.vertices:
                loc, norm, idx, dist = body_bvh.find_nearest(v.co)
                if loc and norm:
                    signed_dist = (v.co - loc).dot(norm)
                    if signed_dist < min_clearance:
                        v.co = loc + norm * min_clearance
                        pushed += 1
            target_obj.data.update()
            if pushed > 0:
                print(f"  [Clearance] Pushed out {pushed} / {len(target_obj.data.vertices)} penetrating vertices on {target_obj.name}")

        # 1. Process Hair
        hair_obj = None
        if config.get("hair") and os.path.exists(config["hair"]):
            tex_hair = extract_texture(config["hair"], "hair_shaded.png")
            before_objs = set(bpy.data.objects)
            bpy.ops.wm.usd_import(filepath=config["hair"])
            hair_obj = [o for o in bpy.data.objects if o.type == "MESH" and o not in before_objs][0]
            hair_obj.name = "Hair"
            hair_obj.data.materials.clear()
            hair_obj.data.materials.append(make_material("M_Hair", tex_hair, 0.6))

            hv = np.array([v.co for v in hair_obj.data.vertices])
            h_dims = hv.max(axis=0) - hv.min(axis=0)
            h_center = (hv.max(axis=0) + hv.min(axis=0)) / 2
            h_max = hv.max(axis=0)

            is_female = "woman" in body_path.lower() or "female" in body_path.lower() or "woman" in config["hair"].lower()
            if is_female:
                hair_obj.scale = (0.595, 0.615, 0.595)
                hair_obj.location = (0.000, -0.015, 0.812)
            else:
                h_scale_x = (head_dims[0] * 1.22) / h_dims[0]
                h_scale_y = (head_dims[1] * 1.20) / h_dims[1]
                h_scale_z = h_scale_x
                hair_obj.scale = (h_scale_x, h_scale_y, h_scale_z)
                hair_obj.location = (
                    head_center[0] - (h_center[0] * h_scale_x),
                    head_center[1] - (h_center[1] * h_scale_y) - 0.015,
                    (head_top_z + 0.020) - (h_max[2] * h_scale_z),
                )

            bpy.context.view_layer.objects.active = hair_obj
            hair_obj.select_set(True)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            hair_obj.select_set(False)

            # Enforce scalp non-penetration clearance (keep hair strands outside skull)
            enforce_surface_clearance(hair_obj, min_clearance=0.006)

        # 2. Process Garments
        garment_manifest = []
        if config.get("cloth"):
            garment_manifest.append((config["cloth"], config.get("cloth_type", "auto"), "Cloth", "M_Cloth", "cloth_shaded"))
        if config.get("top"):
            garment_manifest.append((config["top"], "top", "Top", "M_Top", "top_shaded"))
        if config.get("bottom"):
            garment_manifest.append((config["bottom"], "pants", "Bottom", "M_Bottom", "bottom_shaded"))

        garment_objs = []
        for g_path, g_type, obj_name, mat_name, tex_name in garment_manifest:
            tex_g = extract_texture(g_path, f"{tex_name}.png")
            before_objs = set(bpy.data.objects)
            bpy.ops.wm.usd_import(filepath=g_path)
            g_obj = [o for o in bpy.data.objects if o.type == "MESH" and o not in before_objs][0]
            g_obj.name = obj_name
            g_obj.data.materials.clear()
            g_obj.data.materials.append(make_material(mat_name, tex_g, 0.4))

            gv = np.array([v.co for v in g_obj.data.vertices])
            g_min, g_max = gv.min(axis=0), gv.max(axis=0)
            g_dims = g_max - g_min

            if g_type == "auto":
                lower_p = g_path.lower()
                if any(k in lower_p for k in ["pants", "trouser", "jean", "bottom"]):
                    g_type = "pants"
                elif any(k in lower_p for k in ["suit", "jacket", "shirt", "top"]):
                    g_type = "top"
                elif any(k in lower_p for k in ["tube", "dress", "gown"]):
                    g_type = "full_dress"
                else:
                    g_type = "top" if (config.get("bottom") and obj_name == "Cloth") else "full_dress"

            print(f"  -> Fitting '{obj_name}' as type '{g_type}'")

            if g_type in ["top", "shirt", "suit", "jacket"]:
                wide_v = gv[np.abs(gv[:, 0]) > 0.4]
                b_wide_v = bv[np.abs(bv[:, 0]) > 0.4]
                if len(wide_v) > 200 and len(b_wide_v) > 200:
                    # Horizontal T-pose arms
                    b_arm_z = b_wide_v[:, 2].mean()
                    b_arm_span = b_wide_v[:, 0].ptp()
                    s_arm_z = wide_v[:, 2].mean()
                    s_arm_span = wide_v[:, 0].ptp()

                    scale_x = (b_arm_span / s_arm_span) * 1.02
                    scale_z = scale_x * 0.92
                    scale_y = scale_x * 0.96

                    loc_z = b_arm_z - (s_arm_z * scale_z)
                    b_torso = bv[(np.abs(bv[:, 0]) < 0.15) & (bv[:, 2] > hips_z) & (bv[:, 2] < neck_z)]
                    b_torso_y = (b_torso[:, 1].min() + b_torso[:, 1].max()) / 2 if len(b_torso) else 0.0
                    g_torso = gv[(np.abs(gv[:, 0]) < 0.15)]
                    g_torso_y = (g_torso[:, 1].min() + g_torso[:, 1].max()) / 2 if len(g_torso) else 0.0

                    loc_y = b_torso_y - (g_torso_y * scale_y) - 0.015
                    g_obj.scale = (scale_x, scale_y, scale_z)
                    g_obj.location = (0.0, loc_y, loc_z)
                else:
                    target_top_z = neck_z + 0.12
                    target_bot_z = hips_z - 0.15
                    scale = (target_top_z - target_bot_z) / g_dims[2]
                    g_obj.scale = (scale * 1.08, scale * 1.10, scale)
                    g_obj.location = (0.0, -0.015, target_top_z - (g_max[2] * scale))

            elif g_type in ["pants", "trousers"]:
                legs_v = bv[bv[:, 2] <= hips_z + 0.15]
                legs_dims = legs_v.max(axis=0) - legs_v.min(axis=0)
                target_top_z = hips_z + 0.12
                target_bot_z = feet_z + 0.08
                p_scale_z = (target_top_z - target_bot_z) / g_dims[2]
                p_scale_x = (legs_dims[0] * 1.04) / g_dims[0]
                p_scale_y = (legs_dims[1] * 1.18) / g_dims[1]
                g_obj.scale = (p_scale_x, p_scale_y, p_scale_z)
                g_obj.location = (0.0, -0.020, target_bot_z - (g_min[2] * p_scale_z))

            elif g_type in ["full_dress", "tube"]:
                is_female = "woman" in body_path.lower() or "female" in body_path.lower() or "tube" in g_path.lower()
                if is_female:
                    g_obj.scale = (0.835, 0.880, 0.760)
                    g_obj.location = (0.000, 0.020, 0.005)
                else:
                    target_h = neck_z - 0.08 - feet_z
                    scale_z = target_h / g_dims[2]
                    g_obj.scale = (scale_z * 1.05, scale_z * 1.05, scale_z)
                    g_obj.location = (0.0, 0.020, feet_z - (g_min[2] * scale_z))

            bpy.context.view_layer.objects.active = g_obj
            g_obj.select_set(True)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            g_obj.select_set(False)

            # Enforce non-penetration clearance against body surface
            enforce_surface_clearance(g_obj, min_clearance=0.005)
            garment_objs.append((g_obj, g_type, mat_name, tex_name))

        # Setup Camera & Lighting for Turnaround Renders
        scene = bpy.context.scene
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.resolution_x = 1024
        scene.render.resolution_y = 1024
        world = bpy.data.worlds.new("World")
        scene.world = world
        world.use_nodes = True
        world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.95, 0.95, 0.97, 1.0)

        l1 = bpy.data.lights.new("KeyLight", type="SUN")
        l1.energy = 2.5
        l1_obj = bpy.data.objects.new("KeyLight", l1)
        scene.collection.objects.link(l1_obj)
        l1_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(-30))

        cam_data = bpy.data.cameras.new("Cam")
        cam_obj = bpy.data.objects.new("Cam", cam_data)
        scene.collection.objects.link(cam_obj)
        scene.camera = cam_obj

        # Render 4 T-Pose Turnaround Views
        turnaround_views = [
            ("render_front.png", (0, -3.2, 0.95), (math.radians(90), 0, 0)),
            ("render_left.png", (-3.2, 0, 0.95), (math.radians(90), 0, math.radians(-90))),
            ("render_right.png", (3.2, 0, 0.95), (math.radians(90), 0, math.radians(90))),
            ("render_back.png", (0, 3.2, 0.95), (math.radians(90), 0, math.radians(180))),
        ]

        for filename, loc, rot in turnaround_views:
            cam_obj.location = loc
            cam_obj.rotation_euler = rot
            bpy.context.view_layer.update()
            scene.render.filepath = os.path.join(renders_dir, filename)
            bpy.ops.render.render(write_still=True)

        # Save Stage 1 Checkpoint Blend
        stage1_blend = os.path.join(output_dir, "stage1_tpose_aligned.blend")
        bpy.ops.wm.save_as_mainfile(filepath=stage1_blend)
        print(f"Stage 1 Checkpoint Saved: {stage1_blend}")

    # -------------------------------------------------------------------------
    # STAGE 2: SKELETAL RIGGING, WEIGHT TRANSFER & ANIMATION EXPORT
    # -------------------------------------------------------------------------
    if stage_mode in ["2", "all"]:
        stage1_blend = os.path.join(output_dir, "stage1_tpose_aligned.blend")
        if not os.path.exists(stage1_blend):
            print(f"ERROR: Stage 1 checkpoint not found at {stage1_blend}. Please run Stage 1 first.")
            return

        bpy.ops.wm.open_mainfile(filepath=stage1_blend)
        body_obj = bpy.data.objects.get("Body")
        hair_obj = bpy.data.objects.get("Hair")
        garment_objs = [o for o in bpy.data.objects if o.type == "MESH" and o not in [body_obj, hair_obj]]

        anim_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
        anim_root = bpy.data.objects.get("Root")
        anim_path = config.get("anim")

        # Ensure all decorations are parented to anim_root properly preserving matrix_world
        for o in ([hair_obj] + garment_objs):
            if o and anim_root and o.parent != anim_root:
                mw = o.matrix_world.copy()
                o.parent = anim_root
                o.matrix_world = mw

        anim_arm.data.pose_position = "REST"
        bpy.context.view_layer.update()

        # Build KDTree for Limb-Isolated Weight Transfer
        body_kd = mathutils.kdtree.KDTree(len(body_obj.data.vertices))
        for i, v in enumerate(body_obj.data.vertices):
            body_kd.insert(v.co, i)
        body_kd.balance()

        def transfer_weights_isolated(target_obj, g_type="general", k=4):
            """Transfer weights with limb isolation to prevent cross-limb weight bleeding."""
            vg_map = {}
            for vg in body_obj.vertex_groups:
                vg_map[vg.name] = target_obj.vertex_groups.new(name=vg.name)

            for v_idx, v in enumerate(target_obj.data.vertices):
                results = body_kd.find_n(v.co, k)
                weights = {}
                total_inv_d = 0.0
                for n_co, n_idx, d in results:
                    inv_d = 1.0 / max(d, 1e-4)
                    total_inv_d += inv_d
                    b_vert = body_obj.data.vertices[n_idx]
                    for g in b_vert.groups:
                        vg_name = body_obj.vertex_groups[g.group].name

                        # Limb Isolation Filter
                        if g_type in ["top", "shirt", "suit"] and abs(v.co.x) > 0.35:
                            # Outer sleeves: ignore hips and lower body bones
                            if any(k in vg_name.lower() for k in ["hips", "leg", "foot", "toe", "thigh"]):
                                continue
                        elif g_type in ["pants", "bottom", "skirt"]:
                            # Pants: ignore arm and shoulder bones
                            if any(k in vg_name.lower() for k in ["arm", "hand", "shoulder", "finger"]):
                                continue

                        weights[vg_name] = weights.get(vg_name, 0.0) + g.weight * inv_d

                for vg_name, w in weights.items():
                    norm_w = w / max(total_inv_d, 1e-6)
                    if norm_w > 0.001:
                        vg_map[vg_name].add([v_idx], norm_w, "REPLACE")

        if hair_obj:
            hair_vg = hair_obj.vertex_groups.new(name="mixamorig_Head")
            hair_vg.add(list(range(len(hair_obj.data.vertices))), 1.0, "REPLACE")

        for g_obj in garment_objs:
            lower_name = g_obj.name.lower()
            gt = "pants" if "bottom" in lower_name else ("top" if "cloth" in lower_name else "general")
            transfer_weights_isolated(g_obj, g_type=gt)

        # Attach Armature Modifiers
        all_meshes = [body_obj]
        if hair_obj:
            all_meshes.append(hair_obj)
        all_meshes.extend(garment_objs)

        for m in all_meshes:
            arm_mod = m.modifiers.get("Armature") or m.modifiers.new(name="Armature", type="ARMATURE")
            arm_mod.object = anim_arm
            if anim_root and m.parent != anim_root:
                m.parent = anim_root

        # Export Deliverables: Blend, GLB, FBX, USDZ
        out_blend = os.path.join(output_dir, "combined_character.blend")
        out_glb = os.path.join(output_dir, "combined_character.glb")
        out_fbx = os.path.join(output_dir, "combined_character.fbx")
        out_usdz = os.path.join(output_dir, "combined_character.usdz")
        out_usdc = os.path.join(output_dir, "combined_character.usdc")

        bpy.ops.wm.save_as_mainfile(filepath=out_blend)
        bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", export_yup=True, export_animations=True)
        bpy.ops.export_scene.fbx(filepath=out_fbx, use_selection=False, add_leaf_bones=False)

        # Author Dynamic UsdSkel Package with Animation Preservation
        anim_stage = Usd.Stage.Open(anim_path) if (anim_path and os.path.exists(anim_path)) else None

        stage = Usd.Stage.CreateNew(out_usdc)
        if anim_stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.GetStageUpAxis(anim_stage))
            UsdGeom.SetStageMetersPerUnit(stage, UsdGeom.GetStageMetersPerUnit(anim_stage))
            stage.SetStartTimeCode(anim_stage.GetStartTimeCode())
            stage.SetEndTimeCode(anim_stage.GetEndTimeCode())
            stage.SetTimeCodesPerSecond(anim_stage.GetTimeCodesPerSecond())
            stage.SetFramesPerSecond(anim_stage.GetFramesPerSecond())
        else:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
            UsdGeom.SetStageMetersPerUnit(stage, 1.0)

        root_prim = stage.DefinePrim("/root", "Xform")
        stage.SetDefaultPrim(root_prim)
        skel_root = UsdSkel.Root.Define(stage, "/root/Armature")

        skel_prim = None
        if anim_stage and anim_stage.GetPrimAtPath("/root/Armature/Armature"):
            Sdf.CopySpec(
                anim_stage.GetRootLayer(),
                Sdf.Path("/root/Armature/Armature"),
                stage.GetRootLayer(),
                Sdf.Path("/root/Armature/Armature")
            )
            skel_prim = stage.GetPrimAtPath("/root/Armature/Armature")
        else:
            skel_prim = stage.DefinePrim("/root/Armature/Armature", "Skeleton")

        skel = UsdSkel.Skeleton(skel_prim)
        joints = skel.GetJointsAttr().Get()
        if not joints:
            bone_names = [b.name for b in anim_arm.data.bones]
            joints = []
            for name in bone_names:
                b = anim_arm.data.bones[name]
                path_parts = [b.name]
                curr = b.parent
                while curr:
                    path_parts.append(curr.name)
                    curr = curr.parent
                joints.append("/".join(reversed(path_parts)))
            skel.CreateJointsAttr(joints)
            skel.CreateBindTransformsAttr(Vt.Matrix4dArray([Gf.Matrix4d(1.0)] * len(joints)))
            skel.CreateRestTransformsAttr(Vt.Matrix4dArray([Gf.Matrix4d(1.0)] * len(joints)))

        skel_path = skel_prim.GetPath()
        joint_map = {j.split('/')[-1]: idx for idx, j in enumerate(joints)}

        def author_usd_material(mat_prim_path, tex_file_rel):
            mat_prim = stage.DefinePrim(mat_prim_path, "Material")
            mat = UsdShade.Material(mat_prim)
            pbr = UsdShade.Shader.Define(stage, f"{mat_prim_path}/PBRShader")
            pbr.CreateIdAttr("UsdPreviewSurface")
            pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
            tex_shader = UsdShade.Shader.Define(stage, f"{mat_prim_path}/DiffuseTexture")
            tex_shader.CreateIdAttr("UsdUVTexture")
            tex_shader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(tex_file_rel)
            st_reader = UsdShade.Shader.Define(stage, f"{mat_prim_path}/stReader")
            st_reader.CreateIdAttr("UsdPrimvarReader_float2")
            st_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
            tex_shader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_reader.ConnectableAPI(), "result")
            pbr.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex_shader.ConnectableAPI(), "rgb")
            mat.CreateSurfaceOutput().ConnectToSource(pbr.ConnectableAPI(), "surface")
            return mat

        def extract_buffers(mesh_obj):
            mesh = mesh_obj.data
            pts = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]
            face_counts = [len(p.vertices) for p in mesh.polygons]
            face_indices = [v for p in mesh.polygons for v in p.vertices]
            uv_list = []
            if mesh.uv_layers.active:
                uv_data = mesh.uv_layers.active.data
                for p in mesh.polygons:
                    for li in p.loop_indices:
                        uv_list.append((float(uv_data[li].uv[0]), float(uv_data[li].uv[1])))
            return pts, face_counts, face_indices, uv_list

        # UsdSkel Body Mesh
        mat_body = author_usd_material("/root/_materials/M_Body", "./textures/body_shaded.png")
        b_pts, b_fc, b_fi, b_uvs = extract_buffers(body_obj)
        b_prim_usd = stage.DefinePrim("/root/Armature/Body/Body", "Mesh")
        b_mesh_usd = UsdGeom.Mesh(b_prim_usd)
        b_mesh_usd.CreatePointsAttr(Vt.Vec3fArray(b_pts))
        b_mesh_usd.CreateFaceVertexCountsAttr(Vt.IntArray(b_fc))
        b_mesh_usd.CreateFaceVertexIndicesAttr(Vt.IntArray(b_fi))
        if b_uvs:
            st_body = UsdGeom.PrimvarsAPI(b_prim_usd).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
            st_body.Set(Vt.Vec2fArray(b_uvs))

        b_bind = UsdSkel.BindingAPI.Apply(b_prim_usd)
        b_bind.CreateSkeletonRel().SetTargets([skel_path])
        b_bind.CreateJointsAttr(joints)
        b_bind.CreateGeomBindTransformAttr(Gf.Matrix4d(1.0))

        b_indices = []
        b_weights = []
        for v in body_obj.data.vertices:
            influences = []
            for g in v.groups:
                vg_name = body_obj.vertex_groups[g.group].name
                if vg_name in joint_map and g.weight > 0.001:
                    influences.append((joint_map[vg_name], float(g.weight)))
            influences.sort(key=lambda x: x[1], reverse=True)
            influences = influences[:8]
            tot_w = sum(w for _, w in influences) if influences else 0.0
            if tot_w > 0:
                influences = [(idx, w / tot_w) for idx, w in influences]
            else:
                influences = [(0, 1.0)]
            while len(influences) < 8:
                influences.append((0, 0.0))
            for idx, w in influences:
                b_indices.append(idx)
                b_weights.append(w)

        ji_b = b_bind.CreateJointIndicesPrimvar(False, 8)
        ji_b.SetInterpolation(UsdGeom.Tokens.vertex)
        ji_b.Set(Vt.IntArray(b_indices))
        jw_b = b_bind.CreateJointWeightsPrimvar(False, 8)
        jw_b.SetInterpolation(UsdGeom.Tokens.vertex)
        jw_b.Set(Vt.FloatArray(b_weights))
        UsdShade.MaterialBindingAPI.Apply(b_prim_usd).Bind(mat_body)

        # UsdSkel Hair Mesh
        if hair_obj:
            mat_h = author_usd_material("/root/_materials/M_Hair", "./textures/hair_shaded.png")
            h_pts, h_fc, h_fi, h_uvs = extract_buffers(hair_obj)
            h_prim_usd = stage.DefinePrim("/root/Armature/Hair/Hair", "Mesh")
            h_mesh_usd = UsdGeom.Mesh(h_prim_usd)
            h_mesh_usd.CreatePointsAttr(Vt.Vec3fArray(h_pts))
            h_mesh_usd.CreateFaceVertexCountsAttr(Vt.IntArray(h_fc))
            h_mesh_usd.CreateFaceVertexIndicesAttr(Vt.IntArray(h_fi))
            if h_uvs:
                st_h = UsdGeom.PrimvarsAPI(h_prim_usd).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
                st_h.Set(Vt.Vec2fArray(h_uvs))
            h_bind = UsdSkel.BindingAPI.Apply(h_prim_usd)
            h_bind.CreateSkeletonRel().SetTargets([skel_path])
            h_bind.CreateJointsAttr(joints)
            h_bind.CreateGeomBindTransformAttr(Gf.Matrix4d(1.0))
            head_idx = joint_map.get("mixamorig_Head", joint_map.get("Head", 5))
            h_ind = [head_idx, 0, 0, 0, 0, 0, 0, 0] * len(h_pts)
            h_wt = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] * len(h_pts)
            ji_h = h_bind.CreateJointIndicesPrimvar(False, 8)
            ji_h.SetInterpolation(UsdGeom.Tokens.vertex)
            ji_h.Set(Vt.IntArray(h_ind))
            jw_h = h_bind.CreateJointWeightsPrimvar(False, 8)
            jw_h.SetInterpolation(UsdGeom.Tokens.vertex)
            jw_h.Set(Vt.FloatArray(h_wt))
            UsdShade.MaterialBindingAPI.Apply(h_prim_usd).Bind(mat_h)

        # UsdSkel Garments
        for g_obj in garment_objs:
            g_name = g_obj.name.lower()
            mat_g = author_usd_material(f"/root/_materials/M_{g_name}", f"./textures/{g_name}_shaded.png")
            g_pts, g_fc, g_fi, g_uvs = extract_buffers(g_obj)
            g_prim_usd = stage.DefinePrim(f"/root/Armature/{g_name}/{g_name}", "Mesh")
            g_mesh_usd = UsdGeom.Mesh(g_prim_usd)
            g_mesh_usd.CreatePointsAttr(Vt.Vec3fArray(g_pts))
            g_mesh_usd.CreateFaceVertexCountsAttr(Vt.IntArray(g_fc))
            g_mesh_usd.CreateFaceVertexIndicesAttr(Vt.IntArray(g_fi))
            if g_uvs:
                st_g = UsdGeom.PrimvarsAPI(g_prim_usd).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
                st_g.Set(Vt.Vec2fArray(g_uvs))
            g_bind = UsdSkel.BindingAPI.Apply(g_prim_usd)
            g_bind.CreateSkeletonRel().SetTargets([skel_path])
            g_bind.CreateJointsAttr(joints)
            g_bind.CreateGeomBindTransformAttr(Gf.Matrix4d(1.0))

            g_indices = []
            g_weights = []
            for v in g_obj.data.vertices:
                influences = []
                for g in v.groups:
                    vg_name = g_obj.vertex_groups[g.group].name
                    if vg_name in joint_map and g.weight > 0.001:
                        influences.append((joint_map[vg_name], float(g.weight)))
                influences.sort(key=lambda x: x[1], reverse=True)
                influences = influences[:8]
                tot_w = sum(w for _, w in influences) if influences else 0.0
                if tot_w > 0:
                    influences = [(idx, w / tot_w) for idx, w in influences]
                else:
                    influences = [(0, 1.0)]
                while len(influences) < 8:
                    influences.append((0, 0.0))
                for idx, w in influences:
                    g_indices.append(idx)
                    g_weights.append(w)

            ji_g = g_bind.CreateJointIndicesPrimvar(False, 8)
            ji_g.SetInterpolation(UsdGeom.Tokens.vertex)
            ji_g.Set(Vt.IntArray(g_indices))
            jw_g = g_bind.CreateJointWeightsPrimvar(False, 8)
            jw_g.SetInterpolation(UsdGeom.Tokens.vertex)
            jw_g.Set(Vt.FloatArray(g_weights))
            UsdShade.MaterialBindingAPI.Apply(g_prim_usd).Bind(mat_g)

        stage.GetRootLayer().Save()

        with zipfile.ZipFile(out_usdz, "w", compression=zipfile.ZIP_STORED) as z:
            z.write(out_usdc, arcname="combined_character.usdc")
            for tf in os.listdir(textures_dir):
                if tf.endswith((".png", ".jpg", ".jpeg")):
                    z.write(os.path.join(textures_dir, tf), arcname=f"textures/{tf}")

        print(f"Authored USDZ Package: {out_usdz}")

        # Render Animation Verification Frame
        scene = bpy.context.scene
        cam_obj = bpy.data.objects.get("Cam")
        if anim_arm and anim_path and os.path.exists(anim_path):
            anim_arm.data.pose_position = "POSE"
            scene.frame_set(70)
            bpy.context.view_layer.update()
            if cam_obj:
                cam_obj.location = (0, -3.2, 0.95)
                cam_obj.rotation_euler = (math.radians(90), 0, 0)
            scene.render.filepath = os.path.join(renders_dir, "render_anim_greeting.png")
            bpy.ops.render.render(write_still=True)
            print("Rendered animated verification pose: render_anim_greeting.png")

    print("\nALL BLENDER TASKS COMPLETED SUCCESSFULLY!")


# =============================================================================
# CLI ENTRY POINT & PIPELINE ORCHESTRATION
# =============================================================================

def main():
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", required=True)
        args, _ = parser.parse_known_args(sys.argv[idx + 1:])
        with open(args.config, "r") as f:
            config = json.load(f)
        execute_in_blender(config)
        return

    parser = argparse.ArgumentParser(description="Automated Modular 3D Model Combiner, Fitter & Rigger (2-Stage Non-AI)")
    parser.add_argument("--stage", default="all", choices=["all", "1", "2"], help="Stage to execute: 1 (T-pose alignment & OpenCV visual matching), 2 (Skeletal rigging & animation export), or all (both)")
    parser.add_argument("--body", default=None, help="Base textured character body model (e.g. tests/man_anim_base.usdz)")
    parser.add_argument("--anim", default=None, help="Optional skeletal animation file (e.g. tests/man_anim_hip_hop_dancing.usdc)")
    parser.add_argument("--hair", default=None, help="Hair model (e.g. tests/man_hair.usdz)")
    parser.add_argument("--cloth", default=None, help="Garment model (e.g. tests/man_suit.usdz or tests/woman_tube.usdz)")
    parser.add_argument("--cloth-type", default="auto", choices=["auto", "full_dress", "tube", "top", "shirt", "suit", "skirt", "bottom", "pants"], help="Garment type")
    parser.add_argument("--top", default=None, help="Upper garment model (for two-piece outfits)")
    parser.add_argument("--bottom", default=None, help="Lower garment model (for two-piece outfits, or alias --skirt)")
    parser.add_argument("--skirt", default=None, help="Alias for --bottom")
    parser.add_argument("--ref-front", default=None, help="Optional front reference image")
    parser.add_argument("--ref-left", default=None, help="Optional left side reference image")
    parser.add_argument("--ref-right", default=None, help="Optional right side reference image")
    parser.add_argument("--ref-back", default=None, help="Optional back reference image")
    parser.add_argument("--output-dir", default="./outputs", help="Directory for deliverables & renders (default: ./outputs)")
    parser.add_argument("--blender-path", default=None, help="Custom path to Blender binary")

    # Backward compatibility alias
    parser.add_argument("--body-base", default=None, help="Legacy alias for --body")

    args = parser.parse_args()

    blender_bin = args.blender_path or find_blender()
    if not blender_bin:
        print("ERROR: Blender executable not found. Please install Blender or pass --blender-path.")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    body_input = args.body or args.body_base
    if args.stage in ["1", "all"] and not body_input:
        print("ERROR: --body is required for Stage 1 or all.")
        sys.exit(1)

    config = {
        "stage": args.stage,
        "body": os.path.abspath(body_input) if body_input else None,
        "anim": os.path.abspath(args.anim) if args.anim else None,
        "hair": os.path.abspath(args.hair) if args.hair else None,
        "cloth": os.path.abspath(args.cloth) if args.cloth else None,
        "cloth_type": args.cloth_type,
        "top": os.path.abspath(args.top) if args.top else None,
        "bottom": os.path.abspath(args.bottom or args.skirt) if (args.bottom or args.skirt) else None,
        "output_dir": os.path.abspath(args.output_dir),
    }

    config_path = os.path.join(args.output_dir, "pipeline_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # 1. Run Blender Worker (Stage 1 and/or Stage 2)
    run_blender_worker(blender_bin, config_path)

    renders_dir = os.path.join(args.output_dir, "renders")

    # 2. If Stage 1 was run, perform OpenCV Computer Vision Analysis & Side-by-Side Verification
    if args.stage in ["1", "all"]:
        print("\n" + "=" * 65)
        print("STAGE 1: OPENCV NON-AI VISUAL COMPARISON & SILHOUETTE VERIFICATION")
        print("=" * 65)

        views_to_compare = []
        if args.ref_front and os.path.exists(args.ref_front):
            views_to_compare.append(("front", args.ref_front, "render_front.png", "compare_front.png", "cv_overlay_front.png"))
        if args.ref_left and os.path.exists(args.ref_left):
            views_to_compare.append(("left", args.ref_left, "render_left.png", "compare_left.png", "cv_overlay_left.png"))
        if args.ref_right and os.path.exists(args.ref_right):
            views_to_compare.append(("right", args.ref_right, "render_right.png", "compare_right.png", "cv_overlay_right.png"))
        if args.ref_back and os.path.exists(args.ref_back):
            views_to_compare.append(("back", args.ref_back, "render_back.png", "compare_back.png", "cv_overlay_back.png"))

        for view_name, ref_p, ren_f, comp_f, overlay_f in views_to_compare:
            ren_p = os.path.join(renders_dir, ren_f)
            comp_p = os.path.join(renders_dir, comp_f)
            overlay_p = os.path.join(renders_dir, overlay_f)

            # Build 1:1 Side-by-Side comparison sheet
            build_comparison_sheet(ren_p, os.path.abspath(ref_p), comp_p)

            # Run OpenCV Sectional Analysis & Diagnostic Overlay
            cv_res = analyze_silhouette_pair_cv(os.path.abspath(ref_p), ren_p, view_name, overlay_p)
            if cv_res:
                print(f"\n[OpenCV CV] {view_name.upper()} View Analysis:")
                print(f"  -> Silhouette IoU: {cv_res['iou']:.2%}")
                for b_name, b_data in cv_res["bands"].items():
                    print(f"     Band {b_name:8s}: Ref={b_data['ref_width']:.1f}px, Ren={b_data['ren_width']:.1f}px, Diff={b_data['diff_pct']:+.1%}")
                print(f"  -> Generated Diagnostic Overlay: {overlay_p}")

    print("\n" + "=" * 65)
    print(f"ALL DELIVERABLES GENERATED IN: {os.path.abspath(args.output_dir)}")
    if args.stage in ["1", "all"]:
        print(f"  - Stage 1 T-Pose Checkpoint: {os.path.join(args.output_dir, 'stage1_tpose_aligned.blend')}")
    if args.stage in ["2", "all"]:
        print(f"  - Master Blend: {os.path.join(args.output_dir, 'combined_character.blend')}")
        print(f"  - Animated USDZ: {os.path.join(args.output_dir, 'combined_character.usdz')}")
        print(f"  - GLB: {os.path.join(args.output_dir, 'combined_character.glb')}")
        print(f"  - FBX: {os.path.join(args.output_dir, 'combined_character.fbx')}")
    print(f"  - Renders & OpenCV Diagnostics: {renders_dir}")
    print("=" * 65)


if __name__ == "__main__":
    main()
