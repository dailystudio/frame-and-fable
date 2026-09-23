#!/usr/bin/env python3
"""
fix_chin_jaw_weights.py

Anatomically-Bounded Skinning Weight Cleaner for USDZ / USDC character models.

Solves rigging anomalies from automatic heat/voxel skinning (e.g. Mixamo):
  1. Chin & Jaw Rubber Stretching:
     - Strips stray torso (Spine/Chest), shoulder, and arm weights from chin and jaw vertices.
     - Strictly bounded to the anatomical head/jaw cylinder to prevent accidental shoulder corruption.
  2. Shoulder & Trapezius Weight Bleeding:
     - Cleans stray Head/Neck weights off outer shoulders, deltoids, and trapezius ridges.
     - Reallocates weight to Shoulder (Clavicle) and Spine2 bones.
  3. Upper Back Arm Bleeding:
     - Strips accidental upper arm weights bleeding into the scapula / mid-back in A-pose.
  4. Platform Compliance:
     - Clamps influences to 4 per vertex (Apple RealityKit / PICO / GPU standard) and renormalizes.
"""

import argparse
import os
import shutil
import sys
import tempfile

# If run with standard python3 lacking pxr (USD), re-launch via Blender's Python
try:
    import pxr
except ImportError:
    mac_paths = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/Applications/Blender.app/Contents/MacOS/blender",
    ]
    env_blender = os.environ.get("BLENDER_BIN")
    blender_bin = env_blender or shutil.which("blender")
    if not blender_bin:
        for p in mac_paths:
            if os.path.exists(p):
                blender_bin = p
                break

    if blender_bin and os.path.exists(blender_bin):
        cmd = [blender_bin, "-b", "--python", os.path.abspath(__file__), "--"] + sys.argv[1:]
        import subprocess
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    else:
        print("Error: pxr (Universal Scene Description) not found and Blender executable was not located.")
        sys.exit(1)

from pxr import Sdf, Usd, UsdGeom, UsdSkel, UsdUtils
import numpy as np


def find_skeleton_and_meshes(stage):
    """Dynamically finds the Skeleton and all skinned Mesh prims in the USD stage."""
    skel_prim = None
    meshes = []
    for p in stage.Traverse():
        if not skel_prim and p.IsA(UsdSkel.Skeleton):
            skel_prim = p
        if p.IsA(UsdGeom.Mesh) and p.HasAPI(UsdSkel.BindingAPI):
            binding = UsdSkel.BindingAPI(p)
            if binding.GetJointIndicesAttr().HasValue():
                meshes.append(p)
    return skel_prim, meshes


def identify_joints(joints):
    """
    Identifies head, neck, spine2, shoulders, and arm joints using standard naming conventions.
    Compatible with Mixamo, Unreal, Unity HumanIK, Blender Rigify, DAZ, CC4, etc.
    """
    head_idx = None
    neck_idx = None
    spine2_idx = None
    l_sh_idx = None
    r_sh_idx = None

    invalid_for_head = set()
    l_arm_indices = []
    r_arm_indices = []

    for idx, j in enumerate(joints):
        name = j.split("/")[-1].lower()
        if "head" in name and not any(x in name for x in ["top", "end", "nub", "tip"]):
            head_idx = idx
        elif "neck" in name:
            neck_idx = idx
        elif "spine2" in name or "chest" in name:
            spine2_idx = idx
        elif any(x in name for x in ["leftshoulder", "l_shoulder", "leftclavicle", "l_clavicle"]):
            l_sh_idx = idx
        elif any(x in name for x in ["rightshoulder", "r_shoulder", "rightclavicle", "r_clavicle"]):
            r_sh_idx = idx

        # Bones that should NEVER directly influence the head or chin:
        if any(token in name for token in ["spine", "chest", "torso", "hip", "pelvis",
                                           "shoulder", "clavicle", "arm", "hand"]):
            invalid_for_head.add(idx)

        # Arm bones for checking back bleed:
        if any(token in name for token in ["leftarm", "leftforearm", "lefthand"]):
            l_arm_indices.append(idx)
        elif any(token in name for token in ["rightarm", "rightforearm", "righthand"]):
            r_arm_indices.append(idx)

    return head_idx, neck_idx, spine2_idx, l_sh_idx, r_sh_idx, invalid_for_head, l_arm_indices, r_arm_indices


def clean_skinning_weights(stage, skel_prim, mesh_prim, fix_chin_jaw=True, fix_shoulders_back=True,
                           torso_cutoff=-0.20, beard_mode=False):
    """
    Cleans up contaminated vertex weights using an anatomically bounded coordinate frame:
      1. Bounded Chin & Jaw: Strips torso/arm bleed within the cranial/facial volume.
         Protects chest accessories (scarves, collars, necklaces) using a torso-vertical plane cutoff.
         Optionally supports beard-mode with height gradient falloff for longer hanging beards.
      2. Shoulder & Trapezius: Cleans stray Head weights off outer shoulders and deltoids.
      3. Upper Back: Strips Arm bone bleed off the scapula / mid-back.
      4. Clamps influences to 4 per vertex and normalizes.
    """
    mesh = UsdGeom.Mesh(mesh_prim)
    points = np.array(mesh.GetPointsAttr().Get())
    binding = UsdSkel.BindingAPI(mesh_prim)

    weights_attr = binding.GetJointWeightsAttr()
    indices_attr = binding.GetJointIndicesAttr()
    orig_elem_size = binding.GetJointIndicesPrimvar().GetElementSize()

    weights = np.array(weights_attr.Get()).reshape(-1, orig_elem_size)
    indices = np.array(indices_attr.Get()).reshape(-1, orig_elem_size)

    skel = UsdSkel.Skeleton(skel_prim)
    joints = list(skel.GetJointsAttr().Get())
    bind_xforms = skel.GetBindTransformsAttr().Get()

    (head_idx, neck_idx, spine2_idx, l_sh_idx, r_sh_idx,
     invalid_for_head, l_arm_indices, r_arm_indices) = identify_joints(joints)

    if head_idx is None:
        print(f"[-] Warning: Head bone not found in skeleton '{skel_prim.GetPath()}'. Skipping.")
        return 0

    # Transform mesh points to skeleton space using geomBindTransform
    gbt = binding.GetGeomBindTransformAttr().Get()
    if gbt:
        M = np.array([[gbt[i][j] for j in range(4)] for i in range(4)])
        pts_h = np.hstack([points, np.ones((len(points), 1))])
        skel_pts = (pts_h @ M)[:, :3]
    else:
        skel_pts = points

    p_head = np.array(bind_xforms[head_idx].ExtractTranslation())
    p_neck = np.array(bind_xforms[neck_idx].ExtractTranslation()) if neck_idx is not None else p_head
    p_spine2 = np.array(bind_xforms[spine2_idx].ExtractTranslation()) if spine2_idx is not None else p_neck

    # Reference Frame Computation: Up, Lateral, Forward
    up_vec = p_head - p_neck
    d_hn = np.linalg.norm(up_vec)
    if d_hn < 1e-4:
        d_hn = 10.0
        up_dir = np.array([0.0, 1.0, 0.0])
    else:
        up_dir = up_vec / d_hn

    # Torso Vertical Axis (Neck from Spine2) - critical for separating chest accessories from chin
    if spine2_idx is not None and neck_idx is not None:
        torso_vec = p_neck - p_spine2
        d_spine_neck = np.linalg.norm(torso_vec)
        torso_up = torso_vec / d_spine_neck if d_spine_neck > 1e-4 else up_dir
    else:
        torso_up = up_dir
        d_spine_neck = 15.0

    if l_sh_idx is not None and r_sh_idx is not None:
        p_l_sh = np.array(bind_xforms[l_sh_idx].ExtractTranslation())
        p_r_sh = np.array(bind_xforms[r_sh_idx].ExtractTranslation())
        lat_vec = p_l_sh - p_r_sh
        sh_span = np.linalg.norm(lat_vec) / 2.0
        lat_dir = lat_vec / (sh_span * 2.0)
    else:
        sh_span = d_hn * 1.8
        lat_dir = np.array([1.0, 0.0, 0.0])
        p_l_sh = p_neck + lat_dir * sh_span
        p_r_sh = p_neck - lat_dir * sh_span

    fwd_dir = np.cross(lat_dir, up_dir)
    norm_fwd = np.linalg.norm(fwd_dir)
    if norm_fwd > 1e-4:
        fwd_dir = fwd_dir / norm_fwd
    else:
        fwd_dir = np.array([0.0, 0.0, 1.0])

    # Robust anatomical head scale based on neck distance and shoulder span
    head_scale = max(d_hn, sh_span * 0.60)

    d_head = np.linalg.norm(skel_pts - p_head, axis=1)
    d_neck = np.linalg.norm(skel_pts - p_neck, axis=1)

    chin_fixed = 0
    shoulder_fixed = 0
    back_arm_fixed = 0

    new_indices = []
    new_weights = []

    for i in range(len(points)):
        pt = skel_pts[i]
        rel = pt - p_neck
        h = float(np.dot(rel, up_dir))
        lat = float(np.dot(rel, lat_dir))
        fwd = float(np.dot(rel, fwd_dir))
        torso_h = float(np.dot(rel, torso_up))

        row_ind = indices[i]
        row_wt = weights[i]
        w_dict = {}
        for j_idx, w in zip(row_ind, row_wt):
            if w > 1e-5:
                w_dict[int(j_idx)] = w_dict.get(int(j_idx), 0.0) + float(w)

        sh_w = (w_dict.get(l_sh_idx, 0.0) if l_sh_idx is not None else 0.0) + (w_dict.get(r_sh_idx, 0.0) if r_sh_idx is not None else 0.0)
        spine_w = w_dict.get(spine2_idx, 0.0) if spine2_idx is not None else 0.0
        head_w = w_dict.get(head_idx, 0.0)

        # ----------------------------------------------------------------------
        # 1. Targeted Chin & Jaw Weight Fix (Anatomically Bounded)
        # ----------------------------------------------------------------------
        if fix_chin_jaw:
            min_torso_h = torso_cutoff * d_spine_neck
            if beard_mode:
                min_torso_h = -0.55 * d_spine_neck

            is_chin_jaw = (
                fwd >= 0.5 and
                abs(lat) <= 0.60 * sh_span and
                h >= -0.50 * head_scale and
                h <= 2.20 * head_scale and
                torso_h >= min_torso_h and
                sh_w < 0.20 and
                (d_head[i] < 6.0 * head_scale or d_neck[i] < 6.0 * head_scale)
            )

            is_upper_head = (
                h >= 0.50 * head_scale and
                abs(lat) <= 0.65 * sh_span and
                head_w >= 0.35 and
                d_head[i] <= 4.0 * head_scale
            )

            if is_chin_jaw or is_upper_head:
                bad_w = sum(w_dict.pop(k, 0.0) for k in list(w_dict.keys()) if k in invalid_for_head)
                if bad_w > 0:
                    if beard_mode and torso_h < -0.15 * d_spine_neck:
                        # Smooth gradient falloff for hanging beard tips resting on chest
                        alpha = max(0.0, min(1.0, (torso_h - min_torso_h) / (-0.15 * d_spine_neck - min_torso_h)))
                        head_portion = bad_w * (0.5 + 0.5 * alpha)
                        neck_portion = bad_w - head_portion
                        w_dict[head_idx] = w_dict.get(head_idx, 0.0) + head_portion
                        if neck_idx is not None:
                            w_dict[neck_idx] = w_dict.get(neck_idx, 0.0) + neck_portion
                        else:
                            w_dict[head_idx] = w_dict.get(head_idx, 0.0) + neck_portion
                    else:
                        w_dict[head_idx] = w_dict.get(head_idx, 0.0) + bad_w
                    chin_fixed += 1

        # ----------------------------------------------------------------------
        # 2. Targeted Shoulder / Trapezius Weight Fix
        # ----------------------------------------------------------------------
        if fix_shoulders_back:
            is_shoulder_back = (
                (abs(lat) >= 0.55 * sh_span and h <= 0.65 * head_scale) or
                (fwd <= -0.5 and abs(lat) >= 0.30 * sh_span and h <= 0.50 * head_scale) or
                (fwd <= -1.0 and h <= 0.0)
            )
            if is_shoulder_back and head_idx in w_dict:
                # Strip stray head weight only if vertex is primarily torso/shoulder
                if (spine_w + sh_w) >= 0.40 and head_w <= 0.35:
                    stray_head_w = w_dict.pop(head_idx)
                    valid_bones = [k for k in w_dict.keys() if k != head_idx]
                    if valid_bones:
                        tot_v = sum(w_dict[k] for k in valid_bones)
                        for k in valid_bones:
                            w_dict[k] += stray_head_w * (w_dict[k] / tot_v)
                    else:
                        target_sh = l_sh_idx if lat > 0 else r_sh_idx
                        target_bone = target_sh if target_sh is not None else spine2_idx
                        w_dict[target_bone] = stray_head_w
                    shoulder_fixed += 1

            # ------------------------------------------------------------------
            # 3. Arm Bleed onto Upper Back / Scapula
            # ------------------------------------------------------------------
            is_mid_back = (fwd < -2.0) and (abs(lat) < 0.45 * sh_span) and (h < -0.1 * head_scale)
            if is_mid_back and spine2_idx is not None:
                stray_arm_w = sum(w_dict.pop(k, 0.0) for k in list(w_dict.keys()) if k in l_arm_indices or k in r_arm_indices)
                if stray_arm_w > 0:
                    w_dict[spine2_idx] = w_dict.get(spine2_idx, 0.0) + stray_arm_w
                    back_arm_fixed += 1

        # Keep top 4 influences and normalize (Apple RealityKit / GPU standard)
        sorted_items = sorted(w_dict.items(), key=lambda x: -x[1])[:4]
        total_w = sum(x[1] for x in sorted_items)
        if total_w > 0:
            norm_items = [(x[0], x[1] / total_w) for x in sorted_items]
        else:
            norm_items = [(head_idx, 1.0)]

        while len(norm_items) < 4:
            norm_items.append((0, 0.0))

        new_indices.append([x[0] for x in norm_items])
        new_weights.append([x[1] for x in norm_items])

    new_indices_flat = np.array(new_indices, dtype=np.int32).flatten()
    new_weights_flat = np.array(new_weights, dtype=np.float32).flatten()

    binding.GetJointIndicesPrimvar().SetElementSize(4)
    binding.GetJointWeightsPrimvar().SetElementSize(4)
    indices_attr.Set(new_indices_flat)
    weights_attr.Set(new_weights_flat)

    print(f"[✓] Processed '{mesh_prim.GetName()}':")
    print(f"    - Chin & Jaw fixed        : {chin_fixed} vertices")
    print(f"    - Shoulder/Trap stray head: {shoulder_fixed} vertices")
    print(f"    - Back arm bleed cleaned  : {back_arm_fixed} vertices")
    print(f"    - Influence limit clamped to 4 and normalized.")
    return chin_fixed + shoulder_fixed + back_arm_fixed


def fix_usdz_file(input_file, output_file=None, in_place=False, from_backup=False,
                  fix_chin_jaw=True, fix_shoulders_back=True,
                  torso_cutoff=-0.20, beard_mode=False):
    """Processes a .usdz (or .usdc) file and cleans skinning weights."""
    abs_input = os.path.abspath(input_file)
    if not os.path.exists(abs_input):
        print(f"Error: File not found: {abs_input}")
        return False

    is_usdz = abs_input.lower().endswith(".usdz")
    backup_file = os.path.splitext(abs_input)[0] + ("_backup.usdz" if is_usdz else "_backup.usdc")

    # If from_backup is requested, read from pristine backup file
    if from_backup and os.path.exists(backup_file):
        read_source = backup_file
        print(f"[*] Reading from pristine backup: {os.path.basename(backup_file)}")
    else:
        read_source = abs_input

    if in_place:
        abs_output = abs_input
    elif output_file:
        abs_output = os.path.abspath(output_file)
    else:
        suffix = "_fixed.usdz" if is_usdz else "_fixed.usdc"
        abs_output = os.path.splitext(abs_input)[0] + suffix

    print(f"\n==========================================")
    print(f"Processing: {os.path.basename(abs_input)}")
    print(f"Output:     {os.path.basename(abs_output)}")
    print(f"==========================================")

    if is_usdz:
        with tempfile.TemporaryDirectory() as tmpdir:
            shutil.unpack_archive(read_source, tmpdir, "zip")
            base_usd = None
            for root, _, files in os.walk(tmpdir):
                for f in files:
                    if f.endswith(".usdc") or f.endswith(".usd"):
                        base_usd = os.path.join(root, f)
                        break
                if base_usd:
                    break

            if not base_usd:
                print(f"Error: No USD file found inside {read_source}")
                return False

            stage = Usd.Stage.Open(base_usd)
            skel_prim, meshes = find_skeleton_and_meshes(stage)
            if not skel_prim or not meshes:
                print("Error: Could not find Skeleton or Skinned Mesh in stage.")
                return False

            for mesh_prim in meshes:
                clean_skinning_weights(stage, skel_prim, mesh_prim,
                                       fix_chin_jaw=fix_chin_jaw,
                                       fix_shoulders_back=fix_shoulders_back,
                                       torso_cutoff=torso_cutoff,
                                       beard_mode=beard_mode)

            stage.Save()

            if in_place and not os.path.exists(backup_file):
                shutil.copyfile(abs_input, backup_file)
                print(f"[✓] Backup created at: {backup_file}")

            if os.path.exists(abs_output):
                os.remove(abs_output)

            success = UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath(base_usd), abs_output)
            if not success:
                success = UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(base_usd), abs_output)

            if success:
                print(f"[✓] Successfully saved: {abs_output}")
                return True
            else:
                print(f"Error: Failed to package USDZ at: {abs_output}")
                return False
    else:
        if from_backup and read_source != abs_input:
            # Copy backup to a temporary stage to avoid modifying backup in place
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_file = os.path.join(tmpdir, os.path.basename(read_source))
                shutil.copyfile(read_source, tmp_file)
                stage = Usd.Stage.Open(tmp_file)
                skel_prim, meshes = find_skeleton_and_meshes(stage)
                if not skel_prim or not meshes:
                    print("Error: Could not find Skeleton or Skinned Mesh in stage.")
                    return False

                for mesh_prim in meshes:
                    clean_skinning_weights(stage, skel_prim, mesh_prim,
                                           fix_chin_jaw=fix_chin_jaw,
                                           fix_shoulders_back=fix_shoulders_back,
                                           torso_cutoff=torso_cutoff,
                                           beard_mode=beard_mode)

                stage.Save()
                shutil.copyfile(tmp_file, abs_output)
                print(f"[✓] Successfully exported from backup to: {abs_output}")
                return True
        else:
            stage = Usd.Stage.Open(abs_input)
            skel_prim, meshes = find_skeleton_and_meshes(stage)
            if not skel_prim or not meshes:
                print("Error: Could not find Skeleton or Skinned Mesh in stage.")
                return False

            for mesh_prim in meshes:
                clean_skinning_weights(stage, skel_prim, mesh_prim,
                                       fix_chin_jaw=fix_chin_jaw,
                                       fix_shoulders_back=fix_shoulders_back,
                                       torso_cutoff=torso_cutoff,
                                       beard_mode=beard_mode)

            if in_place:
                if not os.path.exists(backup_file):
                    shutil.copyfile(abs_input, backup_file)
                    print(f"[✓] Backup created at: {backup_file}")
                stage.Save()
                print(f"[✓] Successfully updated in-place: {abs_input}")
            else:
                stage.GetRootLayer().Export(abs_output)
                print(f"[✓] Successfully exported: {abs_output}")
            return True


def main():
    args_list = sys.argv[1:]
    if "--" in args_list:
        args_list = args_list[args_list.index("--") + 1:]

    parser = argparse.ArgumentParser(
        description="Fix chin, jaw, shoulder, and back skinning weights on rigged USDZ/USDC characters."
    )
    parser.add_argument(
        "inputs", nargs="*", help="Path(s) to .usdz or .usdc files to clean."
    )
    parser.add_argument(
        "-o", "--output", help="Output file path (only when processing a single input file)."
    )
    parser.add_argument(
        "--in-place", action="store_true", help="Overwrite the input file in place (creates a _backup file if none exists)."
    )
    parser.add_argument(
        "--from-backup", action="store_true", help="Read from existing <file>_backup.<ext> as pristine source."
    )
    parser.add_argument(
        "--no-chin-jaw", action="store_true", help="Skip chin & jaw weight repair."
    )
    parser.add_argument(
        "--no-shoulders-back", action="store_true", help="Skip shoulder and upper back weight repair."
    )
    parser.add_argument(
        "--torso-cutoff", type=float, default=-0.20,
        help="Relative torso height cutoff (-1.0 to 0.0) below the neck to protect chest clothing/scarves/necklaces (default: -0.20)."
    )
    parser.add_argument(
        "--beard-mode", action="store_true",
        help="Enable beard mode with height gradient falloff down onto chest for long beards."
    )

    args = parser.parse_args(args_list)

    if not args.inputs:
        parser.print_help()
        sys.exit(0)

    if args.output and len(args.inputs) > 1:
        print("Error: --output can only be specified when processing a single input file.")
        sys.exit(1)

    for f in args.inputs:
        fix_usdz_file(
            f,
            output_file=args.output,
            in_place=args.in_place,
            from_backup=args.from_backup,
            fix_chin_jaw=not args.no_chin_jaw,
            fix_shoulders_back=not args.no_shoulders_back,
            torso_cutoff=args.torso_cutoff,
            beard_mode=args.beard_mode,
        )


if __name__ == "__main__":
    main()
